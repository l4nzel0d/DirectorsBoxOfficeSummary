"""Shared domain types — the vocabulary every layer speaks.

Intentionally dependency-free (no project imports, no I/O): the API client, the
PDF, and the chart all name these types, so they live at the bottom of the
layering. Money values are plain ints; 0 means "missing or genuinely zero" —
there is no separate unknown sentinel.
"""

from dataclasses import dataclass


@dataclass
class Director:
    id: str
    name: str
    image_url: str | None = None


@dataclass
class DirectorCandidate:
    """A person matched by a name search, before fetching them as a Director."""

    id: str  # IMDb name id, e.g. "nm0634240"
    name: str
    professions: str = ""  # e.g. "Producer, Writer, Director"
    is_director: bool = False  # "Director" is among their professions
    known_for: str = ""  # e.g. "Get Out (2017), Us (2019)"
    rank: int | None = None  # IMDb STARmeter rank: lower is more popular; None = unranked


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
