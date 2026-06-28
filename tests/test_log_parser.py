"""Tests for log parser."""
from __future__ import annotations

from pathlib import Path

from jellyshift.web.services.log_parser import parse_log_file

SAMPLE_LOG = """\
2026-06-28 10:17:47 INFO     [jellyshift] ────────────────────────────────────────────────────────────
2026-06-28 10:17:47 INFO     [jellyshift]   run_id:       abc-123
2026-06-28 10:17:47 INFO     [jellyshift] JellyShift run started
2026-06-28 10:17:47 INFO     [jellyshift]   config:       /app/config.yaml
2026-06-28 10:17:47 INFO     [jellyshift]   content_path: /downloads/Show.S01E01.mkv
2026-06-28 10:17:47 INFO     [jellyshift]   torrent_name: 'Show.S01E01.mkv'
2026-06-28 10:17:47 INFO     [jellyshift]   category:     'tv'
2026-06-28 10:17:47 INFO     [jellyshift]   dry_run:      False
2026-06-28 10:17:47 INFO     [jellyshift]   force:        False
2026-06-28 10:17:47 INFO     [jellyshift] Classified as: tv
2026-06-28 10:17:47 INFO     [jellyshift.processor] TMDB matched series: My Show (2020)
2026-06-28 10:17:47 INFO     [jellyshift.processor] MOVED    /downloads/Show.S01E01.mkv  →  /tv/My Show/Season 01/file.mkv
2026-06-28 10:17:47 INFO     [jellyshift] JellyShift run finished successfully
2026-06-28 10:18:00 INFO     [jellyshift] ────────────────────────────────────────────────────────────
2026-06-28 10:18:00 INFO     [jellyshift] JellyShift run started
2026-06-28 10:18:00 INFO     [jellyshift]   content_path: /downloads/orphan.mkv
2026-06-28 10:18:00 INFO     [jellyshift]   torrent_name: 'orphan.mkv'
2026-06-28 10:18:00 INFO     [jellyshift]   category:     '(none)'
2026-06-28 10:18:00 INFO     [jellyshift]   dry_run:      False
2026-06-28 10:18:00 INFO     [jellyshift]   force:        False
2026-06-28 10:18:00 WARNING  [jellyshift.review] REVIEW   /downloads/orphan.mkv  →  /review/orphan.mkv  (unclassified)
2026-06-28 10:18:00 INFO     [jellyshift] JellyShift run finished successfully
"""


class TestLogParser:
    def test_parse_runs(self, tmp_path: Path):
        log_file = tmp_path / "jellyshift.log"
        log_file.write_text(SAMPLE_LOG)
        runs = parse_log_file(log_file)
        assert len(runs) == 2
        assert runs[0].run_id == "abc-123"
        assert runs[0].media.classified_as == "tv"
        assert runs[0].media.tmdb_match == "My Show (2020)"
        assert len(runs[0].media.files_moved) == 1
        assert runs[0].status == "success"
        assert runs[1].media.sent_to_review is True
