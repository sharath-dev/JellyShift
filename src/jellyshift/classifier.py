from __future__ import annotations

import logging
import re
from typing import Literal

log = logging.getLogger(__name__)

MediaType = Literal["movie", "tv", "unknown"]

_SXEY_RE = re.compile(r"\bS\d{1,3}E\d{1,3}\b", re.IGNORECASE)
_ALTEP_RE = re.compile(r"\b\d{1,2}x\d{2}\b", re.IGNORECASE)
_SEASON_ONLY_RE = re.compile(
    r"(?:\bS\d{1,3}\b(?!E\d)|\bSeason[\s._-]*\d+\b)",
    re.IGNORECASE,
)
_EP_WORD_RE = re.compile(r"\bEpisode[\s._-]*\d+\b", re.IGNORECASE)


def classify(
    name: str,
    category: str | None = None,
    category_map: dict[str, str] | None = None,
) -> MediaType:
    """Classify a torrent as movie, tv, or unknown.

    Resolution order:
    1. qBittorrent category + category_map lookup.
    2. Regex heuristics on the torrent name.
    3. Default to movie when no TV markers are found.
    """
    if category and category_map:
        mapped = category_map.get(category.lower())
        if mapped in ("movie", "tv"):
            log.debug("Classified via category %r → %s", category, mapped)
            return mapped  # type: ignore[return-value]
        log.debug("Unknown category %r → review", category)
        return "unknown"

    for pat in (_SXEY_RE, _ALTEP_RE, _SEASON_ONLY_RE, _EP_WORD_RE):
        if pat.search(name):
            log.debug("Classified via pattern %r in name → tv", pat.pattern)
            return "tv"

    log.debug("No TV markers found in %r → movie", name)
    return "movie"
