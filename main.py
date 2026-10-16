"""Interactive entry point: prompt for a director, write their Box Office Summary
as a PDF, an HTML page, or both.

    python main.py

Wires the layers together — movies (data) -> pdf / html_page (render) -> disk —
and keeps all stdin/stdout and file I/O here, so the src/ modules stay
side-effect free.

The director is looked up by name on IMDb (GraphQL, no key needed), and all
the data comes from there too. Typing an IMDb name id directly (e.g.
nm0634240) skips the name search.
"""

import re
from pathlib import Path

from src.html_page import make_html
from src.images import fetch_data_uris
from src.models import Director, Movie
from src.movies import (
    DirectorCandidate,
    get_director,
    get_directed_films,
    pick_director,
    search_directors,
)
from src.pdf import make_pdf

OUTPUT_DIR = Path("output")
NAME_ID = re.compile(r"^nm\d+$")
MAX_CHOICES = 5
# Answer (or its first letter) -> formats to write. Blank means PDF.
FORMATS = {"pdf": ("pdf",), "html": ("html",), "both": ("pdf", "html")}


def _choose(candidates: list[DirectorCandidate]) -> DirectorCandidate | None:
    """Show a numbered list and let the user pick one; blank input cancels."""
    print("Several people match:")
    for i, c in enumerate(candidates, 1):
        professions = f" ({c.professions})" if c.professions else ""
        known = f" - {c.known_for}" if c.known_for else ""
        print(f"  {i}. {c.name}{professions}{known}")
    while True:
        answer = input(f"Which one? [1-{len(candidates)}, blank to cancel]: ").strip()
        if not answer:
            return None
        if answer.isdigit() and 1 <= int(answer) <= len(candidates):
            return candidates[int(answer) - 1]
        print(f"Please enter a number from 1 to {len(candidates)}.")


def _choose_format() -> tuple[str, ...]:
    """Ask which output(s) to write; blank means PDF."""
    while True:
        answer = input("Output format [pdf/html/both] (pdf): ").strip().lower() or "pdf"
        for name, formats in FORMATS.items():
            if answer in (name, name[0]):
                return formats
        print("Please enter pdf, html or both.")


def _write_pdf(director: Director, films: list[Movie]) -> None:
    print("Building PDF...")
    pdf = make_pdf(director, films)
    out_path = OUTPUT_DIR / f"{director.name}.pdf"
    pdf.output(str(out_path))
    print(f"Saved {out_path}")


def _write_html(director: Director, films: list[Movie]) -> None:
    urls = [director.image_url, *(film.poster_url for film in films)]
    print(f"Downloading {sum(1 for url in urls if url)} image(s)...")
    images = fetch_data_uris(urls)
    out_path = OUTPUT_DIR / f"{director.name}.html"
    out_path.write_text(make_html(director, films, images), encoding="utf-8")
    print(f"Saved {out_path}")


def main() -> None:
    query = input("Director's full name: ").strip()
    if not query:
        return

    if NAME_ID.match(query):
        name_id = query
    else:
        candidates = search_directors(query)
        if not candidates:
            print(f"No one found matching {query!r}.")
            return
        choice = pick_director(query, candidates) or _choose(candidates[:MAX_CHOICES])
        if choice is None:
            return
        name_id = choice.id

    director = get_director(name_id)
    if director is None:
        print(f"No one on IMDb with id {name_id!r}.")
        return
    print(f"Found {director.name} ({director.id}). Fetching filmography...")

    films = get_directed_films(director.id)
    if not films:
        print(f"{director.name} has no released theatrical features with box-office data.")
        return
    print(f"{len(films)} film(s).")

    formats = _choose_format()
    OUTPUT_DIR.mkdir(exist_ok=True)
    if "pdf" in formats:
        _write_pdf(director, films)
    if "html" in formats:
        _write_html(director, films)


if __name__ == "__main__":
    main()
