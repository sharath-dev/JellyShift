from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_RUN_START = re.compile(r"JellyShift run started")
_CLASSIFIED = re.compile(r"Classified as: (\w+)")
_TMDB_MATCH = re.compile(r"TMDB matched (?:series|movie): (.+)")
_MOVED = re.compile(r"(?:MOVED|DRY-RUN)\s+(.+?)\s+→\s+(.+)")
_SKIP = re.compile(r"SKIP \(already exists\): (.+)")
_REVIEW = re.compile(r"REVIEW\s+(.+?)\s+→\s+(.+?) \((.+)\)")
_RUN_SUCCESS = re.compile(r"JellyShift run finished successfully")
_RUN_FAILED = re.compile(r"JellyShift run failed")


@dataclass
class FileMove:
    src: str
    dst: str
    action: str = "moved"


@dataclass
class RunInputs:
    content_path: str
    torrent_name: str
    category: str | None
    dry_run: bool
    force: bool
    config_file: str


@dataclass
class RunMedia:
    classified_as: str | None = None
    tmdb_match: str | None = None
    files_moved: list[FileMove] = field(default_factory=list)
    files_skipped: list[str] = field(default_factory=list)
    sent_to_review: bool = False
    review_reason: str | None = None


@dataclass
class RunRecord:
    run_id: str
    started_at: str
    finished_at: str | None = None
    status: str = "running"
    inputs: RunInputs | None = None
    media: RunMedia = field(default_factory=RunMedia)
    error: str | None = None
    log_lines: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.status == "failed":
            return self.error or "failed"
        if self.media.sent_to_review:
            return "sent to review"
        moved = len(self.media.files_moved)
        if moved:
            return f"{moved} moved"
        skipped = len(self.media.files_skipped)
        if skipped:
            return f"{skipped} skipped"
        if self.status == "success":
            return "completed"
        return self.status


class _RunLogHandler(logging.Handler):
    def __init__(self, recorder: RunRecorder) -> None:
        super().__init__()
        self._recorder = recorder

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._recorder._handle_log_line(msg)
        except Exception:
            self.handleError(record)


class RunRecorder:
    """Collect structured metadata for a single CLI invocation."""

    def __init__(self, *, runs_dir: Path) -> None:
        self.run_id = str(uuid.uuid4())
        self.runs_dir = runs_dir
        self.record = RunRecord(
            run_id=self.run_id,
            started_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        )
        self._handler: _RunLogHandler | None = None
        self._file_format = logging.Formatter(
            "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def attach(self) -> None:
        self._handler = _RunLogHandler(self)
        self._handler.setFormatter(self._file_format)
        root = logging.getLogger("jellyshift")
        root.addHandler(self._handler)

    def detach(self) -> None:
        if self._handler is not None:
            logging.getLogger("jellyshift").removeHandler(self._handler)
            self._handler = None

    def set_inputs(
        self,
        *,
        content_path: Path,
        torrent_name: str,
        category: str | None,
        config_file: Path,
        dry_run: bool,
        force: bool,
    ) -> None:
        self.record.inputs = RunInputs(
            content_path=str(content_path),
            torrent_name=torrent_name,
            category=category,
            dry_run=dry_run,
            force=force,
            config_file=str(config_file),
        )

    def set_classified(self, media_type: str) -> None:
        self.record.media.classified_as = media_type

    def finish(self, *, status: str, error: str | None = None) -> None:
        self.record.status = status
        self.record.error = error
        self.record.finished_at = datetime.now(timezone.utc).astimezone().isoformat(
            timespec="seconds"
        )
        self._write_index()

    def _handle_log_line(self, line: str) -> None:
        self.record.log_lines.append(line)

        if match := _CLASSIFIED.search(line):
            self.record.media.classified_as = match.group(1)
        elif match := _TMDB_MATCH.search(line):
            self.record.media.tmdb_match = match.group(1).strip()
        elif match := _MOVED.search(line):
            action = "dry-run" if line.strip().find("DRY-RUN") >= 0 else "moved"
            self.record.media.files_moved.append(
                FileMove(src=match.group(1).strip(), dst=match.group(2).strip(), action=action)
            )
        elif match := _SKIP.search(line):
            self.record.media.files_skipped.append(match.group(1).strip())
        elif match := _REVIEW.search(line):
            self.record.media.sent_to_review = True
            self.record.media.review_reason = match.group(3).strip()
        elif _RUN_SUCCESS.search(line):
            if self.record.media.sent_to_review:
                self.record.status = "review"
            else:
                self.record.status = "success"
        elif _RUN_FAILED.search(line):
            self.record.status = "failed"

    def _write_index(self) -> None:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        path = self.runs_dir / f"{self.run_id}.json"
        payload = self._to_json_dict()
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _to_json_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "run_id": self.record.run_id,
            "started_at": self.record.started_at,
            "finished_at": self.record.finished_at,
            "status": self.record.status,
            "error": self.record.error,
        }
        if self.record.inputs:
            data["inputs"] = asdict(self.record.inputs)
        data["media"] = {
            "classified_as": self.record.media.classified_as,
            "tmdb_match": self.record.media.tmdb_match,
            "files_moved": [asdict(f) for f in self.record.media.files_moved],
            "files_skipped": list(self.record.media.files_skipped),
            "sent_to_review": self.record.media.sent_to_review,
            "review_reason": self.record.media.review_reason,
        }
        data["log_lines"] = self.record.log_lines[-500:]
        return data


def load_run_record(path: Path) -> RunRecord:
    raw = json.loads(path.read_text(encoding="utf-8"))
    media_raw = raw.get("media") or {}
    inputs_raw = raw.get("inputs")
    inputs = RunInputs(**inputs_raw) if inputs_raw else None
    files_moved = [
        FileMove(**item) for item in media_raw.get("files_moved", [])
    ]
    media = RunMedia(
        classified_as=media_raw.get("classified_as"),
        tmdb_match=media_raw.get("tmdb_match"),
        files_moved=files_moved,
        files_skipped=list(media_raw.get("files_skipped", [])),
        sent_to_review=bool(media_raw.get("sent_to_review")),
        review_reason=media_raw.get("review_reason"),
    )
    return RunRecord(
        run_id=raw["run_id"],
        started_at=raw["started_at"],
        finished_at=raw.get("finished_at"),
        status=raw.get("status", "unknown"),
        inputs=inputs,
        media=media,
        error=raw.get("error"),
        log_lines=list(raw.get("log_lines", [])),
    )
