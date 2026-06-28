"""Install and manage JellyShift Web UI as a persistent background service."""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

SERVICE_NAME = "jellyshift-web.service"
MODE_FILE = "webui.mode"
PID_FILE = "webui.pid"
LOG_FILE = "webui.log"


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


def _logs_dir(app_dir: Path) -> Path:
    d = app_dir / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _mode_path(app_dir: Path) -> Path:
    return _logs_dir(app_dir) / MODE_FILE


def _pid_path(app_dir: Path) -> Path:
    return _logs_dir(app_dir) / PID_FILE


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


def _systemd_unavailable_message() -> str:
    return (
        "systemd user services are not available (D-Bus not running).\n"
        "On WSL, enable systemd in /etc/wsl.conf:\n"
        "  [boot]\n"
        "  systemd=true\n"
        "Then restart WSL from Windows: wsl --shutdown\n"
        "Re-open WSL and run: jellyshift service install --config config.yaml\n"
        "\n"
        "Or use background mode without systemd:\n"
        "  jellyshift service install --config config.yaml --background"
    )


def systemd_user_bus_available() -> bool:
    """Return True only when systemctl can talk to the user systemd instance."""
    if not shutil.which("systemctl"):
        return False
    try:
        result = _run(["systemctl", "--user", "is-system-running"], check=False)
        if result.returncode == 0:
            return True
        # "degraded" or "running" may appear; treat connect errors as unavailable.
        combined = (result.stdout + result.stderr).lower()
        if "failed to connect to bus" in combined:
            return False
        # Fallback: any non-connection failure means systemd responded.
        return "failed to connect" not in combined and result.returncode in (0, 1)
    except OSError:
        return False


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _stop_nohup(app_dir: Path) -> None:
    pid_path = _pid_path(app_dir)
    if not pid_path.exists():
        return
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        pid_path.unlink(missing_ok=True)
        return
    if _pid_alive(pid):
        try:
            os.kill(pid, signal.SIGTERM)
            for _ in range(20):
                if not _pid_alive(pid):
                    break
                time.sleep(0.1)
            if _pid_alive(pid):
                os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    pid_path.unlink(missing_ok=True)


def _install_nohup(*, app_dir: Path, config_file: Path) -> None:
    _stop_nohup(app_dir)
    logs = _logs_dir(app_dir)
    log_file = logs / LOG_FILE
    binary = find_jellyshift_binary(app_dir)
    config = config_file.resolve()

    with open(log_file, "a", encoding="utf-8") as log:
        proc = subprocess.Popen(
            [str(binary), "serve", "--config", str(config)],
            stdout=log,
            stderr=subprocess.STDOUT,
            cwd=str(app_dir.resolve()),
            start_new_session=True,
        )
    _pid_path(app_dir).write_text(str(proc.pid), encoding="utf-8")
    _mode_path(app_dir).write_text("nohup", encoding="utf-8")


def _install_systemd(*, app_dir: Path, config_file: Path) -> None:
    unit_path = unit_file_path()
    unit_path.parent.mkdir(parents=True, exist_ok=True)
    unit_path.write_text(
        render_unit_file(app_dir=app_dir, config_file=config_file),
        encoding="utf-8",
    )

    user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    if user and shutil.which("loginctl"):
        _run(["loginctl", "enable-linger", user], check=False)

    try:
        _run(["systemctl", "--user", "daemon-reload"])
        _run(["systemctl", "--user", "enable", "--now", SERVICE_NAME])
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(_systemd_unavailable_message()) from exc

    _mode_path(app_dir).write_text("systemd", encoding="utf-8")
    _stop_nohup(app_dir)


def install_service(
    *,
    app_dir: Path,
    config_file: Path,
    background: bool = False,
) -> str:
    """Install Web UI service. Returns 'systemd' or 'nohup'."""
    if background:
        _install_nohup(app_dir=app_dir, config_file=config_file)
        return "nohup"

    if systemd_user_bus_available():
        _install_systemd(app_dir=app_dir, config_file=config_file)
        return "systemd"

    raise RuntimeError(_systemd_unavailable_message())


def uninstall_service(*, app_dir: Path | None = None) -> None:
    mode = None
    if app_dir is not None:
        mode_path = _mode_path(app_dir)
        if mode_path.exists():
            mode = mode_path.read_text(encoding="utf-8").strip()
            mode_path.unlink(missing_ok=True)

    if mode == "nohup" and app_dir is not None:
        _stop_nohup(app_dir)
    elif systemd_user_bus_available():
        _run(["systemctl", "--user", "disable", "--now", SERVICE_NAME], check=False)
        _run(["systemctl", "--user", "daemon-reload"], check=False)

    if app_dir is not None:
        _stop_nohup(app_dir)

    unit_path = unit_file_path()
    if unit_path.exists():
        unit_path.unlink()


def service_status(*, app_dir: Path | None = None) -> str:
    if app_dir is not None:
        mode_path = _mode_path(app_dir)
        if mode_path.exists() and mode_path.read_text(encoding="utf-8").strip() == "nohup":
            pid_path = _pid_path(app_dir)
            if not pid_path.exists():
                return "Background Web UI is not running (no PID file)."
            pid = int(pid_path.read_text(encoding="utf-8").strip())
            if _pid_alive(pid):
                log_file = _logs_dir(app_dir) / LOG_FILE
                return f"Background Web UI running (PID {pid}). Logs: {log_file}"
            return f"Background Web UI not running (stale PID {pid})."

    if not systemd_user_bus_available():
        return _systemd_unavailable_message()

    result = _run(
        ["systemctl", "--user", "status", SERVICE_NAME, "--no-pager"],
        check=False,
    )
    return result.stdout + result.stderr


def service_action(action: str) -> None:
    if not systemd_user_bus_available():
        raise RuntimeError(_systemd_unavailable_message())
    try:
        _run(["systemctl", "--user", action, SERVICE_NAME])
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(exc.stderr or str(exc)) from exc
