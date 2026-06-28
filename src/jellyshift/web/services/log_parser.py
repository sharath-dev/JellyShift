from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from jellyshift.run_recorder import FileMove, RunInputs, RunMedia, RunRecord

_LOG_LINE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+)\s+\[([^\]]+)\] (.+)$"
)
_RUN_ID = re.compile(r"run_id:\s+(\S+)")
_SEPARATOR = "─" * 60
_RUN_START = "JellyShift run started"
_CLASSIFIED = re.compile(r"Classified as: (\w+)")
_TMDB_MATCH = re.compile(r"TMDB matched (?:series|movie): (.+)")
_MOVED = re.compile(r"(?:MOVED|DRY-RUN)\s+(.+?)\s+→\s+(.+)")
_SKIP = re.compile(r"SKIP \(already exists\): (.+)")
_REVIEW = re.compile(r"REVIEW\s+(.+?)\s+→\s+(.+?) \((.+)\)")


@dataclass
class ParsedLogLine:
    timestamp: str
    level: str
    logger: str
    message: str
    raw: str


def _collect_log_files(log_file: Path) -> list[Path]:
    if not log_file.exists():
        return []
    files = [log_file]
    for i in range(1, 10):
        rotated = Path(f"{log_file}.{i}")
        if rotated.exists():
            files.append(rotated)
        else:
            break
    return files


def parse_log_file(log_file: Path) -> list[RunRecord]:
    """Parse jellyshift.log into RunRecord objects for runs without JSON index."""
    all_lines: list[str] = []
    for path in reversed(_collect_log_files(log_file)):
        all_lines.extend(path.read_text(encoding="utf-8", errors="replace").splitlines())

    runs: list[RunRecord] = []
    current_lines: list[str] = []
    current_meta: dict[str, str | bool | None] = {}
    in_run = False
    run_id: str | None = None
    started_at: str | None = None
    media = RunMedia()
    status = "unknown"

    def finalize() -> None:
        nonlocal current_lines, current_meta, in_run, run_id, started_at, media, status
        if not in_run or not started_at:
            current_lines = []
            return

        content_path = str(current_meta.get("content_path", ""))
        torrent_name = str(current_meta.get("torrent_name", "")).strip("'\"")
        category_raw = str(current_meta.get("category", "(none)"))
        category = None if category_raw in ("(none)", "None", "") else category_raw.strip("'\"")
        dry_run = str(current_meta.get("dry_run", "False")).lower() == "true"
        force = str(current_meta.get("force", "False")).lower() == "true"
        config_file = str(current_meta.get("config", ""))

        if not run_id:
            run_id = f"legacy-{hash((started_at, content_path)) & 0xFFFFFFFF:08x}"

        inputs = RunInputs(
            content_path=content_path,
            torrent_name=torrent_name,
            category=category,
            dry_run=dry_run,
            force=force,
            config_file=config_file,
        )

        runs.append(
            RunRecord(
                run_id=run_id,
                started_at=started_at,
                finished_at=started_at,
                status=status,
                inputs=inputs,
                media=media,
                log_lines=list(current_lines),
            )
        )
        current_lines = []
        in_run = False
        run_id = None
        started_at = None
        media = RunMedia()
        status = "unknown"

    for line in all_lines:
        if _SEPARATOR in line and "JellyShift run started" not in line:
            if in_run:
                finalize()
            in_run = True
            current_lines = [line]
            current_meta = {}
            media = RunMedia()
            status = "unknown"
            ts_match = _LOG_LINE.match(line.strip())
            started_at = ts_match.group(1) if ts_match else datetime.now().isoformat()
            continue

        if not in_run:
            continue

        current_lines.append(line)

        parsed = _LOG_LINE.match(line.strip())
        msg = parsed.group(4) if parsed else line

        if _RUN_START in msg:
            continue
        if match := _RUN_ID.search(msg):
            run_id = match.group(1)
            continue
        if msg.strip().startswith("config:"):
            current_meta["config"] = msg.split(":", 1)[1].strip()
        elif msg.strip().startswith("content_path:"):
            current_meta["content_path"] = msg.split(":", 1)[1].strip()
        elif msg.strip().startswith("torrent_name:"):
            current_meta["torrent_name"] = msg.split(":", 1)[1].strip()
        elif msg.strip().startswith("category:"):
            current_meta["category"] = msg.split(":", 1)[1].strip()
        elif msg.strip().startswith("dry_run:"):
            current_meta["dry_run"] = msg.split(":", 1)[1].strip()
        elif msg.strip().startswith("force:"):
            current_meta["force"] = msg.split(":", 1)[1].strip()
        elif match := _CLASSIFIED.search(msg):
            media.classified_as = match.group(1)
        elif match := _TMDB_MATCH.search(msg):
            media.tmdb_match = match.group(1).strip()
        elif match := _MOVED.search(msg):
            action = "dry-run" if "DRY-RUN" in msg else "moved"
            media.files_moved.append(
                FileMove(src=match.group(1).strip(), dst=match.group(2).strip(), action=action)
            )
        elif match := _SKIP.search(msg):
            media.files_skipped.append(match.group(1).strip())
        elif match := _REVIEW.search(msg):
            media.sent_to_review = True
            media.review_reason = match.group(3).strip()
        elif "JellyShift run finished successfully" in msg:
            status = "review" if media.sent_to_review else "success"
        elif "JellyShift run failed" in msg:
            status = "failed"

    if in_run:
        finalize()

    return runs
