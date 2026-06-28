from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jellyshift.config import Config


@dataclass
class AppState:
    config_path: Path
    config: Config

    @property
    def app_dir(self) -> Path:
        return self.config_path.resolve().parent

    @property
    def config_dir(self) -> Path:
        return self.app_dir
