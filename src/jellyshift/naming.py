from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

VIDEO_EXTS: frozenset[str] = frozenset(
    {".mkv", ".mp4", ".avi", ".m4v", ".webm", ".mov", ".wmv", ".ts", ".m2ts"}
)

COMPANION_EXTS: frozenset[str] = frozenset(
    {".srt", ".ass", ".ssa", ".sub", ".idx", ".nfo", ".jpg", ".jpeg", ".png", ".tbn"}
)

_JUNK_RE = re.compile(
    r"\b(?:"
    r"720p|1080p|2160p|4320p|4k|uhd|8k"
    r"|blu[- ]?ray|bdrip|brrip|hdrip|hdtv|webrip|web[- ]dl|webdl|web"
    r"|dvdrip|dvd|dvdscr|cam|telesync|workprint"
    r"|x264|x265|h264|h265|hevc|avc|xvid|divx|vp9"
    r"|aac|ac3|dts|ddp|eac3|truehd|atmos|flac|mp3"
    r"|hdr|hdr10|hdr10\+|sdr|dv|dolby"
    r"|extended|theatrical|remastered|proper|repack|retail|hone"
    r"|yify|yts|rarbg|eztv|ettv|ion10|cm8|ntb|befair|fgt"
    r"|10bit|hi10p|remux|prores"
    r"|english|french|german|spanish|hindi|japanese|korean|multi"
    r")\b",
    re.IGNORECASE,
)

# Indexer/site prefix, e.g. "www.UIndex.org - Title..."
_SITE_PREFIX_RE = re.compile(
    r"^\s*(?:www\.)?[a-z0-9][-a-z0-9]*\.(?:org|com|net|to|me|info|cz|ws|ru)\s*[-–—]\s*",
    re.IGNORECASE,
)

# First quality/codec marker — everything after this is release metadata.
_QUALITY_START_RE = re.compile(
    r"\b(?:"
    r"720p|1080p|2160p|4320p|4k|uhd|8k"
    r"|blu[- ]?ray|bdrip|brrip|hdrip|hdtv|webrip|web[- ]dl|webdl|web"
    r"|dvdrip|dvdscr|cam|telesync|workprint"
    r"|x264|x265|h264|h265|hevc|avc|xvid|divx|vp9"
    r"|remux|prores"
    r")\b",
    re.IGNORECASE,
)

# Trailing release group, e.g. "- DarQ HONE REPACK"
_RELEASE_GROUP_SUFFIX_RE = re.compile(
    r"\s*[-–—]\s*(?:"
    r"[A-Z0-9][A-Z0-9.+]*"
    r"(?:\s+[A-Z0-9][A-Z0-9.+]*){0,4}"
    r")\s*$"
)

# Surround sound channel notation left after junk stripping, e.g. "7 1"
_SURROUND_CHANNELS_RE = re.compile(r"\b[257]\s*[.\s]\s*1\b")

_EP_RE = re.compile(
    r"[.\s_-]?S(?P<sn>\d{1,3})E(?P<en>\d{1,3})(?:E\d{1,3})*[.\s_-]?",
    re.IGNORECASE,
)

_ALT_EP_RE = re.compile(r"[.\s_-](?P<sn>\d{1,2})x(?P<en>\d{2})[.\s_-]", re.IGNORECASE)

_SEASON_ONLY_RE = re.compile(
    r"[.\s_-]S(?P<sn>\d{1,3})(?:[.\s_-]|complete|pack|\Z)"
    r"|Season[\s._-]*(?P<sn2>\d{1,3})",
    re.IGNORECASE,
)

_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")

_YEAR_BEFORE_JUNK_RE = re.compile(
    r"\b((?:19|20)\d{2})\b"
    r"(?:[.\s_-]*(?:720p|1080p|2160p|4k|uhd|blu[- ]?ray|bdrip|brrip|hdrip|hdtv"
    r"|webrip|web[- ]dl|web|dvdrip|remux|remastered|proper|repack|extended"
    r"|x264|x265|h264|h265|hevc|avc|xvid|divx))",
    re.IGNORECASE,
)

_UNSAFE_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Jellyfin season folders: "Season 1", "Season 01", "Season 3", etc.
_SEASON_FOLDER_RE = re.compile(r"^Season\s*(\d+)$", re.IGNORECASE)


@dataclass(eq=True)
class EpisodeInfo:
    season: int
    episode: int


def safe_name(s: str) -> str:
    s = re.sub(r":\s+", " - ", s)
    s = _UNSAFE_RE.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


