from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProcessResult:
    exit_code: int
    stdout: str
    stderr: str


def find_jellyshift_binary(app_dir: Path) -> Path:
    venv_bin = app_dir / ".venv" / "bin" / "jellyshift"
    if venv_bin.exists():
        return venv_bin
    return Path(sys.executable).parent / "jellyshift"


def run_jellyshift(
    *,
    app_dir: Path,
    config_file: Path,
    content_path: Path,
    torrent_name: str | None = None,
    category: str | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> ProcessResult:
    binary = find_jellyshift_binary(app_dir)
    cmd = [
        str(binary),
        "--config",
        str(config_file),
        str(content_path),
    ]
    if torrent_name:
        cmd.extend(["--torrent-name", torrent_name])
    if category:
        cmd.extend(["--category", category])
    if dry_run:
        cmd.append("--dry-run")
    if force:
        cmd.append("--force")

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(app_dir),
    )
    return ProcessResult(
        exit_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def test_path_writable(path: Path) -> tuple[bool, str]:
    try:
        path = path.expanduser()
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".jellyshift-write-test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        return True, "Path is writable"
    except OSError as exc:
        return False, str(exc)
