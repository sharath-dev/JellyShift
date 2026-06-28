"""CLI entry point invoked by qBittorrent on torrent completion.

Typical qBittorrent completion command:
    jellyshift --config C:\\JellyShift\\config.yaml "%F" --category "%L" --torrent-name "%N"
"""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer

from .classifier import MediaType, classify
from .config import Config
from .log_config import log_run_context, resolve_log_file, setup_logging
from .processor import process_movie, process_tv
from .review import send_to_review
from .run_recorder import RunRecorder
from .tmdb import TmdbClient
from . import web_service

app = typer.Typer(
    help="Import a qBittorrent download into Jellyfin library paths.",
    no_args_is_help=True,
)

service_app = typer.Typer(help="Manage JellyShift Web UI as a background service.")
app.add_typer(service_app, name="service")

log = logging.getLogger("jellyshift")


@app.command()
def main(
    content_path: Path = typer.Argument(
        ...,
        help="Downloaded file or folder — use qBittorrent token %%F.",
    ),
    config_file: Path = typer.Option(
        Path("config.yaml"),
        "--config",
        "-c",
        help="Path to config.yaml.",
    ),
    category: Optional[str] = typer.Option(
        None,
        "--category",
        help="qBittorrent category (%%L). Skips heuristic classification when set.",
    ),
    torrent_name: Optional[str] = typer.Option(
        None,
        "--torrent-name",
        help="Raw torrent name (%%N). Falls back to the basename of CONTENT_PATH.",
    ),
    dry_run: Optional[bool] = typer.Option(
        None,
        "--dry-run/--no-dry-run",
        help="Preview moves without touching the filesystem.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite existing files at the destination.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Debug logging."),
    log_file: Optional[Path] = typer.Option(
        None,
        "--log-file",
        help="Override log file path from config (use 'none' to disable file logging).",
    ),
) -> None:
    config_dir = config_file.resolve().parent if config_file.exists() else Path.cwd()

    if log_file is not None:
        effective_log_file = resolve_log_file(str(log_file), base_dir=config_dir)
    else:
        effective_log_file = resolve_log_file(None, base_dir=config_dir)

    setup_logging(
        level="DEBUG" if verbose else "INFO",
        log_file=effective_log_file,
        verbose=verbose,
    )

    if not config_file.exists():
        log.error("Config file not found: %s", config_file)
        typer.echo(f"Config file not found: {config_file}", err=True)
        raise typer.Exit(1)

    config = Config.load(config_file)

    if dry_run is not None:
        config.dry_run = dry_run

    # Re-apply config log settings now that config is loaded.
    if log_file is not None:
        effective_log_file = resolve_log_file(str(log_file), base_dir=config_dir)
    else:
        effective_log_file = config.log_file
    setup_logging(
        level=config.log_level,
        log_file=effective_log_file,
        verbose=verbose,
        max_bytes=config.log_max_bytes,
        backup_count=config.log_backup_count,
    )

    if not content_path.exists():
        log.error("Content path does not exist: %s", content_path)
        typer.echo(f"Content path does not exist: {content_path}", err=True)
        raise typer.Exit(1)

    # qBittorrent passes "" when no category is set — treat as unset.
    if category is not None and not category.strip():
        category = None

    name = torrent_name or content_path.name

    runs_dir = config_dir / "logs" / "runs"
    recorder = RunRecorder(runs_dir=runs_dir)
    recorder.attach()
    recorder.set_inputs(
        content_path=content_path,
        torrent_name=name,
        category=category,
        config_file=config_file,
        dry_run=config.dry_run,
        force=force,
    )

    log_run_context(
        log,
        content_path=content_path,
        torrent_name=name,
        category=category,
        config_file=config_file,
        dry_run=config.dry_run,
        force=force,
        run_id=recorder.run_id,
    )

    media_type: MediaType = classify(
        name, category=category, category_map=config.category_map
    )
    log.info("Classified as: %s", media_type)
    recorder.set_classified(media_type)
    log.debug(
        "Classification detail: torrent_name=%r category=%r map=%s",
        name,
        category,
        config.category_map,
    )

    if not config.tmdb_api_key or config.tmdb_api_key == "YOUR_TMDB_API_KEY":
        log.warning(
            "No TMDB API key configured — all items will use parse-only fallback."
        )

    tmdb = TmdbClient(config.tmdb_api_key)
    shared = dict(
        torrent_name=name,
        tmdb=tmdb,
        config=config,
        dry_run=config.dry_run,
        force=force,
    )

    try:
        if media_type == "movie":
            process_movie(content_path, **shared)  # type: ignore[arg-type]
        elif media_type == "tv":
            process_tv(content_path, **shared)  # type: ignore[arg-type]
        else:
            log.warning("Could not classify %r — sending to review", name)
            send_to_review(
                content_path,
                config.review_dir,
                "unclassified media type",
                torrent_name=name,
                dry_run=config.dry_run,
            )
        if recorder.record.media.sent_to_review:
            recorder.finish(status="review")
        else:
            recorder.finish(status="success")
        log.info("JellyShift run finished successfully")
    except Exception as exc:
        recorder.finish(status="failed", error=str(exc))
        log.exception("JellyShift run failed")
        raise
    finally:
        recorder.detach()


