from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .log_config import DEFAULT_LOG_RELATIVE, resolve_log_file


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

    @classmethod
    def load(cls, path: Path) -> Config:
        with open(path) as fh:
            raw = yaml.safe_load(fh)

        api_key = os.environ.get("TMDB_API_KEY") or raw.get("tmdb_api_key", "")
        config_dir = path.resolve().parent

        if "log_file" in raw:
            log_file = resolve_log_file(raw.get("log_file"), base_dir=config_dir)
        else:
            log_file = resolve_log_file(None, base_dir=config_dir)

        return cls(
            tmdb_api_key=api_key,
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
        )
