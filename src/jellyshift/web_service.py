"""Install and manage JellyShift Web UI as a persistent systemd user service."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

SERVICE_NAME = "jellyshift-web.service"


def find_jellyshift_binary(app_dir: Path) -> Path:
    venv_bin = app_dir / ".venv" / "bin" / "jellyshift"
    if venv_bin.exists():
        return venv_bin.resolve()
    which = shutil.which("jellyshift")
    if which:
        return Path(which).resolve()
    return Path(sys.executable).parent / "jellyshift"


def unit_file_path() -> Path:
    return Path.home() / ".config" / "systemd" / "user" / SERVICE_NAME


def render_unit_file(*, app_dir: Path, config_file: Path, binary: Path | None = None) -> str:
    binary = binary or find_jellyshift_binary(app_dir)
    config = config_file.resolve()
    workdir = app_dir.resolve()
    return f"""[Unit]
Description=JellyShift Web UI
After=network.target

[Service]
Type=simple
WorkingDirectory={workdir}
ExecStart={binary} serve --config {config}
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
"""


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=check)


def systemd_available() -> bool:
    if not shutil.which("systemctl"):
        return False
    try:
        result = _run(["systemctl", "--user", "--version"], check=False)
        return result.returncode == 0
    except OSError:
        return False


def install_service(*, app_dir: Path, config_file: Path) -> None:
    if not systemd_available():
        raise RuntimeError(
            "systemd user services are not available. "
            "On WSL, enable systemd in /etc/wsl.conf:\n"
            "  [boot]\n"
            "  systemd=true\n"
            "Then restart WSL: wsl --shutdown"
        )

    unit_path = unit_file_path()
    unit_path.parent.mkdir(parents=True, exist_ok=True)
    unit_path.write_text(
        render_unit_file(app_dir=app_dir, config_file=config_file),
        encoding="utf-8",
    )

    user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    if user:
        _run(["loginctl", "enable-linger", user], check=False)

    _run(["systemctl", "--user", "daemon-reload"])
    _run(["systemctl", "--user", "enable", "--now", SERVICE_NAME])


def uninstall_service() -> None:
    if systemd_available():
        _run(["systemctl", "--user", "disable", "--now", SERVICE_NAME], check=False)
        _run(["systemctl", "--user", "daemon-reload"], check=False)
    unit_path = unit_file_path()
    if unit_path.exists():
        unit_path.unlink()


def service_status() -> str:
    if not systemd_available():
        return "systemd user services not available"
    result = _run(
        ["systemctl", "--user", "status", SERVICE_NAME, "--no-pager"],
        check=False,
    )
    return result.stdout + result.stderr


def service_action(action: str) -> None:
    _run(["systemctl", "--user", action, SERVICE_NAME])
