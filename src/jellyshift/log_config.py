from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

DEFAULT_LOG_RELATIVE = Path("logs") / "jellyshift.log"
FALLBACK_LOG = Path("/tmp/jellyshift.log")

_CONSOLE_FORMAT = "%(levelname)-8s %(message)s"
_FILE_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _open_file_handler(
    path: Path,
    *,
    max_bytes: int,
    backup_count: int,
) -> logging.handlers.RotatingFileHandler | None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Verify writable before handing to the handler.
        with open(path, "a", encoding="utf-8"):
            pass
        handler = logging.handlers.RotatingFileHandler(
            path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(
            logging.Formatter(_FILE_FORMAT, datefmt=_DATE_FORMAT)
        )
        return handler
    except OSError:
        return None


def resolve_log_file(
    path: str | Path | None,
    *,
    base_dir: Path | None = None,
) -> Path | None:
    """Return an expanded log path, or None when file logging is disabled.

    Relative paths are resolved against *base_dir* (typically the config file
    directory, i.e. the JellyShift application folder).
    """
    if path is None:
        if base_dir is None:
            return None
        return (base_dir / DEFAULT_LOG_RELATIVE).resolve()

    if isinstance(path, str) and path.lower() in ("", "none", "null", "false"):
        return None

    expanded = Path(str(path).replace("~", str(Path.home()))).expanduser()
    if not expanded.is_absolute() and base_dir is not None:
        expanded = (base_dir / expanded).resolve()
    return expanded


def setup_logging(
    *,
    level: str = "INFO",
    log_file: str | Path | None = None,
    verbose: bool = False,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 3,
) -> logging.Logger:
    """Configure root jellyshift logging to stderr and an optional rotating log file."""
    global _configured

    resolved_level = logging.DEBUG if verbose else getattr(logging, level.upper(), logging.INFO)
    resolved_file = None if log_file is None else Path(log_file)

    root = logging.getLogger("jellyshift")
    root.handlers.clear()
    root.setLevel(resolved_level)
    root.propagate = False

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(resolved_level)
    console.setFormatter(logging.Formatter(_CONSOLE_FORMAT))
    root.addHandler(console)

    if resolved_file is not None:
        file_handler = _open_file_handler(
            resolved_file,
            max_bytes=max_bytes,
            backup_count=backup_count,
        )
        if file_handler is not None:
            root.addHandler(file_handler)
            root.debug("File logging enabled: %s", resolved_file)
        else:
            root.warning(
                "Cannot write to %s — logging to %s instead",
                resolved_file,
                FALLBACK_LOG,
            )
            fallback = _open_file_handler(
                FALLBACK_LOG,
                max_bytes=max_bytes,
                backup_count=backup_count,
            )
            if fallback is not None:
                root.addHandler(fallback)

    if _configured:
        root.debug("Logging reconfigured (level=%s)", logging.getLevelName(resolved_level))
    else:
        root.debug(
            "Logging initialized (level=%s, file=%s)",
            logging.getLevelName(resolved_level),
            resolved_file,
        )
    _configured = True
    return root


def log_run_context(
    logger: logging.Logger,
    *,
    content_path: Path,
    torrent_name: str,
    category: str | None,
    config_file: Path,
    dry_run: bool,
    force: bool,
) -> None:
    """Log the inputs for a single hook invocation."""
    logger.info("─" * 60)
    logger.info("JellyShift run started")
    logger.info("  config:       %s", config_file)
    logger.info("  content_path: %s", content_path)
    logger.info("  torrent_name: %r", torrent_name)
    logger.info("  category:     %r", category or "(none)")
    logger.info("  dry_run:      %s", dry_run)
    logger.info("  force:        %s", force)
