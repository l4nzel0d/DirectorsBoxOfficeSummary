"""Domain layer: turn raw IMDb GraphQL JSON into clean domain objects.

This module owns all knowledge of the API's nesting and key names, so nothing
downstream (PDF, chart, main) ever touches a raw dict. The data types live in
`models`; this module builds them and provides the aggregates/selectors the
PDF layer reads.
"""

import math
import unicodedata
from datetime import date

from . import imdb_api
from .models import Director, DirectorCandidate, Movie

__all__ = [
    "Director",
    "DirectorCandidate",
    "Movie",
    "search_directors",
    "pick_director",
    "get_director",
    "get_directed_films",
    "total_worldwide",
    "total_domestic",
    "total_international",
    "by_worldwide_desc",
    "top_by_worldwide",
    "top_by_domestic",
    "top_by_opening",
]


def _amount(node, *path: str) -> int:
    """Walk `path` to a Money node ({amount, currency}) and return its amount
    as an int, or 0 if any step (or the amount itself) is missing/None/
    unparseable. Non-USD amounts also count as missing: the PDF prints dollars
    and the totals sum them, and IMDb gives some budgets in local currency
    (RRR's is 3,500,000,000 INR)."""
    for key in path:
        if not isinstance(node, dict):
            return 0
        node = node.get(key)
    if isinstance(node, dict):
        if node.get("currency") not in (None, "USD"):
            return 0
        node = node.get("amount")
    if isinstance(node, str):
        try:
            return int(node)
        except ValueError:
            return 0
    return int(node) if isinstance(node, (int, float)) else 0


def _text(node) -> str | None:
    """The `text` of a GraphQL text node like nameText/titleText, or None."""
    return node.get("text") if isinstance(node, dict) else None


def _norm(name: str) -> str:
    """Case- and accent-insensitive form of a name, for exact-match checks
    ("inarritu" matches "Iñárritu")."""
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.casefold().split())


def _known_for(person: dict, limit: int = 3) -> str:
    """Format a person's known-for titles, e.g. "Get Out (2017), Us (2019)"."""
    parts = []
    for credit in ((person.get("knownForV2") or {}).get("credits") or [])[:limit]:
        title = credit.get("title") or {}
        name = _text(title.get("titleText"))
        if not name:
            continue
        year = (title.get("releaseYear") or {}).get("year")
        parts.append(f"{name} ({year})" if year else name)
    return ", ".join(parts)


def _candidate(person: dict) -> DirectorCandidate:
    categories = [p.get("category") or {} for p in person.get("primaryProfessions") or []]
    return DirectorCandidate(
        id=person["id"],
        name=_text(person.get("nameText")) or person["id"],
        professions=", ".join(c["text"] for c in categories if c.get("text")),
        is_director=any(c.get("id") == "director" for c in categories),
        known_for=_known_for(person),
        rank=(person.get("meterRanking") or {}).get("currentRank"),
    )


def _rank_key(c: DirectorCandidate) -> float:
    """Sort key for popularity: lower rank first, unranked last."""
    return c.rank if c.rank is not None else math.inf


def search_directors(name: str) -> list[DirectorCandidate]:
    """Search IMDb for people named `name`, best candidates first.

    Ranked by: has "Director" among their professions, then exact name match,
    then STARmeter rank. The sort is stable, so ties keep IMDb's own relevance
    order. Non-directors are kept (ranked lower) so the user can still pick them.
    """
    query = _norm(name)
    candidates = [_candidate(p) for p in imdb_api.search_names(name) if p.get("id")]
    return sorted(
        candidates,
        key=lambda c: (not c.is_director, _norm(c.name) != query, _rank_key(c)),
    )


# How many times better (lower) the top director's rank must be than the
# runner-up's to be picked without asking. Searching "nolan" gives Christopher
# Nolan rank 94 and Jonathan Nolan rank 3421, a 36x lead.
CLEAR_LEAD = 5


