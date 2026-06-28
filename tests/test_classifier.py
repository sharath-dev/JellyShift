"""Tests for media type classification."""
from __future__ import annotations

import pytest

from jellyshift.classifier import classify

CATEGORY_MAP = {
    "movies": "movie",
    "tv": "tv",
    "shows": "tv",
}


class TestClassifyByCategory:
    def test_movies_category(self):
        assert classify("Anything", category="movies", category_map=CATEGORY_MAP) == "movie"

    def test_tv_category(self):
        assert classify("S01E01", category="tv", category_map=CATEGORY_MAP) == "tv"

    def test_category_case_insensitive(self):
        assert classify("name", category="MOVIES", category_map=CATEGORY_MAP) == "movie"

    def test_unrecognised_category_returns_unknown(self):
        result = classify("Show.S01E01.mkv", category="audiobooks", category_map=CATEGORY_MAP)
        assert result == "unknown"

    def test_no_category_still_uses_heuristics(self):
        assert classify("Show.S01E01.mkv", category=None, category_map=CATEGORY_MAP) == "tv"


class TestClassifyByName:
    @pytest.mark.parametrize("name", [
        "Breaking.Bad.S01E03.BluRay",
        "show.s02e11.mkv",
        "Show.2x05.HDTV",
        "Series S01 Complete 1080p",
        "Episode 5 HDTV",
        "Season 2 Complete",
    ])
    def test_tv_patterns(self, name):
        assert classify(name) == "tv"

    @pytest.mark.parametrize("name", [
        "The.Dark.Knight.2008.1080p.BluRay",
        "Inception.2010.BluRay.x264",
        "Parasite.2019.1080p",
    ])
    def test_movie_patterns(self, name):
        assert classify(name) == "movie"

    def test_no_category_map(self):
        result = classify("Show.S01E01.mkv", category=None, category_map=None)
        assert result == "tv"
