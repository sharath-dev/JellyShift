from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

log = logging.getLogger(__name__)


def send_to_review(
    content_path: Path,
    review_dir: Path,
    reason: str,
    *,
    torrent_name: str | None = None,
    dry_run: bool = False,
) -> None:
    """Move content_path into review_dir and write a JSON sidecar manifest."""
    if dry_run:
        log.info("DRY-RUN  would move %s to review — %s", content_path, reason)
        return

    review_dir.mkdir(parents=True, exist_ok=True)
    dest = review_dir / content_path.name
    if dest.exists():
        suffix_counter = 1
        while (
            review_dir / f"{content_path.stem}_{suffix_counter}{content_path.suffix}"
        ).exists():
            suffix_counter += 1
        dest = review_dir / f"{content_path.stem}_{suffix_counter}{content_path.suffix}"

    shutil.move(str(content_path), str(dest))

    manifest = {
        "original_path": str(content_path),
        "moved_to": str(dest),
        "reason": reason,
    }
    if torrent_name:
        manifest["torrent_name"] = torrent_name

    manifest_path = review_dir / f"{dest.name}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    log.warning("REVIEW   %s  →  %s  (%s)", content_path, dest, reason)