def pick_director(name: str, candidates: list[DirectorCandidate]) -> DirectorCandidate | None:
    """The obvious match for `name`, or None if the user should choose.

    Looks among the exact-name matches if there are any, otherwise among all
    candidates. A lone director there wins, as does a ranked director with a
    clear rank lead over the other directors (or over unranked ones). With no
    directors, only a lone match is trusted.
    """
    query = _norm(name)
    pool = [c for c in candidates if _norm(c.name) == query] or candidates
    directors = [c for c in pool if c.is_director]
    if not directors:
        return pool[0] if len(pool) == 1 else None
    if len(directors) == 1:
        return directors[0]
    top, runner_up = sorted(directors, key=_rank_key)[:2]
    if top.rank is not None and (runner_up.rank is None or runner_up.rank >= CLEAR_LEAD * top.rank):
        return top
    return None


def get_director(name_id: str) -> Director | None:
    """Resolve a bare IMDb name id (e.g. "nm0634240") to a Director, or None if
    no such name exists (the API answers an unknown id with a null nameText)."""
    name = imdb_api.get_name(name_id)
    display = _text((name or {}).get("nameText"))
    if not display:
        return None
    image = name.get("primaryImage") or {}
    return Director(
        id=name["id"],
        name=display,
        image_url=image.get("url"),
    )


def _build_movie(title: dict) -> Movie:
    """Assemble a Movie from a credits Title node (which carries its own box
    office). Pure: no network, so it's testable with hand-built dicts."""
    image = title.get("primaryImage") or {}
    return Movie(
        id=title["id"],
        title=_text(title.get("titleText")) or title["id"],
        year=(title.get("releaseYear") or {}).get("year"),
        poster_url=image.get("url"),
        budget=_amount(title, "productionBudget", "budget"),
        domestic_gross=_amount(title, "domestic", "total"),
        worldwide_gross=_amount(title, "worldwide", "total"),
        opening_weekend=_amount(title, "openingWeekendGross", "gross", "total"),
    )


def _is_released_feature(title: dict) -> bool:
    """A directed title counts as a box-office feature when it's a movie (not a
    short, TV movie, video...) whose production stage is "released". If IMDb
    gives no stage, fall back to a known release year that isn't in the future."""
    if (title.get("titleType") or {}).get("id") != "movie":
        return False
    status = title.get("productionStatus") or {}
    stage = (status.get("currentProductionStage") or {}).get("id")
    if stage is not None:
        return stage == "released"
    year = (title.get("releaseYear") or {}).get("year")
    return isinstance(year, int) and year <= date.today().year


def get_directed_films(director_id: str) -> list[Movie]:
    """All released theatrical features a person directed, with box office.

    One paged query returns every directing credit with its budget and grosses;
    we keep the released movies (see _is_released_feature). Unsorted — callers
    sort for their own needs. Fail-fast: an API error propagates.
    """
    titles = imdb_api.get_directing_credits(director_id)
    return [_build_movie(t) for t in titles if _is_released_feature(t)]


# --------------------------------------------------------------------------- #
# Pure aggregates / selectors over a list of Movies (used by the PDF layer).
# All tolerate an empty list: totals return 0, selectors return None.
# --------------------------------------------------------------------------- #


def total_worldwide(movies: list[Movie]) -> int:
    return sum(m.worldwide_gross for m in movies)


def total_domestic(movies: list[Movie]) -> int:
    return sum(m.domestic_gross for m in movies)


def total_international(movies: list[Movie]) -> int:
    """Worldwide minus domestic."""
    return total_worldwide(movies) - total_domestic(movies)


def by_worldwide_desc(movies: list[Movie]) -> list[Movie]:
    """Copy sorted by worldwide gross, highest first (table/ranking order)."""
    return sorted(movies, key=lambda m: m.worldwide_gross, reverse=True)


def top_by_worldwide(movies: list[Movie]) -> Movie | None:
    return max(movies, key=lambda m: m.worldwide_gross, default=None)


def top_by_domestic(movies: list[Movie]) -> Movie | None:
    return max(movies, key=lambda m: m.domestic_gross, default=None)


def top_by_opening(movies: list[Movie]) -> Movie | None:
    return max(movies, key=lambda m: m.opening_weekend, default=None)
