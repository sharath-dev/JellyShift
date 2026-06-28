from __future__ import annotations

import difflib
import logging
import shutil
from pathlib import Path

from .config import Config
from .naming import (
    COMPANION_EXTS,
    VIDEO_EXTS,
    EpisodeInfo,
    companion_dest,
    derive_movie_title,
    derive_series_title,
    extract_episode,
    movie_dest,
    safe_name,
    tv_dest,
)
from .review import send_to_review
from .tmdb import TmdbClient

log = logging.getLogger(__name__)


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def safe_move(src: Path, dst: Path, *, dry_run: bool, force: bool) -> None:
    if dry_run:
        log.info("DRY-RUN  %s  →  %s", src, dst)
        return
    if dst.exists() and not force:
        log.warning("SKIP (already exists): %s", dst)
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    log.info("MOVED    %s  →  %s", src, dst)


def enum_files(content_path: Path) -> list[Path]:
    if content_path.is_dir():
        return [p for p in content_path.rglob("*") if p.is_file()]
    return [content_path]


def enum_video_files(content_path: Path) -> list[Path]:
    return sorted(
        (f for f in enum_files(content_path) if f.suffix.lower() in VIDEO_EXTS),
        key=lambda p: p.name,
    )


def stem_matches(video_stem: str, companion_stem: str) -> bool:
    if companion_stem == video_stem:
        return True
    for sep in (".", " ", "-", "_"):
        if companion_stem.startswith(video_stem + sep):
            return True
    return False


def companions_for_video(
    video: Path,
    all_files: list[Path],
    ep_info_filter: EpisodeInfo | None = None,
) -> list[Path]:
    comps = []
    for f in all_files:
        if f == video:
            continue
        if f.suffix.lower() not in COMPANION_EXTS:
            continue
        if stem_matches(video.stem, f.stem) or (
            ep_info_filter is not None and extract_episode(f.name) == ep_info_filter
        ):
            comps.append(f)
    return comps


def process_movie(
    content_path: Path,
    torrent_name: str,
    tmdb: TmdbClient,
    config: Config,
    *,
    dry_run: bool,
    force: bool,
) -> None:
    parsed_title, parsed_year = derive_movie_title(torrent_name)
    log.debug("Movie parse  title=%r  year=%s", parsed_title, parsed_year)

    best_title = parsed_title
    best_year: str | int = parsed_year or "????"
    matched = False

    try:
        results = tmdb.search_movie(parsed_title, year=parsed_year)
        if not results and parsed_year:
            results = tmdb.search_movie(parsed_title)
        if results:
            top = results[0]
            score = similarity(parsed_title, top.title)
            log.debug("TMDB movie top match: %r  score=%.2f", top.title, score)
            if score >= config.tmdb_similarity_threshold:
                best_title = safe_name(top.title)
                best_year = top.year or best_year
                matched = True
                log.info("TMDB matched movie: %s (%s)", best_title, best_year)
            else:
                log.info(
                    "TMDB match too weak (%.2f < %.2f), using parse fallback: %r",
                    score,
                    config.tmdb_similarity_threshold,
                    parsed_title,
                )
    except Exception as exc:
        log.warning("TMDB lookup failed: %s — using parse fallback", exc)

    video_files = enum_video_files(content_path)
    log.debug("Found %d video file(s) in %s", len(video_files), content_path)
    if not video_files:
        send_to_review(
            content_path,
            config.review_dir,
            "no video files found",
            torrent_name=torrent_name,
            dry_run=dry_run,
        )
        return

    all_files = enum_files(content_path)
    primary = max(video_files, key=lambda p: p.stat().st_size)
    log.debug("Primary movie file: %s (%d bytes)", primary.name, primary.stat().st_size)
    dest = movie_dest(config.movies_root, best_title, best_year, primary.suffix)
    safe_move(primary, dest, dry_run=dry_run, force=force)

    for comp in companions_for_video(primary, all_files):
        cdest = companion_dest(comp, dest.stem, dest.parent)
        safe_move(comp, cdest, dry_run=dry_run, force=force)

    if not matched:
        log.warning(
            "No confident TMDB match — renamed using parsed title. "
            "If incorrect, check: %s",
            dest.parent if not dry_run else dest,
        )


def process_tv(
    content_path: Path,
    torrent_name: str,
    tmdb: TmdbClient,
    config: Config,
    *,
    dry_run: bool,
    force: bool,
) -> None:
    parsed_series = derive_series_title(torrent_name)
    log.debug("TV parse  series=%r", parsed_series)

    best_series = parsed_series
    best_year: str | None = None
    series_id: int | None = None

    try:
        results = tmdb.search_tv(parsed_series)
        if results:
            top = results[0]
            score = similarity(parsed_series, top.name)
            log.debug("TMDB TV top match: %r  score=%.2f", top.name, score)
            if score >= config.tmdb_similarity_threshold:
                best_series = safe_name(top.name)
                best_year = top.first_air_year or None
                series_id = top.id
                if best_year:
                    log.info("TMDB matched series: %s (%s)", best_series, best_year)
                else:
                    log.info("TMDB matched series: %s", best_series)
            else:
                log.info(
                    "TMDB TV match too weak (%.2f < %.2f), using parse fallback: %r",
                    score,
                    config.tmdb_similarity_threshold,
                    parsed_series,
                )
    except Exception as exc:
        log.warning("TMDB lookup failed: %s — using parse fallback", exc)

    video_files = enum_video_files(content_path)
    log.debug("Found %d video file(s) in %s", len(video_files), content_path)
    if not video_files:
        send_to_review(
            content_path,
            config.review_dir,
            "no video files found",
            torrent_name=torrent_name,
            dry_run=dry_run,
        )
        return

    all_files = enum_files(content_path)

    for vf in video_files:
        ep_info = extract_episode(vf.name) or extract_episode(vf.parent.name)
        log.debug("Processing TV file %s → episode %s", vf.name, ep_info)
        if not ep_info:
            log.warning("Cannot detect episode code in %s — sending to review", vf.name)
            send_to_review(
                vf,
                config.review_dir,
                f"no episode code in {vf.name}",
                torrent_name=torrent_name,
                dry_run=dry_run,
            )
            continue

        ep_title: str | None = None
        if series_id and config.include_episode_title:
            try:
                detail = tmdb.get_episode(series_id, ep_info.season, ep_info.episode)
                if detail and detail.name:
                    ep_title = safe_name(detail.name)
            except Exception as exc:
                log.debug("Could not fetch episode title: %s", exc)

        dest = tv_dest(
            config.tv_root,
            best_series,
            ep_info.season,
            ep_info.episode,
            vf.suffix,
            ep_title,
            year=best_year,
        )
        safe_move(vf, dest, dry_run=dry_run, force=force)

        for comp in companions_for_video(vf, all_files, ep_info_filter=ep_info):
            cdest = companion_dest(comp, dest.stem, dest.parent)
            safe_move(comp, cdest, dry_run=dry_run, force=force)
