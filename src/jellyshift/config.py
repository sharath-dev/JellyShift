from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .log_config import DEFAULT_LOG_RELATIVE, resolve_log_file


@dataclass
class HookConfig:
    wsl_distro: str = "Ubuntu-22.04"
    wsl_user: str = "sharath"
    hook_sh: str | None = None


@dataclass
class WebConfig:
    host: str = "127.0.0.1"
    port: int = 8765


@dataclass
class Config:
    tmdb_api_key: str
    movies_root: Path
    tv_root: Path
    review_dir: Path
    category_map: dict[str, str] = field(default_factory=dict)
    tmdb_similarity_threshold: float = 0.6
    include_episode_title: bool = True
    dry_run: bool = False
    log_level: str = "INFO"
    log_file: Path | None = None
    log_max_bytes: int = 5 * 1024 * 1024
    log_backup_count: int = 3
    hook: HookConfig = field(default_factory=HookConfig)
    web: WebConfig = field(default_factory=WebConfig)
    file_tmdb_api_key: str = ""
    config_path: Path | None = None

    @property
    def app_dir(self) -> Path:
        if self.config_path is not None:
            return self.config_path.resolve().parent
        return Path.cwd()

    @classmethod
    def load(cls, path: Path) -> Config:
        with open(path) as fh:
            raw = yaml.safe_load(fh) or {}

        file_api_key = str(raw.get("tmdb_api_key", ""))
        api_key = os.environ.get("TMDB_API_KEY") or file_api_key
        config_dir = path.resolve().parent

        if "log_file" in raw:
            log_file = resolve_log_file(raw.get("log_file"), base_dir=config_dir)
        else:
            log_file = resolve_log_file(None, base_dir=config_dir)

        hook_raw = raw.get("hook") or {}
        if not hook_raw:
            hook_raw = cls.load_hook_from_scripts(config_dir)

        web_raw = raw.get("web") or {}

        return cls(
            tmdb_api_key=api_key,
            file_tmdb_api_key=file_api_key,
            movies_root=Path(raw["movies_root"]),
            tv_root=Path(raw["tv_root"]),
            review_dir=Path(raw["review_dir"]),
            category_map={
                k.lower(): v.lower() for k, v in raw.get("category_map", {}).items()
            },
            tmdb_similarity_threshold=float(
                raw.get("tmdb_similarity_threshold", 0.6)
            ),
            include_episode_title=bool(raw.get("include_episode_title", True)),
            dry_run=bool(raw.get("dry_run", False)),
            log_level=str(raw.get("log_level", "INFO")).upper(),
            log_file=log_file,
            log_max_bytes=int(raw.get("log_max_bytes", 5 * 1024 * 1024)),
            log_backup_count=int(raw.get("log_backup_count", 3)),
            hook=HookConfig(
                wsl_distro=str(hook_raw.get("wsl_distro", "Ubuntu-22.04")),
                wsl_user=str(hook_raw.get("wsl_user", "sharath")),
                hook_sh=hook_raw.get("hook_sh"),
            ),
            web=WebConfig(
                host=str(web_raw.get("host", "127.0.0.1")),
                port=int(web_raw.get("port", 8765)),
            ),
            config_path=path,
        )

    @classmethod
    def load_hook_from_scripts(cls, app_dir: Path) -> dict[str, str | None]:
        """Read hook vars from run-hook.cmd when config has no hook: block."""
        cmd_path = app_dir / "run-hook.cmd"
        if not cmd_path.exists():
            return {}

        text = cmd_path.read_text(encoding="utf-8", errors="replace")
        result: dict[str, str | None] = {}

        for key, pattern in (
            ("wsl_distro", r'set\s+"WSL_DISTRO=([^"]*)"'),
            ("wsl_user", r'set\s+"WSL_USER=([^"]*)"'),
            ("hook_sh", r'set\s+"HOOK_SH=([^"]*)"'),
        ):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result[key] = match.group(1)

        return result

    def to_save_dict(self) -> dict[str, Any]:
        log_file_value: str | None
        if self.config_path is not None:
            default_log = (self.config_path.parent / DEFAULT_LOG_RELATIVE).resolve()
            if self.log_file is None:
                log_file_value = None
            elif self.log_file.resolve() == default_log:
                log_file_value = str(DEFAULT_LOG_RELATIVE).replace("\\", "/")
            else:
                log_file_value = str(self.log_file)
        else:
            log_file_value = str(self.log_file) if self.log_file else None

        hook_sh = self.hook.hook_sh
        if hook_sh is None:
            hook_sh_value = None
        else:
            hook_sh_value = hook_sh

        return {
            "tmdb_api_key": self.file_tmdb_api_key or self.tmdb_api_key,
            "movies_root": str(self.movies_root),
            "tv_root": str(self.tv_root),
            "review_dir": str(self.review_dir),
            "category_map": dict(self.category_map),
            "tmdb_similarity_threshold": self.tmdb_similarity_threshold,
            "include_episode_title": self.include_episode_title,
            "dry_run": self.dry_run,
            "log_level": self.log_level,
            "log_file": log_file_value,
            "log_max_bytes": self.log_max_bytes,
            "log_backup_count": self.log_backup_count,
            "hook": {
                "wsl_distro": self.hook.wsl_distro,
                "wsl_user": self.hook.wsl_user,
                "hook_sh": hook_sh_value,
            },
            "web": {
                "host": self.web.host,
                "port": self.web.port,
            },
        }

    def save(self, path: Path | None = None) -> None:
        target = path or self.config_path
        if target is None:
            raise ValueError("No config path specified for save")

        data = self.to_save_dict()
        try:
            from ruamel.yaml import YAML

            yaml_handler = YAML()
            yaml_handler.default_flow_style = False
            yaml_handler.indent(mapping=2, sequence=4, offset=2)

            if target.exists():
                with open(target) as fh:
                    existing = yaml_handler.load(fh) or {}
            else:
                existing = {}

            for key, value in data.items():
                existing[key] = value

            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w") as fh:
                yaml_handler.dump(existing, fh)
        except ImportError:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w") as fh:
                yaml.safe_dump(data, fh, default_flow_style=False, sort_keys=False)

        self.config_path = target