def clean_title(raw: str) -> str:
    s = re.sub(r"[\(\[][^\)\]]*[\)\]]", " ", raw)
    s = re.sub(r"[._]", " ", s)
    s = _JUNK_RE.sub(" ", s)
    s = _SURROUND_CHANNELS_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _normalize_raw(raw: str) -> str:
    s = _SITE_PREFIX_RE.sub("", raw, count=1)
    s = re.sub(r"[._]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _title_before_quality(raw: str) -> str:
    m = _QUALITY_START_RE.search(raw)
    if m:
        return raw[: m.start()].strip(" -_.")
    return raw


def _strip_release_group_suffix(raw: str) -> str:
    return _RELEASE_GROUP_SUFFIX_RE.sub("", raw).strip(" -_.")


def extract_year(raw: str) -> int | None:
    m = _YEAR_BEFORE_JUNK_RE.search(raw)
    if m:
        return int(m.group(1))
    m = _YEAR_RE.search(raw)
    return int(m.group(1)) if m else None


def extract_episode(raw: str) -> EpisodeInfo | None:
    m = _EP_RE.search(raw)
    if m:
        return EpisodeInfo(season=int(m.group("sn")), episode=int(m.group("en")))
    m = _ALT_EP_RE.search(raw)
    if m:
        return EpisodeInfo(season=int(m.group("sn")), episode=int(m.group("en")))
    return None


def title_before_marker(raw: str) -> str:
    for pat in (_EP_RE, _ALT_EP_RE, _SEASON_ONLY_RE):
        m = pat.search(raw)
        if m:
            return raw[: m.start()]
    return raw


def derive_series_title(torrent_name: str) -> str:
    normalized = _normalize_raw(torrent_name)
    before = title_before_marker(normalized)
    raw_title = before if before.strip() else normalized
    raw_title = _title_before_quality(raw_title)
    raw_title = _strip_release_group_suffix(raw_title)
    clean = clean_title(raw_title)
    year = extract_year(raw_title)
    if year:
        clean = re.sub(rf"\b{year}\b", "", clean).strip(" -")
    return safe_name(clean.title())


def derive_movie_title(torrent_name: str) -> tuple[str, int | None]:
    normalized = _normalize_raw(torrent_name)
    title_part = _title_before_quality(normalized)
    title_part = _strip_release_group_suffix(title_part)

    log.debug("Movie title parse: raw=%r", torrent_name)
    log.debug("  normalized:      %r", normalized)
    log.debug("  title_part:      %r", title_part)

    year = extract_year(torrent_name) or extract_year(title_part)
    clean = clean_title(title_part)
    if year:
        clean = re.sub(rf"\b{year}\b", "", clean).strip(" -")
    if not clean and year:
        clean = str(year)
        year = None
    result = safe_name(clean.title()), year
    log.debug("  result:          title=%r year=%s", result[0], result[1])
    return result


def movie_dest(
    movies_root: Path,
    title: str,
    year: str | int,
    ext: str,
) -> Path:
    folder = safe_name(f"{title} ({year})")
    filename = f"{folder}{ext}"
    return movies_root / folder / filename


def resolve_series_folder(
    tv_root: Path, series: str, year: str | int | None = None
) -> str:
    """Return the Jellyfin show folder name, including first-air year when known."""
    if year:
        return safe_name(f"{series} ({year})")
    return safe_name(series)


def resolve_season_folder(series_dir: Path, season: int) -> str:
    """Return an existing season folder name, or the default zero-padded form.

    Treats ``Season 3`` and ``Season 03`` as the same season — reuses whichever
    already exists under *series_dir* so duplicate folders are not created.
    """
    default = f"Season {season:02d}"
    if not series_dir.is_dir():
        return default

    for entry in sorted(series_dir.iterdir()):
        if not entry.is_dir():
            continue
        m = _SEASON_FOLDER_RE.match(entry.name)
        if m and int(m.group(1)) == season:
            log.debug(
                "Reusing existing season folder %r for season %d",
                entry.name,
                season,
            )
            return entry.name

    return default


def tv_dest(
    tv_root: Path,
    series: str,
    season: int,
    episode: int,
    ext: str,
    episode_title: str | None = None,
    year: str | int | None = None,
) -> Path:
    series_folder = resolve_series_folder(tv_root, series, year)
    season_folder = resolve_season_folder(tv_root / series_folder, season)
    ep_tag = f"S{season:02d}E{episode:02d}"
    if episode_title:
        filename = safe_name(f"{series} - {ep_tag} - {episode_title}") + ext
    else:
        filename = f"{safe_name(series)} - {ep_tag}{ext}"
    return tv_root / series_folder / season_folder / filename


def companion_dest(original: Path, video_stem: str, dest_folder: Path) -> Path:
    return dest_folder / f"{video_stem}{original.suffix}"
