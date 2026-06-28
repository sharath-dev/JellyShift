"""Tests for Web API."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")

from jellyshift.web.app import create_app


def _write_config(tmp_path: Path) -> Path:
    review_dir = tmp_path / "review"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "tmdb_api_key: test-key\n"
        f"movies_root: {tmp_path / 'movies'}\n"
        f"tv_root: {tmp_path / 'tv'}\n"
        f"review_dir: {review_dir}\n"
        "category_map:\n  movies: movie\n"
    )
    return config_path


@pytest.fixture
def client(tmp_path: Path):
    config_path = _write_config(tmp_path)
    app = create_app(config_path)
    return TestClient(app)


class TestWebAPI:
    def test_health(self, client: TestClient):
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

    def test_invocations_list(self, client: TestClient):
        res = client.get("/api/invocations")
        assert res.status_code == 200
        assert "items" in res.json()

    def test_settings_get(self, client: TestClient):
        res = client.get("/api/settings")
        assert res.status_code == 200
        data = res.json()
        assert data["movies_root"].endswith("/movies")
        assert "tmdb_api_key" not in data

    def test_settings_put(self, client: TestClient, tmp_path: Path):
        payload = {
            "tmdb_api_key": "new-key",
            "movies_root": "/new/movies",
            "tv_root": "/tv",
            "review_dir": "/review",
            "category_map": {"movies": "movie"},
            "tmdb_similarity_threshold": 0.7,
            "include_episode_title": True,
            "dry_run": False,
            "log_level": "INFO",
            "log_file": None,
            "log_max_bytes": 5242880,
            "log_backup_count": 3,
            "hook": {"wsl_distro": "Ubuntu", "wsl_user": "u", "hook_sh": None},
            "web": {"host": "127.0.0.1", "port": 8765},
        }
        res = client.put("/api/settings", json=payload)
        assert res.status_code == 200
        assert res.json()["movies_root"] == "/new/movies"

    def test_review_list(self, client: TestClient):
        res = client.get("/api/review")
        assert res.status_code == 200

    def test_pages_render(self, client: TestClient):
        for path in ("/", "/review", "/settings"):
            res = client.get(path)
            assert res.status_code == 200
            assert "JellyShift" in res.text
