"""Tests for file processing helpers."""
from __future__ import annotations

from pathlib import Path

from jellyshift.processor import companions_for_video, enum_video_files, safe_move
from jellyshift.naming import EpisodeInfo


class TestEnumVideoFiles:
    def test_single_file(self, tmp_path: Path):
        video = tmp_path / "movie.mkv"
        video.write_bytes(b"video")
        assert enum_video_files(video) == [video]

    def test_folder_with_multiple(self, tmp_path: Path):
        (tmp_path / "a.mkv").write_bytes(b"a")
        (tmp_path / "b.mp4").write_bytes(b"b")
        (tmp_path / "readme.txt").write_text("nope")
        result = enum_video_files(tmp_path)
        assert len(result) == 2
        assert all(p.suffix in {".mkv", ".mp4"} for p in result)


class TestCompanionsForVideo:
    def test_matching_srt(self, tmp_path: Path):
        video = tmp_path / "show.s01e01.mkv"
        srt = tmp_path / "show.s01e01.en.srt"
        video.write_bytes(b"v")
        srt.write_text("subs")
        all_files = [video, srt]
        comps = companions_for_video(video, all_files)
        assert srt in comps

    def test_episode_filter(self, tmp_path: Path):
        ep1 = tmp_path / "show.s01e01.mkv"
        ep2 = tmp_path / "show.s01e02.mkv"
        sub1 = tmp_path / "show.s01e01.srt"
        sub2 = tmp_path / "show.s01e02.srt"
        for f in (ep1, ep2, sub1, sub2):
            f.write_bytes(b"x")
        comps = companions_for_video(
            ep1, [ep1, ep2, sub1, sub2], ep_info_filter=EpisodeInfo(1, 1)
        )
        assert sub1 in comps
        assert sub2 not in comps


class TestSafeMove:
    def test_dry_run_does_not_move(self, tmp_path: Path):
        src = tmp_path / "src.mkv"
        dst = tmp_path / "dest" / "dst.mkv"
        src.write_bytes(b"data")
        safe_move(src, dst, dry_run=True, force=False)
        assert src.exists()
        assert not dst.exists()

    def test_move_creates_parents(self, tmp_path: Path):
        src = tmp_path / "src.mkv"
        dst = tmp_path / "nested" / "dst.mkv"
        src.write_bytes(b"data")
        safe_move(src, dst, dry_run=False, force=False)
        assert not src.exists()
        assert dst.exists()
        assert dst.read_bytes() == b"data"

    def test_skip_existing(self, tmp_path: Path):
        src = tmp_path / "src.mkv"
        dst = tmp_path / "dst.mkv"
        src.write_bytes(b"new")
        dst.write_bytes(b"old")
        safe_move(src, dst, dry_run=False, force=False)
        assert src.exists()
        assert dst.read_bytes() == b"old"

    def test_force_overwrites(self, tmp_path: Path):
        src = tmp_path / "src.mkv"
        dst = tmp_path / "dst.mkv"
        src.write_bytes(b"new")
        dst.write_bytes(b"old")
        safe_move(src, dst, dry_run=False, force=True)
        assert not src.exists()
        assert dst.read_bytes() == b"new"
