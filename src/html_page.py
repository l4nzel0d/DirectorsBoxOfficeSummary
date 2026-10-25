"""Render the Box Office Summary as one self-contained HTML page.

The browser counterpart of pdf.py: the same Director + list[Movie] and the
same aggregates/selectors, but designed for a screen rather than ported from
A4 — a hero with the headline total, stat tiles, highlight cards, an inline
SVG career chart (svg_chart) and a sortable filmography table. CSS and JS are
inlined from assets/, and images arrive as data URIs (images.fetch_data_uris),
so the result is a single file that works offline. Pure: returns a string.
"""

from html import escape
from pathlib import Path

from . import movies
from .favicon import FAVICON_LINK
from .formatting import money, money_short
from .models import Director, Movie
from .svg_chart import render_svg_chart

_ASSETS = Path(__file__).parent / "assets"

# (label, selector, the amount it ranks by). "Openning" is the project's spelling.
_HIGHLIGHTS = (
    ("Highest Grossing Worldwide", movies.top_by_worldwide, lambda m: m.worldwide_gross),
    ("Highest Grossing Domestically", movies.top_by_domestic, lambda m: m.domestic_gross),
    ("Biggest Domestic Openning", movies.top_by_opening, lambda m: m.opening_weekend),
)

# Filmography columns: (header, data-type, first sort direction on click).
_COLUMNS = (
    ("#", "num", "ascending"),
    ("Film", "text", "ascending"),
    ("Year", "num", "ascending"),
    ("Budget", "num", "descending"),
    ("Openning weekend", "num", "descending"),
    ("Domestic", "num", "descending"),
    ("Worldwide", "num", "descending"),
)


def _initials(name: str) -> str:
    return "".join(word[0] for word in name.split()[:2]).upper()


def _portrait(director: Director, images: dict[str, str]) -> str:
    src = images.get(director.image_url)
    if src:
        return f'<img class="portrait" src="{src}" alt="{escape(director.name)}">'
    return f'<div class="portrait placeholder" aria-hidden="true">{escape(_initials(director.name))}</div>'


def _poster(movie: Movie, images: dict[str, str], cls: str) -> str:
    """The poster image (decorative: the title is always next to it), or an
    empty tile of the same shape."""
    src = images.get(movie.poster_url)
    if src:
        return f'<img class="{cls}" src="{src}" alt="" loading="lazy">'
    return f'<div class="{cls} placeholder" aria-hidden="true"></div>'


def _segments(domestic_share: float) -> str:
    """Domestic + international segments of a worldwide bar; a zero-width
    segment is left out so no stray gap shows."""
    share = min(max(domestic_share, 0.0), 1.0)
    return "".join(
        f'<span class="seg {name}" style="flex-grow:{grow:.4f}"></span>'
        for name, grow in (("domestic", share), ("international", 1 - share))
        if grow > 0
    )


def _span(films: list[Movie]) -> str:
    years = [m.year for m in films if m.year is not None]
    if not years:
        return ""
    first, last = min(years), max(years)
    return str(first) if first == last else f"{first}–{last}"


def _hero(director: Director, films: list[Movie], images: dict[str, str]) -> str:
    total = movies.total_worldwide(films)
    count = f"{len(films)} feature film{'' if len(films) == 1 else 's'}"
    exact = f"{money(total)} across {count}" if total else count
    return f"""
<header class="hero">
  {_portrait(director, images)}
  <div class="hero-text">
    <p class="eyebrow">Box Office Summary</p>
    <h1>{escape(director.name)}</h1>
    <p class="role">as Director</p>
    <p class="hero-figure">{money_short(total)}</p>
    <p class="hero-caption">Total worldwide box office · {exact}</p>
  </div>
</header>"""


def _tile(label: str, value: str, detail: str) -> str:
    detail_html = f'<p class="tile-detail">{detail}</p>' if detail else ""
    return f'<div class="tile"><p class="tile-label">{label}</p><p class="tile-value">{value}</p>{detail_html}</div>'


def _stats(films: list[Movie]) -> str:
    worldwide = movies.total_worldwide(films)
    domestic = movies.total_domestic(films)
    international = movies.total_international(films)
    tiles = (
        _tile("Domestic box office", money_short(domestic), money(domestic) if domestic else "")
        + _tile("International box office", money_short(international), money(international) if international else "")
        + _tile("Feature films", str(len(films)), _span(films))
    )
    split = ""
    if worldwide > 0:
        dom_pct = round(min(max(domestic / worldwide, 0), 1) * 100)
        split = f"""
  <div class="split" role="img" aria-label="Domestic {dom_pct}%, international {100 - dom_pct}% of worldwide box office">
    <div class="split-bar">{_segments(domestic / worldwide)}</div>
    <div class="split-legend">
      <span><i class="key domestic"></i>Domestic <b>{dom_pct}%</b></span>
      <span><i class="key international"></i>International <b>{100 - dom_pct}%</b></span>
    </div>
  </div>"""
    return f"""
<section class="stats">
  <div class="tiles">{tiles}</div>{split}
</section>"""


