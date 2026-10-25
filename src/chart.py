"""Render a director's box-office-over-time chart as an in-memory PNG.

Consumes Movie objects only; returns a BytesIO that fpdf can embed directly,
so nothing touches disk. Uses the object-oriented Figure API on the Agg
backend (headless-safe — no display required). The figure is drawn at the
exact physical size of its box in the PDF, so text is never rescaled.
"""

import io
import math
import textwrap

import matplotlib

matplotlib.use("Agg")
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from .models import Movie
from .movies import by_year

_MILLION = 1_000_000
_DPI = 150

# Tick-label layout search (see _choose_labels). Fonts are tried largest
# first; a smaller one is only used when nothing fits at the larger size.
_FONT_SIZES = (10, 9, 8, 7, 6)
_WRAP_WIDTHS = (None, 24, 18, 14)  # characters per line; None = no wrapping
_ANGLES = (0, 90)  # upright or vertical only; slanted labels look messy
_GAP = 1.25  # min distance between neighbouring rotated labels, in label heights
_MAX_REACH = 3  # a rotated label may span at most this many tick slots


def _label(movie: Movie, show_year: bool, wrap: int | None) -> str:
    """Title, wrapped to `wrap` characters per line if given, optionally with
    the year on a last line. Falls back to title-only when the year is unknown."""
    title = movie.title
    if wrap:
        title = "\n".join(textwrap.wrap(title, wrap, break_long_words=False))
    if show_year and movie.year is not None:
        return f"{title}\n{movie.year}"
    return title


def _fits(w: float, h: float, spacing: float, angle: int) -> bool:
    """Whether labels of unrotated size w x h (pixels), one every `spacing`
    pixels, can be drawn at `angle` degrees without colliding."""
    if angle == 0:
        return w <= 0.95 * spacing
    a = math.radians(angle)
    return (
        spacing * math.sin(a) >= _GAP * h
        and w * math.cos(a) + h * math.sin(a) <= _MAX_REACH * spacing
    )


def _choose_labels(movies, show_year, spacing, measure) -> tuple[list[str], int, int]:
    """Pick the tick labels, rotation and font size that leave the plot the
    most height.

    For each wrap width, takes the first angle (0 or 90) at which the widest/tallest
    label fits (see _fits), and keeps the combination whose label band
    (w sin a + h cos a) is shortest; ties go to less wrapping.
    `measure(text, fontsize)` returns a label's unrotated (width, height)
    in pixels.
    """
    for size in _FONT_SIZES:
        best = None
        for wrap in _WRAP_WIDTHS:
            labels = [_label(m, show_year, wrap) for m in movies]
            extents = [measure(label, size) for label in labels]
            w = max(e[0] for e in extents)
            h = max(e[1] for e in extents)
            angle = next((a for a in _ANGLES if _fits(w, h, spacing, a)), None)
            if angle is None:
                continue
            band = w * math.sin(math.radians(angle)) + h * math.cos(math.radians(angle))
            if best is None or band < best[0]:
                best = (band, labels, angle)
        if best:
            return best[1], best[2], size
    # Too crowded even upright at the smallest font: accept some overlap.
    return [_label(m, show_year, None) for m in movies], 90, _FONT_SIZES[-1]


def render_chart(movies: list[Movie], size: tuple[float, float]) -> io.BytesIO | None:
    """Two-line chart (worldwide + domestic gross, in $millions) across the
    director's career, drawn at `size` (width, height) in inches. Returns a
    PNG buffer, or None if there's nothing to plot.
    """
    if not movies:
        return None

    # Career timeline left->right; unknown-year films sort to the end.
    movies = by_year(movies)

    worldwide = [m.worldwide_gross / _MILLION for m in movies]
    domestic = [m.domestic_gross / _MILLION for m in movies]

    fig = Figure(figsize=size, dpi=_DPI, layout="constrained")
    canvas = FigureCanvasAgg(fig)
    ax = fig.subplots()
    ax.plot(worldwide, marker="o", label="Worldwide")
    ax.plot(domestic, marker="o", label="Domestic")
    ax.legend()
    ax.set_xticks(range(len(movies)))
    ax.set_title("Box Office Graph")
    ax.set_ylabel("Gross in $Millions")

    # Lay out once to learn the tick spacing in pixels, then pick labels to fit.
    canvas.draw()
    renderer = canvas.get_renderer()
    (x0, _), (x1, _) = ax.transData.transform([(0, 0), (1, 0)])
    spacing = x1 - x0 if len(movies) > 1 else math.inf

    def measure(text: str, fontsize: int) -> tuple[float, float]:
        probe = fig.text(0, 0, text, fontsize=fontsize)
        box = probe.get_window_extent(renderer)
        probe.remove()
        return box.width, box.height

    # Drop the per-tick year once there are many films.
    show_year = len(movies) <= 12
    labels, rotation, fontsize = _choose_labels(movies, show_year, spacing, measure)
    if rotation:
        # Anchor each label's end at its tick, centred across its lines, so
        # slanted and wrapped labels stay attached. Push them down by the
        # upper half of the tallest label so its corner clears the tick mark.
        ax.set_xticklabels(labels, fontsize=fontsize, rotation=rotation,
                           ha="right", va="center", rotation_mode="anchor")
        half = max(measure(label, fontsize)[1] for label in labels) / 2
        lift = half * math.cos(math.radians(rotation)) * 72 / _DPI  # px -> points
        ax.tick_params(axis="x", pad=matplotlib.rcParams["xtick.major.pad"] + lift)
    else:
        ax.set_xticklabels(labels, fontsize=fontsize)

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png")
    buffer.seek(0)
    return buffer
