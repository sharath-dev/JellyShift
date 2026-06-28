"""Tests for Web UI service helpers."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from jellyshift.web_service import (
    SERVICE_NAME,
    _pid_alive,
    _stop_nohup,
    install_service,
    render_unit_file,
    unit_file_path,
)


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

    def test_install_nohup_background(self, tmp_path: Path):
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        config = app_dir / "config.yaml"
        config.write_text("x: 1\n")
        binary = app_dir / ".venv" / "bin" / "jellyshift"
        binary.parent.mkdir(parents=True)
        binary.write_text("#!/bin/sh\nsleep 60\n")
        binary.chmod(0o755)

        mode = install_service(app_dir=app_dir, config_file=config, background=True)
        assert mode == "nohup"
        pid_file = app_dir / "logs" / "webui.pid"
        mode_file = app_dir / "logs" / "webui.mode"
        assert pid_file.exists()
        assert mode_file.read_text().strip() == "nohup"
        pid = int(pid_file.read_text())
        assert _pid_alive(pid)
        _stop_nohup(app_dir)
        assert not pid_file.exists()

    def test_install_systemd_when_available(self, tmp_path: Path):
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        config = app_dir / "config.yaml"
        config.write_text("x: 1\n")

        with patch("jellyshift.web_service.systemd_user_bus_available", return_value=True):
            with patch("jellyshift.web_service._install_systemd") as mock_systemd:
                mode = install_service(app_dir=app_dir, config_file=config)
        assert mode == "systemd"
        mock_systemd.assert_called_once()
