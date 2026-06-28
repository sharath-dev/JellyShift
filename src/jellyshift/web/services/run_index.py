from __future__ import annotations

from pathlib import Path

from jellyshift.run_recorder import RunRecord, load_run_record
from jellyshift.web.services.log_parser import parse_log_file


def runs_dir_for_config(config_dir: Path) -> Path:
    return config_dir / "logs" / "runs"


def list_invocations(
    *,
    config_dir: Path,
    log_file: Path | None,
    page: int = 1,
    per_page: int = 50,
    status: str | None = None,
    media_type: str | None = None,
    search: str | None = None,
) -> tuple[list[RunRecord], int]:
    runs: dict[str, RunRecord] = {}

    runs_path = runs_dir_for_config(config_dir)
    if runs_path.exists():
        for path in runs_path.glob("*.json"):
            try:
                record = load_run_record(path)
                runs[record.run_id] = record
            except (OSError, ValueError, KeyError):
                continue

    if log_file is not None:
        for parsed in parse_log_file(log_file):
            if parsed.run_id not in runs:
                runs[parsed.run_id] = parsed
            elif not runs[parsed.run_id].log_lines and parsed.log_lines:
                runs[parsed.run_id].log_lines = parsed.log_lines

    items = sorted(runs.values(), key=lambda r: r.started_at, reverse=True)

    if status:
        items = [r for r in items if r.status == status]
    if media_type:
        items = [
            r for r in items
            if r.media.classified_as == media_type
        ]
    if search:
        q = search.lower()
        items = [
            r for r in items
            if r.inputs and (
                q in r.inputs.torrent_name.lower()
                or q in r.inputs.content_path.lower()
            )
        ]

    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    return items[start:end], total


def get_invocation(
    *,
    config_dir: Path,
    log_file: Path | None,
    run_id: str,
) -> RunRecord | None:
    json_path = runs_dir_for_config(config_dir) / f"{run_id}.json"
    if json_path.exists():
        record = load_run_record(json_path)
        if not record.log_lines and log_file is not None:
            for parsed in parse_log_file(log_file):
                if parsed.run_id == run_id:
                    record.log_lines = parsed.log_lines
                    break
        return record

    if log_file is not None:
        for parsed in parse_log_file(log_file):
            if parsed.run_id == run_id:
                return parsed
    return None
