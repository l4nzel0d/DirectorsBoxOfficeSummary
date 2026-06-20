"""Render a director's box-office-over-time chart as an in-memory PNG.

Consumes Movie objects only; returns a BytesIO that fpdf can embed directly,
so nothing touches disk. Uses the object-oriented Figure API on the Agg
backend (headless-safe — no display required).
"""

import io

import matplotlib

matplotlib.use("Agg")
from matplotlib.figure import Figure

from .movies import Movie

_MILLION = 1_000_000


def _label(movie: Movie, show_year: bool) -> str:
    """Title, optionally with the year on a second line. Falls back to
    title-only when the year is unknown."""
    if show_year and movie.year is not None:
        return f"{movie.title}\n{movie.year}"
    return movie.title


def render_chart(movies: list[Movie]) -> io.BytesIO | None:
    """Two-line chart (worldwide + domestic gross, in $millions) across the
    director's career. Returns a PNG buffer, or None if there's nothing to plot.
    """
    if not movies:
        return None

    # Career timeline left->right; unknown-year films sort to the end.
    movies = sorted(movies, key=lambda m: (m.year is None, m.year))

    # Crowding heuristics: drop the per-tick year once there are many films,
    # and rotate ticks when they'd otherwise overlap.
    show_year = len(movies) <= 12
    labels = [_label(m, show_year) for m in movies]
    rotation = 90 if (len(movies) >= 6 or any(len(l) > 27 for l in labels)) else 0

    worldwide = [m.worldwide_gross / _MILLION for m in movies]
    domestic = [m.domestic_gross / _MILLION for m in movies]

    fig = Figure(figsize=(9, 5), dpi=150)
    ax = fig.subplots()
    ax.plot(worldwide, marker="o", label="Worldwide")
    ax.plot(domestic, marker="o", label="Domestic")
    ax.legend()
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=rotation)
    ax.set_title("Box Office Graph")
    ax.set_ylabel("Gross in $Millions")
    fig.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png")
    buffer.seek(0)
    return buffer