@app.command()
def serve(
    config_file: Path = typer.Option(
        Path("config.yaml"),
        "--config",
        "-c",
        help="Path to config.yaml.",
    ),
    host: Optional[str] = typer.Option(
        None,
        "--host",
        help="Bind host (overrides config web.host).",
    ),
    port: Optional[int] = typer.Option(
        None,
        "--port",
        help="Bind port (overrides config web.port).",
    ),
) -> None:
    """Start the JellyShift web UI."""
    try:
        import uvicorn
        from .web.app import create_app
    except ImportError as exc:
        typer.echo(
            "Web UI dependencies not installed. Run: pip install '.[web]'",
            err=True,
        )
        raise typer.Exit(1) from exc

    if not config_file.exists():
        typer.echo(f"Config file not found: {config_file}", err=True)
        raise typer.Exit(1)

    config = Config.load(config_file)
    bind_host = host or config.web.host
    bind_port = port or config.web.port
    app_instance = create_app(config_file, host=bind_host, port=bind_port)

    typer.echo(f"JellyShift WebUI at http://{bind_host}:{bind_port}")
    uvicorn.run(app_instance, host=bind_host, port=bind_port, log_level="info")


@service_app.command("install")
def service_install(
    config_file: Path = typer.Option(
        Path("config.yaml"),
        "--config",
        "-c",
        help="Path to config.yaml.",
    ),
) -> None:
    """Install and start a systemd user service (persists after terminal close)."""
    if not config_file.exists():
        typer.echo(f"Config file not found: {config_file}", err=True)
        raise typer.Exit(1)
    app_dir = config_file.resolve().parent
    try:
        web_service.install_service(app_dir=app_dir, config_file=config_file)
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Installed {web_service.SERVICE_NAME}")
    typer.echo("Web UI will restart automatically on failure and after WSL reboot.")
    typer.echo("Status:  jellyshift service status")
    typer.echo("Logs:    journalctl --user -u jellyshift-web -f")


@service_app.command("uninstall")
def service_uninstall() -> None:
    """Stop and remove the systemd user service."""
    web_service.uninstall_service()
    typer.echo(f"Removed {web_service.SERVICE_NAME}")


@service_app.command("status")
def service_status_cmd() -> None:
    """Show systemd service status."""
    typer.echo(web_service.service_status())


@service_app.command("start")
def service_start() -> None:
    """Start the Web UI service."""
    try:
        web_service.service_action("start")
    except subprocess.CalledProcessError as exc:
        typer.echo(exc.stderr or str(exc), err=True)
        raise typer.Exit(exc.returncode) from exc


@service_app.command("stop")
def service_stop() -> None:
    """Stop the Web UI service."""
    try:
        web_service.service_action("stop")
    except subprocess.CalledProcessError as exc:
        typer.echo(exc.stderr or str(exc), err=True)
        raise typer.Exit(exc.returncode) from exc


@service_app.command("restart")
def service_restart() -> None:
    """Restart the Web UI service."""
    try:
        web_service.service_action("restart")
    except subprocess.CalledProcessError as exc:
        typer.echo(exc.stderr or str(exc), err=True)
        raise typer.Exit(exc.returncode) from exc


if __name__ == "__main__":
    app()
