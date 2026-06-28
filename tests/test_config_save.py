"""Tests for config save and hook settings."""
from __future__ import annotations

from pathlib import Path

from jellyshift.config import Config, HookConfig, WebConfig


def _minimal_yaml(**overrides: str) -> str:
    base = {
        "tmdb_api_key": "test-key",
        "movies_root": "/movies",
        "tv_root": "/tv",
        "review_dir": "/review",
    }
    base.update(overrides)
    lines = [f"{k}: {v}" for k, v in base.items()]
    return "\n".join(lines) + "\n"


class TestConfigExtended:
    def test_loads_hook_and_web_defaults(self, tmp_path: Path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text(_minimal_yaml())
        config = Config.load(config_path)
        assert config.hook.wsl_distro == "Ubuntu-22.04"
        assert config.web.port == 8765
        assert config.file_tmdb_api_key == "test-key"

    def test_save_round_trip(self, tmp_path: Path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text(_minimal_yaml())
        config = Config.load(config_path)
        config.hook = HookConfig(wsl_distro="Debian", wsl_user="alice")
        config.web = WebConfig(host="0.0.0.0", port=9000)
        config.category_map = {"movies": "movie"}
        config.save()

        reloaded = Config.load(config_path)
        assert reloaded.hook.wsl_distro == "Debian"
        assert reloaded.hook.wsl_user == "alice"
        assert reloaded.web.port == 9000
        assert reloaded.category_map["movies"] == "movie"

    def test_load_hook_from_scripts(self, tmp_path: Path):
        (tmp_path / "run-hook.cmd").write_text(
            'set "WSL_DISTRO=MyDistro"\n'
            'set "WSL_USER=bob"\n'
            'set "HOOK_SH=/home/bob/run-hook.sh"\n'
        )
        hook = Config.load_hook_from_scripts(tmp_path)
        assert hook["wsl_distro"] == "MyDistro"
        assert hook["wsl_user"] == "bob"
