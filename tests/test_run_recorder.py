"""Tests for run recorder."""
from __future__ import annotations

import json
from pathlib import Path

from jellyshift.run_recorder import RunRecorder, load_run_record


class TestRunRecorder:
    def test_writes_json_index(self, tmp_path: Path):
        runs_dir = tmp_path / "runs"
        recorder = RunRecorder(runs_dir=runs_dir)
        recorder.set_inputs(
            content_path=Path("/downloads/test.mkv"),
            torrent_name="test.mkv",
            category="tv",
            config_file=Path("/app/config.yaml"),
            dry_run=False,
            force=False,
        )
        recorder.set_classified("tv")
        recorder.finish(status="success")

        path = runs_dir / f"{recorder.run_id}.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["status"] == "success"
        assert data["inputs"]["torrent_name"] == "test.mkv"

    def test_load_run_record(self, tmp_path: Path):
        runs_dir = tmp_path / "runs"
        recorder = RunRecorder(runs_dir=runs_dir)
        recorder.finish(status="failed", error="boom")
        record = load_run_record(runs_dir / f"{recorder.run_id}.json")
        assert record.status == "failed"
        assert record.error == "boom"
