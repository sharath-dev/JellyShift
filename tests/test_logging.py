"""Tests for logging configuration."""
from __future__ import annotations

import logging
from pathlib import Path

from jellyshift.config import Config
from jellyshift.log_config import DEFAULT_LOG_RELATIVE, FALLBACK_LOG, resolve_log_file, setup_logging


class TestResolveLogFile:
    def test_default_relative_to_app_dir(self, tmp_path: Path):
        path = resolve_log_file(None, base_dir=tmp_path)
        assert path == (tmp_path / DEFAULT_LOG_RELATIVE).resolve()

    def test_null_disables(self):
        assert resolve_log_file("null") is None
        assert resolve_log_file("") is None

    def test_relative_path_uses_base_dir(self, tmp_path: Path):
        path = resolve_log_file("logs/custom.log", base_dir=tmp_path)
        assert path == (tmp_path / "logs" / "custom.log").resolve()

    def test_expands_tilde(self):
        path = resolve_log_file("~/test-jellyshift.log")
        assert path == Path.home() / "test-jellyshift.log"


class TestConfigLogDefaults:
    def test_default_log_file_next_to_config(self, tmp_path: Path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "tmdb_api_key: x\n"
            "movies_root: /m\n"
            "tv_root: /t\n"
            "review_dir: /r\n"
        )
        config = Config.load(config_path)
        assert config.log_file == (tmp_path / "logs" / "jellyshift.log").resolve()


class TestSetupLogging:
    def test_creates_file_handler(self, tmp_path: Path):
        log_file = tmp_path / "test.log"
        logger = setup_logging(level="DEBUG", log_file=log_file, verbose=False)
        logger.info("test message")
        for handler in logger.handlers:
            handler.flush()
        assert log_file.exists()
        assert "test message" in log_file.read_text()

    def test_falls_back_when_log_dir_not_writable(self, tmp_path: Path, monkeypatch):
        blocked = tmp_path / "blocked" / "jellyshift.log"
        monkeypatch.setattr(
            "jellyshift.log_config._open_file_handler",
            lambda path, **kw: None if path == blocked else logging.handlers.RotatingFileHandler(
                FALLBACK_LOG,
                maxBytes=kw["max_bytes"],
                backupCount=kw["backup_count"],
                encoding="utf-8",
            ),
        )
        logger = setup_logging(level="INFO", log_file=blocked, verbose=False)
        # Should still have console handler at minimum
        assert any(isinstance(h, logging.StreamHandler) for h in logger.handlers)

    def test_verbose_sets_debug(self, tmp_path: Path):
        log_file = tmp_path / "verbose.log"
        logger = setup_logging(level="INFO", log_file=log_file, verbose=True)
        assert logger.level == logging.DEBUG

    def test_child_logger_propagates(self, tmp_path: Path):
        log_file = tmp_path / "child.log"
        setup_logging(level="DEBUG", log_file=log_file, verbose=False)
        child = logging.getLogger("jellyshift.naming")
        child.debug("child debug line")
        for handler in logging.getLogger("jellyshift").handlers:
            handler.flush()
        assert "child debug line" in log_file.read_text()
