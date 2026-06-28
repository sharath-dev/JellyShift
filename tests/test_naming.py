"""Tests for filename parsing and Jellyfin path generation."""
from __future__ import annotations

from pathlib import Path

import pytest

from jellyshift.naming import (
    EpisodeInfo,
    clean_title,
    companion_dest,
    derive_movie_title,
    derive_series_title,
    extract_episode,
    extract_year,
    movie_dest,
    resolve_season_folder,
    resolve_series_folder,
    safe_name,
    title_before_marker,
    tv_dest,
)
from jellyshift.processor import stem_matches


class TestCleanTitle:
    def test_strips_resolution(self):
        assert "1080p" not in clean_title("Some.Movie.2023.1080p.BluRay")

    def test_strips_codec(self):
        result = clean_title("Show.S01E01.HDTV.x264-GROUP")
        assert "x264" not in result
        assert "HDTV" not in result

    def test_replaces_dots_with_spaces(self):
        assert "." not in clean_title("Breaking.Bad.S01E01")

    def test_strips_release_group(self):
        result = clean_title("Movie.2021.BluRay.YIFY")
        assert "YIFY" not in result

    def test_keeps_title_words(self):
        result = clean_title("The.Dark.Knight.2008.1080p")
        assert "Dark" in result
        assert "Knight" in result


class TestExtractYear:
    @pytest.mark.parametrize("raw,expected", [
        ("The.Matrix.1999.BluRay", 1999),
        ("Avatar.2009.1080p", 2009),
        ("no_year_here", None),
        ("2001.A.Space.Odyssey", 2001),
    ])
    def test_various(self, raw, expected):
        assert extract_year(raw) == expected


class TestExtractEpisode:
    @pytest.mark.parametrize("raw,expected", [
        ("Breaking.Bad.S01E03.BluRay", EpisodeInfo(season=1, episode=3)),
        ("show.s02e11.mkv", EpisodeInfo(season=2, episode=11)),
        ("Show.2x05.HDTV", EpisodeInfo(season=2, episode=5)),
        ("Movie.2021.BluRay", None),
        ("Series.S10E01.mkv", EpisodeInfo(season=10, episode=1)),
    ])
    def test_various(self, raw, expected):
        assert extract_episode(raw) == expected

    def test_multi_episode_returns_first(self):
        ep = extract_episode("Show.S01E01E02.mkv")
        assert ep == EpisodeInfo(season=1, episode=1)


class TestTitleBeforeMarker:
    def test_sxey(self):
        result = title_before_marker("Breaking.Bad.S01E01.Pilot.BluRay")
        assert result == "Breaking.Bad"

    def test_season_only_pack(self):
        result = title_before_marker("Breaking.Bad.S01.Complete")
        assert "S01" not in result
        assert "Breaking" in result

    def test_no_marker(self):
        raw = "The.Dark.Knight.2008"
        assert title_before_marker(raw) == raw


class TestDeriveMovieTitle:
    def test_basic(self):
        title, year = derive_movie_title("The.Dark.Knight.2008.1080p.BluRay")
        assert year == 2008
        assert "Dark" in title
        assert "Knight" in title

    def test_no_year(self):
        title, year = derive_movie_title("Inception.BluRay.x264")
        assert year is None
        assert "Inception" in title

    def test_2001(self):
        title, year = derive_movie_title("2001.A.Space.Odyssey.1968.BluRay")
        assert year == 1968

    def test_unsafe_chars(self):
        title, _ = derive_movie_title("Mission.Impossible.2023.BluRay")
        assert "<" not in title and ">" not in title

    def test_uindex_superman(self):
        raw = (
            "www.UIndex.org    -    Superman 2025 1080p BluRay x265 SDR "
            "DDP Atmos 7 1 English - DarQ HONE REPACK"
        )
        title, year = derive_movie_title(raw)
        assert title == "Superman"
        assert year == 2025

    def test_site_prefix_stripped(self):
        title, year = derive_movie_title("www.Example.com - Inception 2010 1080p BluRay")
        assert title == "Inception"
        assert year == 2010


class TestDeriveSeriesTitle:
    def test_sxey_torrent(self):
        title = derive_series_title("Breaking.Bad.S03E07.1080p.BluRay")
        assert "Breaking" in title
        assert "Bad" in title
        assert "S03" not in title

    def test_season_pack(self):
        title = derive_series_title("The.Wire.S02.Complete.1080p")
        assert "Wire" in title
        assert "S02" not in title

    def test_plain_series_name(self):
        title = derive_series_title("Succession")
        assert "Succession" in title


class TestMovieDest:
    def test_structure(self):
        root = Path("/jellyfin/Movies")
        dest = movie_dest(root, "The Dark Knight", 2008, ".mkv")
        assert dest == root / "The Dark Knight (2008)" / "The Dark Knight (2008).mkv"

    def test_year_as_string(self):
        root = Path("/jellyfin/Movies")
        dest = movie_dest(root, "Some Film", "2020", ".mp4")
        assert "(2020)" in str(dest)


