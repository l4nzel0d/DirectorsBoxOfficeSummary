"""Render the web app's search page: a name box, an output-format choice and,
when a name is ambiguous, the list of people to pick from.

The browser counterpart of main._choose. It reuses the report page's CSS tokens
(summary.css) so the two look related. Pure: returns a string; app.py does the
routing.
"""

from html import escape
from pathlib import Path

from .models import DirectorCandidate

_ASSETS = Path(__file__).parent / "assets"

# Output format -> label shown in the dropdown. The first is the default.
FORMATS = {"html": "Web page", "pdf": "PDF"}


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
        f'<option value="{value}"{" selected" if value == fmt else ""}>{label}</option>'
        for value, label in FORMATS.items()
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
  <h1>Which director?</h1>
  <form class="search" action="/" method="get">
    <input name="q" value="{escape(query, quote=True)}" placeholder="Full name, or an IMDb id like nm0634240" aria-label="Director's name" autofocus required>
    <select name="format" aria-label="Output format">{options}</select>
    <button type="submit">Look up</button>
  </form>
  {notice}
  {listing}
</main>
<footer>Data from IMDb · for personal, non-commercial use</footer>
</body>
</html>
"""
