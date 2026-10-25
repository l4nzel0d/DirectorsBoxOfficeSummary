"""Web entry point: the Box Office Summary over HTTP, for hosting (Vercel
auto-detects `app` in this file).

    .venv/bin/uvicorn app:app --reload

The sibling of main.py: it owns the request/response I/O so the src/ modules
stay side-effect free. Routes:

    /                        search page; a name redirects to the report, an
                             ambiguous one lists the candidates
    /report/<nm id>.html     the HTML page
    /report/<nm id>.pdf      the PDF

Unlike the CLI's single-file HTML, the web page links its images straight to
the IMDb CDN (as thumbnails) instead of embedding them, which saves the image
downloads and keeps the response small. IMDb's data may only be used
privately, so keep the deployment private (see CLAUDE.md).
"""

import os
import re
from contextlib import contextmanager
from urllib.parse import quote

# Vercel's filesystem is read-only except /tmp, and matplotlib needs a writable
# config/cache dir. Must be set before anything imports matplotlib (src.pdf).
if os.environ.get("VERCEL"):
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from src.html_page import make_html
from src.images import thumbnail_url
from src.models import Director, Movie
from src.movies import get_director, get_directed_films, pick_director, search_directors
from src.pdf import make_pdf
from src.search_page import FORMATS, render_search_page

NAME_ID = re.compile(r"^nm\d+$")
MAX_CHOICES = 5
IMAGE_WIDTH = 400  # px; the CDN resizes, so a poster costs tens of KB

# Let the CDN serve repeat reports without asking IMDb again.
CACHE = {"Cache-Control": "public, max-age=300, s-maxage=86400, stale-while-revalidate=604800"}

# No /docs or /openapi.json: nothing here is meant to be browsed as an API.
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


class PageError(Exception):
    """A problem to show on the search page with this HTTP status."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


@app.exception_handler(PageError)
def _page_error(request: Request, exc: PageError) -> HTMLResponse:
    return HTMLResponse(render_search_page(message=exc.message), status_code=exc.status_code)


@contextmanager
def _upstream():
    """Turn a failed request to IMDb (RuntimeError from src.imdb_api, a
    network or HTTP error, a poster fpdf couldn't download) into a 502 page
    instead of a bare server error."""
    try:
        yield
    except (RuntimeError, OSError) as exc:
        raise PageError(502, f"A request to IMDb failed: {exc}") from exc


def _load(nm_id: str) -> tuple[Director, list[Movie]]:
    """The director and their released features, or a PageError."""
    if not NAME_ID.match(nm_id):
        raise PageError(404, f"{nm_id!r} isn't an IMDb name id (like nm0634240).")
    with _upstream():
        director = get_director(nm_id)
        films = get_directed_films(director.id) if director else []
    if director is None:
        raise PageError(404, f"No one on IMDb with id {nm_id!r}.")
    if not films:
        raise PageError(404, f"{director.name} has no released theatrical features with box-office data.")
    return director, films


@app.get("/")
def search(q: str = "", fmt: str = Query("html", alias="format")) -> Response:
    fmt = fmt if fmt in FORMATS else "html"
    query = q.strip()
    if not query:
        return HTMLResponse(render_search_page(fmt=fmt))
    if NAME_ID.match(query):
        return RedirectResponse(f"/report/{query}.{fmt}", status_code=303)

    with _upstream():
        candidates = search_directors(query)
    if not candidates:
        return HTMLResponse(render_search_page(query, fmt, f"No one found matching {query!r}."))
    choice = pick_director(query, candidates)
    if choice is not None:
        return RedirectResponse(f"/report/{choice.id}.{fmt}", status_code=303)
    return HTMLResponse(
        render_search_page(query, fmt, "Several people match. Which one?", candidates[:MAX_CHOICES])
    )


@app.get("/report/{nm_id}.html")
def report_html(nm_id: str) -> Response:
    director, films = _load(nm_id)
    urls = [director.image_url, *(film.poster_url for film in films)]
    images = {url: thumbnail_url(url, IMAGE_WIDTH) for url in urls if url}
    return HTMLResponse(make_html(director, films, images), headers=CACHE)


@app.get("/report/{nm_id}.pdf")
def report_pdf(nm_id: str) -> Response:
    director, films = _load(nm_id)
    with _upstream():  # fpdf downloads the posters while building
        content = bytes(make_pdf(director, films).output())
    # filename* carries the name percent-encoded, so accents survive in the header.
    disposition = f"inline; filename*=UTF-8''{quote(director.name)}.pdf"
    return Response(content, media_type="application/pdf", headers={**CACHE, "Content-Disposition": disposition})
