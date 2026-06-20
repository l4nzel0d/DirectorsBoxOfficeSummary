"""Domain layer: turn raw IMDb JSON into clean Director/Movie objects.

This module owns all knowledge of the API's nesting and key names, so nothing
downstream (PDF, chart) ever touches a raw dict. Money values are plain ints;
0 means "missing or genuinely zero" — there is no separate unknown sentinel.
"""

import re
from dataclasses import dataclass

from . import imdb_api


@dataclass
class Director:
    id: str
    name: str
    image_url: str | None = None


@dataclass
class Movie:
    id: str
    title: str
    year: int | None = None
    poster_url: str | None = None
    budget: int = 0
    domestic_gross: int = 0
    worldwide_gross: int = 0
    opening_weekend: int = 0


_TITLE_ID = re.compile(r"/title/(tt\d+)/?")


def _bare_title_id(raw: str) -> str:
    """'/title/tt15398776/' -> 'tt15398776' (passes through if already bare)."""
    match = _TITLE_ID.search(raw)
    return match.group(1) if match else raw


def _amount(node, *path: str) -> int:
    """Walk `path` to a Money node and return its `amount`, or 0 if any step
    along the way (or the amount itself) is missing/None."""
    for key in path:
        if not isinstance(node, dict):
            return 0
        node = node.get(key)
    if isinstance(node, dict):
        node = node.get("amount")
    return int(node) if isinstance(node, (int, float)) else 0


def _opening_weekend(box: dict) -> int:
    """Opening-weekend gross lives behind a (possibly empty) edges list."""
    edges = (box.get("openingWeekendGrosses") or {}).get("edges") or []
    if not edges:
        return 0
    return _amount(edges[0], "node", "gross", "total")


def find_director(query: str) -> Director | None:
    """Search by name and take the top autocomplete hit, or None if no match."""
    candidates = imdb_api.search_director(query)
    if not candidates:
        return None
    top = candidates[0]
    image = top.get("i") or {}
    return Director(
        id=top["id"],
        name=top["l"],
        image_url=image.get("imageUrl"),
    )


def _build_movie(film: dict, box: dict) -> Movie:
    """Assemble a Movie from a filmography entry + its box-office summary.

    Pure: no network, so it's testable with hand-built dicts.
    """
    image = film.get("image") or {}
    return Movie(
        id=_bare_title_id(film["id"]),
        title=film["title"],
        year=film.get("year"),
        poster_url=image.get("url"),
        budget=_amount(box, "budget", "totalBudget"),
        domestic_gross=_amount(box, "domesticGross", "total"),
        worldwide_gross=_amount(box, "worldwideGross", "total"),
        opening_weekend=_opening_weekend(box),
    )


def get_directed_films(director_id: str) -> list[Movie]:
    """All released theatrical features a person directed, with box office.

    Makes one box-office call per film (sequential). Unsorted — callers sort
    for their own needs. Fail-fast: an API error on any title propagates.
    """
    filmography = imdb_api.get_filmography(director_id)
    directed = [
        film
        for film in filmography
        if film.get("category") == "director"
        and film.get("status") == "released"
        and film.get("titleType") == "movie"
    ]
    movies = []
    for film in directed:
        box = imdb_api.get_box_office(_bare_title_id(film["id"]))
        movies.append(_build_movie(film, box))
    return movies