def _highlights(films: list[Movie], images: dict[str, str]) -> str:
    cards = []
    for label, select, amount_of in _HIGHLIGHTS:
        movie = select(films)
        amount = amount_of(movie) if movie else 0
        if not amount:  # e.g. no film has opening-weekend data
            continue
        year = f'<p class="year">{movie.year}</p>' if movie.year else ""
        cards.append(f"""
  <article class="highlight">
    {_poster(movie, images, "poster")}
    <div>
      <p class="eyebrow">{label}</p>
      <h3>{escape(movie.title)}</h3>{year}
      <p class="highlight-value" title="{money(amount)}">{money_short(amount)}</p>
    </div>
  </article>""")
    if not cards:
        return ""
    return f"""
<section>
  <h2>Highlights</h2>
  <div class="highlights">{"".join(cards)}
  </div>
</section>"""


def _chart(films: list[Movie]) -> str:
    svg = render_svg_chart(films)
    if svg is None:
        return ""
    return f"""
<section class="card">
  <div class="card-head">
    <h2>Box office over career</h2>
    <div class="legend">
      <span><i class="line-key worldwide"></i>Worldwide</span>
      <span><i class="line-key domestic"></i>Domestic</span>
    </div>
  </div>
  <div class="chart"><div class="chart-inner">{svg}<div class="tooltip" hidden></div></div></div>
</section>"""


def _money_cell(amount: int) -> str:
    if not amount:
        return '<td class="num none" data-sort="">-</td>'
    return f'<td class="num" data-sort="{amount}">{money(amount)}</td>'


def _row(rank: int, movie: Movie, peak: int, images: dict[str, str]) -> str:
    worldwide = movie.worldwide_gross
    if worldwide:
        # The bar's track has the same width in every row, so lengths compare.
        bar = (
            f'<span class="track"><span class="bar" style="width:{worldwide / peak * 100:.1f}%">'
            f"{_segments(movie.domestic_gross / worldwide)}</span></span>"
        )
        gross = (
            f'<td class="num gross" data-sort="{worldwide}">'
            f'<div class="gross-cell">{bar}<span class="amount">{money(worldwide)}</span></div></td>'
        )
    else:
        gross = '<td class="num gross none" data-sort="">-</td>'
    year = movie.year if movie.year is not None else ""
    return f"""
    <tr data-rank="{rank}">
      <td class="num rank" data-sort="{rank}">{rank}</td>
      <td data-sort="{escape(movie.title.casefold())}"><div class="film">{_poster(movie, images, "thumb")}<span>{escape(movie.title)}</span></div></td>
      <td class="num{"" if year else " none"}" data-sort="{year}">{year or "-"}</td>
      {_money_cell(movie.budget)}{_money_cell(movie.opening_weekend)}{_money_cell(movie.domestic_gross)}{gross}
    </tr>"""


def _table(films: list[Movie], images: dict[str, str]) -> str:
    if not films:
        return ""
    peak = max(m.worldwide_gross for m in films)
    headers = ""
    for label, kind, first in _COLUMNS:
        # Rows start in rank order, so "#" starts out marked as the sorted column.
        sort = ' aria-sort="ascending"' if label == "#" else ""
        headers += (
            f'<th scope="col" class="{kind}" data-type="{kind}" data-first="{first}"{sort}>'
            f'<button type="button">{label}</button></th>'
        )
    rows = "".join(_row(rank, movie, peak, images) for rank, movie in enumerate(films, start=1))
    return f"""
<section class="card">
  <div class="card-head">
    <h2>Filmography</h2>
    <p class="hint">Ranked by worldwide gross · select a column to sort</p>
  </div>
  <div class="table-wrap">
    <table class="films">
      <thead><tr>{headers}</tr></thead>
      <tbody>{rows}
      </tbody>
    </table>
  </div>
</section>"""


def make_html(director: Director, films: list[Movie], images: dict[str, str] | None = None) -> str:
    """The whole page as a string. `images` maps an image URL (portrait or
    poster) to its data URI; a URL that's missing gets a placeholder."""
    images = images or {}
    ordered = movies.by_worldwide_desc(films)
    css = (_ASSETS / "summary.css").read_text(encoding="utf-8")
    js = (_ASSETS / "summary.js").read_text(encoding="utf-8")
    body = (
        _hero(director, ordered, images)
        + _stats(ordered)
        + _highlights(ordered, images)
        + _chart(ordered)
        + _table(ordered, images)
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
{FAVICON_LINK}
<title>{escape(director.name)} · Box Office Summary</title>
<style>
{css}</style>
</head>
<body>
<main>{body}
</main>
<footer>Data from IMDb · for personal, non-commercial use</footer>
<script>
{js}</script>
</body>
</html>
"""
