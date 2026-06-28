"""Tests for hook script sync."""
from __future__ import annotations

from pathlib import Path

from jellyshift.config import HookConfig
from jellyshift.web.services.hook_sync import (
    patch_run_hook_cmd,
    sync_hook_scripts,
    write_hook_env,
)


class TestHookSync:
    def test_write_hook_env(self, tmp_path: Path):
        write_hook_env(tmp_path, "testuser")
        env = (tmp_path / "hook.env").read_text()
        assert 'JELLYSHIFT_DEFAULT_USER="testuser"' in env

    def test_patch_run_hook_cmd(self, tmp_path: Path):
        cmd = tmp_path / "run-hook.cmd"
        cmd.write_text(
            'set "WSL_DISTRO=OldDistro"\n'
            'set "WSL_USER=olduser"\n'
            'set "HOOK_SH=/old/path"\n'
        )
        patch_run_hook_cmd(tmp_path, "NewDistro", "newuser", "/home/newuser/hook.sh")
        text = cmd.read_text()
        assert 'WSL_DISTRO=NewDistro' in text
        assert 'WSL_USER=newuser' in text
        assert 'HOOK_SH=/home/newuser/hook.sh' in text

    def test_sync_hook_scripts(self, tmp_path: Path):
        (tmp_path / "run-hook.cmd").write_text(
            'set "WSL_DISTRO=Old"\nset "WSL_USER=old"\nset "HOOK_SH=/old"\n'
        )
        sh = tmp_path / "run-hook.sh"
        sh.write_text('APP_DIR="."\nWSL_USER="${JELLYSHIFT_USER:-sharath}"\n')
        sync_hook_scripts(
            tmp_path,
            HookConfig(wsl_distro="Ubuntu", wsl_user="dev", hook_sh="/home/dev/hook.sh"),
        )
        assert (tmp_path / "hook.env").exists()
        assert "Ubuntu" in (tmp_path / "run-hook.cmd").read_text()
