"""Tests for Web UI systemd service helpers."""
from __future__ import annotations

from pathlib import Path

from jellyshift.web_service import SERVICE_NAME, render_unit_file, unit_file_path


class TestWebService:
    def test_render_unit_file(self, tmp_path: Path):
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        config = app_dir / "config.yaml"
        config.write_text("x: 1\n")
        binary = app_dir / ".venv" / "bin" / "jellyshift"
        binary.parent.mkdir(parents=True)
        binary.touch()

        unit = render_unit_file(app_dir=app_dir, config_file=config, binary=binary)
        assert "Description=JellyShift Web UI" in unit
        assert f"ExecStart={binary} serve --config {config.resolve()}" in unit
        assert "Restart=on-failure" in unit

    def test_unit_file_path(self):
        assert unit_file_path().name == SERVICE_NAME
