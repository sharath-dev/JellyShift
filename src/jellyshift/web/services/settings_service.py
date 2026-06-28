from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from jellyshift.config import Config, HookConfig, WebConfig
from jellyshift.web.services.hook_sync import sync_hook_scripts


def mask_api_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 4:
        return "****"
    return f"****{key[-4:]}"


@dataclass
class SettingsView:
    tmdb_api_key: str
    tmdb_api_key_masked: str
    tmdb_api_key_from_env: bool
    movies_root: str
    tv_root: str
    review_dir: str
    category_map: dict[str, str]
    tmdb_similarity_threshold: float
    include_episode_title: bool
    dry_run: bool
    log_level: str
    log_file: str | None
    log_max_bytes: int
    log_backup_count: int
    hook: HookConfig
    web: WebConfig
    has_run_hook_cmd: bool

    @classmethod
    def from_config(cls, config: Config) -> SettingsView:
        log_file_str = str(config.log_file) if config.log_file else None
        from_env = bool(os.environ.get("TMDB_API_KEY"))
        return cls(
            tmdb_api_key=config.file_tmdb_api_key or config.tmdb_api_key,
            tmdb_api_key_masked=mask_api_key(config.tmdb_api_key),
            tmdb_api_key_from_env=from_env,
            movies_root=str(config.movies_root),
            tv_root=str(config.tv_root),
            review_dir=str(config.review_dir),
            category_map=dict(config.category_map),
            tmdb_similarity_threshold=config.tmdb_similarity_threshold,
            include_episode_title=config.include_episode_title,
            dry_run=config.dry_run,
            log_level=config.log_level,
            log_file=log_file_str,
            log_max_bytes=config.log_max_bytes,
            log_backup_count=config.log_backup_count,
            hook=config.hook,
            web=config.web,
            has_run_hook_cmd=(config.app_dir / "run-hook.cmd").exists(),
        )

    def to_dict(self, *, include_key: bool = False) -> dict[str, Any]:
        data = asdict(self)
        if not include_key:
            data.pop("tmdb_api_key", None)
        data["hook"] = asdict(self.hook)
        data["web"] = asdict(self.web)
        return data


def load_settings(config_path: Path) -> SettingsView:
    config = Config.load(config_path)
    return SettingsView.from_config(config)


def save_settings(config_path: Path, payload: dict[str, Any]) -> SettingsView:
    config = Config.load(config_path)

    if "tmdb_api_key" in payload and payload["tmdb_api_key"]:
        config.file_tmdb_api_key = str(payload["tmdb_api_key"])
        if not os.environ.get("TMDB_API_KEY"):
            config.tmdb_api_key = config.file_tmdb_api_key

    config.movies_root = Path(payload["movies_root"])
    config.tv_root = Path(payload["tv_root"])
    config.review_dir = Path(payload["review_dir"])
    config.category_map = {
        str(k).lower(): str(v).lower()
        for k, v in (payload.get("category_map") or {}).items()
    }
    config.tmdb_similarity_threshold = float(payload.get("tmdb_similarity_threshold", 0.6))
    config.include_episode_title = bool(payload.get("include_episode_title", True))
    config.dry_run = bool(payload.get("dry_run", False))
    config.log_level = str(payload.get("log_level", "INFO")).upper()

    log_file_raw = payload.get("log_file")
    if log_file_raw in (None, "", "null"):
        config.log_file = None
    else:
        from jellyshift.log_config import resolve_log_file

        config.log_file = resolve_log_file(log_file_raw, base_dir=config_path.parent)

    config.log_max_bytes = int(payload.get("log_max_bytes", config.log_max_bytes))
    config.log_backup_count = int(payload.get("log_backup_count", config.log_backup_count))

    hook_raw = payload.get("hook") or {}
    config.hook = HookConfig(
        wsl_distro=str(hook_raw.get("wsl_distro", config.hook.wsl_distro)),
        wsl_user=str(hook_raw.get("wsl_user", config.hook.wsl_user)),
        hook_sh=hook_raw.get("hook_sh") or None,
    )

    web_raw = payload.get("web") or {}
    config.web = WebConfig(
        host=str(web_raw.get("host", config.web.host)),
        port=int(web_raw.get("port", config.web.port)),
    )

    config.save(config_path)
    sync_hook_scripts(config_path.parent, config.hook)
    return SettingsView.from_config(Config.load(config_path))
