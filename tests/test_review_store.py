"""Tests for review store."""
from __future__ import annotations

import json
from pathlib import Path

from jellyshift.web.services import review_store


def _make_review_item(review_dir: Path, name: str = "orphan.mkv") -> None:
    review_dir.mkdir(parents=True, exist_ok=True)
    media = review_dir / name
    media.write_bytes(b"video")
    manifest = review_dir / f"{name}.manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "original_path": f"/downloads/{name}",
                "moved_to": str(review_dir / name),
                "reason": "test reason",
                "torrent_name": name,
            }
        )
    )


class TestReviewStore:
    def test_list_and_get(self, tmp_path: Path):
        review_dir = tmp_path / "review"
        _make_review_item(review_dir)
        items = review_store.list_items(review_dir)
        assert len(items) == 1
        item = review_store.get_item(review_dir, items[0].id)
        assert item is not None
        assert item.reason == "test reason"

    def test_update_notes(self, tmp_path: Path):
        review_dir = tmp_path / "review"
        _make_review_item(review_dir)
        item = review_store.list_items(review_dir)[0]
        updated = review_store.update_notes(review_dir, item.id, "my notes")
        assert updated is not None
        assert updated.notes == "my notes"

    def test_rename(self, tmp_path: Path):
        review_dir = tmp_path / "review"
        _make_review_item(review_dir)
        item = review_store.list_items(review_dir)[0]
        renamed = review_store.rename_item(review_dir, item.id, "fixed.S01E01.mkv")
        assert renamed is not None
        assert renamed.filename == "fixed.S01E01.mkv"
        assert (review_dir / "fixed.S01E01.mkv.manifest.json").exists()

    def test_delete(self, tmp_path: Path):
        review_dir = tmp_path / "review"
        _make_review_item(review_dir)
        item = review_store.list_items(review_dir)[0]
        assert review_store.delete_item(review_dir, item.id) is True
        assert review_store.list_items(review_dir) == []