class TestTvDest:
    def test_with_episode_title(self):
        root = Path("/jellyfin/TV")
        dest = tv_dest(root, "Breaking Bad", 1, 3, ".mkv", "And the Bag's in the River")
        assert dest.parent == root / "Breaking Bad" / "Season 01"
        assert "S01E03" in dest.name
        assert "And the Bag" in dest.name

    def test_without_episode_title(self):
        root = Path("/jellyfin/TV")
        dest = tv_dest(root, "Succession", 2, 10, ".mkv")
        assert dest.name == "Succession - S02E10.mkv"

    def test_season_zero_padded(self):
        root = Path("/jellyfin/TV")
        dest = tv_dest(root, "Some Show", 1, 1, ".mkv")
        assert "Season 01" in str(dest)

    def test_year_in_series_folder(self):
        root = Path("/jellyfin/TV")
        dest = tv_dest(
            root,
            "My Adventures with Superman",
            3,
            3,
            ".mkv",
            "All's Fair in Love and W.O.R.M.S.",
            year=2023,
        )
        assert dest.parent == root / "My Adventures with Superman (2023)" / "Season 03"
        assert dest.name.startswith("My Adventures with Superman - S03E03")
        assert "(2023)" not in dest.name


class TestResolveSeriesFolder:
    def test_with_year(self):
        assert (
            resolve_series_folder(Path("/TV"), "Breaking Bad", 2008)
            == "Breaking Bad (2008)"
        )

    def test_without_year(self):
        assert resolve_series_folder(Path("/TV"), "Breaking Bad") == "Breaking Bad"


class TestResolveSeasonFolder:
    def test_reuses_season_without_zero_pad(self, tmp_path: Path):
        series_dir = tmp_path / "Breaking Bad"
        (series_dir / "Season 3").mkdir(parents=True)
        assert resolve_season_folder(series_dir, 3) == "Season 3"

    def test_reuses_season_with_zero_pad(self, tmp_path: Path):
        series_dir = tmp_path / "Breaking Bad"
        (series_dir / "Season 03").mkdir(parents=True)
        assert resolve_season_folder(series_dir, 3) == "Season 03"

    def test_defaults_when_missing(self, tmp_path: Path):
        series_dir = tmp_path / "Breaking Bad"
        series_dir.mkdir()
        assert resolve_season_folder(series_dir, 3) == "Season 03"

    def test_tv_dest_uses_existing_unpadded_season(self, tmp_path: Path):
        root = tmp_path / "TV"
        series_dir = root / "Superman"
        (series_dir / "Season 3").mkdir(parents=True)
        dest = tv_dest(root, "Superman", 3, 3, ".mkv")
        assert dest.parent == series_dir / "Season 3"
        assert "Season 03" not in str(dest.parent)

    def test_tv_dest_uses_existing_padded_season(self, tmp_path: Path):
        root = tmp_path / "TV"
        series_dir = root / "Superman"
        (series_dir / "Season 03").mkdir(parents=True)
        dest = tv_dest(root, "Superman", 3, 3, ".mkv")
        assert dest.parent == series_dir / "Season 03"


class TestCompanionDest:
    def test_srt(self):
        srt = Path("/downloads/show/show.s01e01.en.srt")
        dest_folder = Path("/jellyfin/TV/Show/Season 01")
        result = companion_dest(srt, "Show - S01E01", dest_folder)
        assert result == dest_folder / "Show - S01E01.srt"

    def test_nfo(self):
        nfo = Path("/downloads/movie/movie.nfo")
        dest_folder = Path("/jellyfin/Movies/Film (2020)")
        result = companion_dest(nfo, "Film (2020)", dest_folder)
        assert result == dest_folder / "Film (2020).nfo"


class TestSafeName:
    def test_colon_replaced(self):
        assert safe_name("Mission: Impossible") == "Mission - Impossible"

    def test_no_illegal_chars(self):
        result = safe_name('A/B<C>D"E')
        for ch in r'/<>"':
            assert ch not in result


class TestStemMatches:
    def test_exact_match(self):
        assert stem_matches("movie", "movie") is True

    def test_dot_suffix(self):
        assert stem_matches("movie", "movie.en") is True

    def test_space_suffix(self):
        assert stem_matches("Movie Title", "Movie Title forced") is True

    def test_hyphen_suffix(self):
        assert stem_matches("movie", "movie-sdh") is True

    def test_underscore_suffix(self):
        assert stem_matches("movie", "movie_en") is True

    def test_no_false_positive_substring(self):
        assert stem_matches("show.s01", "show.s01e01") is False

    def test_no_false_positive_interior(self):
        assert stem_matches("s01", "show.s01e01") is False

    def test_different_stems(self):
        assert stem_matches("show.s01e01", "show.s01e02.en") is False
