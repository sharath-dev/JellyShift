from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

log = logging.getLogger(__name__)

TMDB_BASE = "https://api.themoviedb.org/3"


@dataclass
class MovieResult:
    id: int
    title: str
    year: str
    popularity: float


@dataclass
class TvResult:
    id: int
    name: str
    first_air_year: str
    popularity: float


@dataclass
class EpisodeDetail:
    name: str
    season_number: int
    episode_number: int


class TmdbClient:
    def __init__(self, api_key: str) -> None:
        self._key = api_key
        self._session = requests.Session()
        self._session.params = {"api_key": api_key}  # type: ignore[assignment]

    def _get(self, endpoint: str, **params: object) -> dict:
        resp = self._session.get(
            f"{TMDB_BASE}/{endpoint}",
            params=params,  # type: ignore[arg-type]
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    def search_movie(self, title: str, year: int | None = None) -> list[MovieResult]:
        params: dict[str, object] = {"query": title, "include_adult": False}
        if year:
            params["year"] = year
        log.debug("TMDB search/movie query=%r year=%s", title, year)
        data = self._get("search/movie", **params)
        results = []
        for r in data.get("results", []):
            release_year = (r.get("release_date") or "")[:4]
            results.append(
                MovieResult(
                    id=r["id"],
                    title=r["title"],
                    year=release_year,
                    popularity=r.get("popularity", 0.0),
                )
            )
        log.debug("TMDB search/movie returned %d result(s)", len(results))
        return results

    def search_tv(self, title: str) -> list[TvResult]:
        log.debug("TMDB search/tv query=%r", title)
        data = self._get("search/tv", query=title, include_adult=False)
        results = []
        for r in data.get("results", []):
            first_year = (r.get("first_air_date") or "")[:4]
            results.append(
                TvResult(
                    id=r["id"],
                    name=r["name"],
                    first_air_year=first_year,
                    popularity=r.get("popularity", 0.0),
                )
            )
        log.debug("TMDB search/tv returned %d result(s)", len(results))
        return results

    def get_episode(
        self, series_id: int, season: int, episode: int
    ) -> EpisodeDetail | None:
        log.debug(
            "TMDB get episode series_id=%s S%02dE%02d", series_id, season, episode
        )
        try:
            data = self._get(
                f"tv/{series_id}/season/{season}/episode/{episode}"
            )
            return EpisodeDetail(
                name=data.get("name") or "",
                season_number=data["season_number"],
                episode_number=data["episode_number"],
            )
        except requests.HTTPError:
            return None
