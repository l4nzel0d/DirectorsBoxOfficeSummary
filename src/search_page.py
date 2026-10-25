"""Render the web app's search page: a name box, an output-format choice and,
when a name is ambiguous, the list of people to pick from.

The browser counterpart of main._choose. It reuses the report page's CSS tokens
(summary.css) so the two look related. Pure: returns a string; app.py does the
routing.
"""

from html import escape
from urllib.parse import quote
from pathlib import Path

from .models import DirectorCandidate

_ASSETS = Path(__file__).parent / "assets"

# Output format -> label shown on the format toggle. The first is the default.
FORMATS = {"html": "Web page", "pdf": "PDF"}

EXAMPLES = ("Christopher Nolan", "Greta Gerwig", "Steven Spielberg")


def _candidate(c: DirectorCandidate, fmt: str) -> str:
    meta = " · ".join(part for part in (c.professions, c.known_for) if part)
    detail = f'<span class="meta">{escape(meta)}</span>' if meta else ""
    return (
        f'<li><a href="/report/{escape(c.id)}.{fmt}">'
        f'<span class="name">{escape(c.name)}</span>{detail}</a></li>'
    )


def render_search_page(
    query: str = "",
    fmt: str = "html",
    message: str = "",
    candidates: list[DirectorCandidate] | None = None,
) -> str:
    """The whole page as a string. `message` is a status line (nothing found,
    several matches, an error); `candidates` are listed as links to the report
    in format `fmt`."""
    css = (_ASSETS / "summary.css").read_text(encoding="utf-8") + (
        _ASSETS / "search.css"
    ).read_text(encoding="utf-8")
    options = "".join(
        f'<label><input type="radio" name="format" value="{value}"{" checked" if value == fmt else ""}>'
        f"<span>{label}</span></label>"
        for value, label in FORMATS.items()
    )
    examples = " ".join(
        f'<a href="/?q={quote(name)}&amp;format={fmt}">{name}</a>' for name in EXAMPLES
    )
    notice = f'<p class="notice" role="status">{escape(message)}</p>' if message else ""
    listing = (
        '<ol class="candidates">' + "".join(_candidate(c, fmt) for c in candidates) + "</ol>"
        if candidates
        else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Box Office Summary</title>
<style>
{css}</style>
</head>
<body>
<main class="search-page">
  <p class="eyebrow">Box Office Summary</p>
  <h1>A director's whole box office career, in one page</h1>
  <p class="lede">Type a film director's name to see their total worldwide gross, the
  domestic and international split, their biggest hits and every film's numbers, with a
  gross-over-time chart. Read it as a web page or save it as a PDF.</p>
  <form class="search" action="/" method="get">
    <input name="q" value="{escape(query, quote=True)}" placeholder="Director's name, or an IMDb id like nm0634240" aria-label="Director's name" autofocus required>
    <div class="segmented" role="radiogroup" aria-label="Output format">{options}</div>
    <button type="submit">Get the report</button>
  </form>
  <p class="try">Try {examples}</p>
  {notice}
  {listing}
</main>
<footer>Data from IMDb · for personal, non-commercial use</footer>
</body>
</html>
"""
