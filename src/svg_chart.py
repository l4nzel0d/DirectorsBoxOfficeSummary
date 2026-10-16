"""Render a director's box-office-over-career chart as an inline SVG string.

The HTML counterpart of chart.py: worldwide and domestic gross per film, in
career order, evenly spaced. Instead of fitting title tick labels (chart.py's
hard part), the x axis shows years and every film's column carries its title
and figures for a hover/focus tooltip, which assets/summary.js wires up.
Colours come from CSS classes, so the chart follows the page's light/dark
theme. The SVG scales to its container through its viewBox.
"""

import math
from html import escape

from .formatting import money_short
from .models import Movie
from .movies import by_year

WIDTH, HEIGHT = 900, 360  # viewBox units (~px at desktop width)
LEFT, RIGHT, TOP, BOTTOM = 56, 12, 16, 32  # plot margins
_MIN_LABEL_GAP = 44  # year labels closer than this are skipped
_EMPTY_SCALE = 1_000_000  # y range when no film has any gross


def _nice_step(raw: float) -> int:
    """Round a raw tick step up to 1, 2, 2.5 or 5 x 10^k (raw >= 10, so the
    step is always a whole number of dollars)."""
    exponent = math.floor(math.log10(raw))
    fraction = raw / 10**exponent
    return int(next(n for n in (1, 2, 2.5, 5, 10) if fraction <= n) * 10**exponent)


def _tick_label(value: int) -> str:
    """Axis label without trailing zeros: $0, $200M, $1.5B, $50K."""
    for size, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if value >= size:
            return f"${value / size:g}{suffix}"
    return f"${value:,}"


def _f(value: float) -> str:
    return f"{value:.1f}"


def _series(points: list[tuple[float, float]], name: str, baseline: float, area: bool) -> list[str]:
    """One series: optional area wash, a 2px line through the known points
    (bridging films with no data) and a dot per point."""
    if not points:
        return []
    coords = " ".join(f"{_f(x)},{_f(y)}" for x, y in points)
    parts = []
    if area and len(points) > 1:
        (x0, _), (x1, _) = points[0], points[-1]
        parts.append(
            f'<polygon class="area {name}" '
            f'points="{_f(x0)},{_f(baseline)} {coords} {_f(x1)},{_f(baseline)}"/>'
        )
    if len(points) > 1:
        parts.append(f'<polyline class="line {name}" points="{coords}"/>')
    parts.extend(f'<circle class="dot {name}" cx="{_f(x)}" cy="{_f(y)}" r="5"/>' for x, y in points)
    return parts


def render_svg_chart(movies: list[Movie]) -> str | None:
    """Two-line SVG chart (worldwide + domestic gross) across the director's
    career, or None if there's nothing to plot. Films with no gross (0) get no
    point; their column still has a year label and a tooltip."""
    if not movies:
        return None
    films = by_year(movies)

    peak = max(max(m.worldwide_gross, m.domestic_gross) for m in films) or _EMPTY_SCALE
    step = _nice_step(max(peak / 5, 10))
    top = step * math.ceil(peak / step)
    plot_w, plot_h = WIDTH - LEFT - RIGHT, HEIGHT - TOP - BOTTOM
    baseline = TOP + plot_h
    slot = plot_w / len(films)

    def x(i: int) -> float:
        return LEFT + (i + 0.5) * slot

    def y(value: int) -> float:
        return TOP + plot_h * (1 - value / top)

    parts = []
    for tick in range(0, top + 1, step):
        parts.append(
            f'<line class="{"axis" if tick == 0 else "grid"}" x1="{LEFT}" x2="{WIDTH - RIGHT}" '
            f'y1="{_f(y(tick))}" y2="{_f(y(tick))}"/>'
        )
        parts.append(
            f'<text class="tick" x="{LEFT - 8}" y="{_f(y(tick))}" dy="0.32em" '
            f'text-anchor="end">{_tick_label(tick)}</text>'
        )

    # One year label per distinct year, skipping any that would crowd the last.
    last_x, last_year = -math.inf, None
    for i, film in enumerate(films):
        if film.year is None or film.year == last_year or x(i) - last_x < _MIN_LABEL_GAP:
            continue
        parts.append(
            f'<text class="tick" x="{_f(x(i))}" y="{baseline + 20}" '
            f'text-anchor="middle">{film.year}</text>'
        )
        last_x, last_year = x(i), film.year

    parts.append(f'<line class="crosshair" x1="0" x2="0" y1="{TOP}" y2="{baseline}"/>')
    for attr, name, area in (("worldwide_gross", "worldwide", True), ("domestic_gross", "domestic", False)):
        points = [(x(i), y(getattr(f, attr))) for i, f in enumerate(films) if getattr(f, attr)]
        parts.extend(_series(points, name, baseline, area))

    # Transparent full-height columns: the hover/focus targets for the tooltip.
    for i, film in enumerate(films):
        year = str(film.year) if film.year is not None else ""
        ww, dom = money_short(film.worldwide_gross), money_short(film.domestic_gross)
        summary = f"{film.title}{f' ({year})' if year else ''}: worldwide {ww}, domestic {dom}"
        parts.append(
            f'<rect class="hit" x="{_f(LEFT + i * slot)}" y="{TOP}" width="{_f(slot)}" '
            f'height="{plot_h}" tabindex="0" data-x="{_f(x(i))}" '
            f'data-title="{escape(film.title)}" data-year="{year}" data-ww="{ww}" '
            f'data-dom="{dom}" aria-label="{escape(summary)}"><title>{escape(summary)}</title></rect>'
        )

    years = [f.year for f in films if f.year is not None]
    span = f", {min(years)}–{max(years)}" if years else ""
    label = f"Worldwide and domestic gross of {len(films)} films{span}"
    return (
        f'<svg class="career" viewBox="0 0 {WIDTH} {HEIGHT}" aria-label="{escape(label)}">'
        + "".join(parts)
        + "</svg>"
    )
