from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote

VIDEO_EXTENSIONS = {
    ".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts"
}


@dataclass
class ReviewItem:
    id: str
    filename: str
    path: Path
    manifest_path: Path
    original_path: str
    moved_to: str
    reason: str
    torrent_name: str | None
    notes: str | None
    added_at: str
    size_bytes: int


def _item_id(path: Path) -> str:
    return quote(str(path.resolve()), safe="")


def _decode_id(item_id: str) -> Path:
    return Path(unquote(item_id))


def _is_under(base: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_manifest(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def list_items(review_dir: Path) -> list[ReviewItem]:
    review_dir = review_dir.resolve()
    if not review_dir.exists():
        return []

    items: list[ReviewItem] = []
    for manifest_path in review_dir.glob("*.manifest.json"):
        try:
            data = _load_manifest(manifest_path)
        except (OSError, json.JSONDecodeError):
            continue

        media_name = manifest_path.name[: -len(".manifest.json")]
        media_path = review_dir / media_name
        if not media_path.exists():
            continue

        mtime = datetime.fromtimestamp(
            media_path.stat().st_mtime, tz=timezone.utc
        ).astimezone().isoformat(timespec="seconds")

        items.append(
            ReviewItem(
                id=_item_id(media_path),
                filename=media_name,
                path=media_path,
                manifest_path=manifest_path,
                original_path=data.get("original_path", ""),
                moved_to=data.get("moved_to", str(media_path)),
                reason=data.get("reason", ""),
                torrent_name=data.get("torrent_name"),
                notes=data.get("notes"),
                added_at=mtime,
                size_bytes=media_path.stat().st_size if media_path.is_file() else 0,
            )
        )

    return sorted(items, key=lambda i: i.added_at, reverse=True)


def get_item(review_dir: Path, item_id: str) -> ReviewItem | None:
    path = _decode_id(item_id)
    if not _is_under(review_dir.resolve(), path):
        return None
    for item in list_items(review_dir):
        if item.id == item_id:
            return item
    return None


def update_notes(review_dir: Path, item_id: str, notes: str) -> ReviewItem | None:
    item = get_item(review_dir, item_id)
    if item is None:
        return None
    data = _load_manifest(item.manifest_path)
    data["notes"] = notes
    _save_manifest(item.manifest_path, data)
    return get_item(review_dir, item_id)


def rename_item(review_dir: Path, item_id: str, new_name: str) -> ReviewItem | None:
    item = get_item(review_dir, item_id)
    if not item or not new_name or new_name != Path(new_name).name:
        return None

    review_dir = review_dir.resolve()
    dest = review_dir / new_name
    if dest.exists():
        raise FileExistsError(f"{new_name} already exists in review")

    shutil.move(str(item.path), str(dest))
    new_manifest = review_dir / f"{new_name}.manifest.json"
    shutil.move(str(item.manifest_path), str(new_manifest))

    data = _load_manifest(new_manifest)
    data["moved_to"] = str(dest)
    _save_manifest(new_manifest, data)
    return get_item(review_dir, _item_id(dest))


def delete_item(review_dir: Path, item_id: str) -> bool:
    item = get_item(review_dir, item_id)
    if item is None:
        return False
    if item.path.is_file():
        item.path.unlink()
    elif item.path.is_dir():
        shutil.rmtree(item.path)
    if item.manifest_path.exists():
        item.manifest_path.unlink()
    return True
