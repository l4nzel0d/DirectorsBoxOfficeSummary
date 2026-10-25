"""Pure tests for the web app: routing, redirects, error pages, report output.
No network: the IMDb-facing functions are replaced with hand-built data."""

import pytest
from fastapi.testclient import TestClient

import app as web
from src.models import Director, DirectorCandidate, Movie

NOLAN = Director(id="nm0634240", name="Christopher Nolan", image_url="https://m.media-amazon.com/images/M/nolan._V1_.jpg")
OPPENHEIMER = Movie(
    id="tt15398776",
    title="Oppenheimer",
    year=2023,
    poster_url="https://m.media-amazon.com/images/M/opp._V1_.jpg",
    domestic_gross=330_078_895,
    worldwide_gross=975_811_333,
)
GERWIG = DirectorCandidate(id="nm1950086", name="Greta Gerwig", professions="Director", is_director=True, rank=500)
OTHER = DirectorCandidate(id="nm1", name="Greta <b>Gerwig</b>", professions="Actress", rank=900)


@pytest.fixture
def client():
    # follow_redirects off, so a test can look at where a search sends you
    return TestClient(web.app, follow_redirects=False)


@pytest.fixture
def imdb(monkeypatch):
    """Nolan is the only known director, with one film; searches find no one."""
    monkeypatch.setattr(web, "search_directors", lambda name: [])
    monkeypatch.setattr(web, "get_director", lambda nm_id: NOLAN if nm_id == NOLAN.id else None)
    monkeypatch.setattr(web, "get_directed_films", lambda nm_id: [OPPENHEIMER])


def test_search_page_has_the_form(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'name="q"' in response.text
    assert '<option value="html" selected>' in response.text


def test_name_id_skips_the_search(client, monkeypatch):
    monkeypatch.setattr(web, "search_directors", lambda name: pytest.fail("searched"))
    response = client.get("/", params={"q": " nm0634240 ", "format": "pdf"})
    assert response.status_code == 303
    assert response.headers["location"] == "/report/nm0634240.pdf"


def test_a_clear_match_redirects_to_the_report(client, monkeypatch):
    monkeypatch.setattr(web, "search_directors", lambda name: [GERWIG, OTHER])
    response = client.get("/", params={"q": "Greta Gerwig"})
    assert response.headers["location"] == "/report/nm1950086.html"


def test_unknown_format_falls_back_to_html(client, monkeypatch):
    monkeypatch.setattr(web, "search_directors", lambda name: [GERWIG])
    response = client.get("/", params={"q": "Greta Gerwig", "format": "docx"})
    assert response.headers["location"] == "/report/nm1950086.html"


def test_ambiguous_name_lists_escaped_candidates(client, monkeypatch):
    twin = DirectorCandidate(id="nm2", name="Greta Gerwig", professions="Director", is_director=True, rank=600)
    monkeypatch.setattr(web, "search_directors", lambda name: [GERWIG, twin, OTHER])
    response = client.get("/", params={"q": "Greta Gerwig", "format": "pdf"})
    assert response.status_code == 200
    assert 'href="/report/nm1950086.pdf"' in response.text
    assert 'href="/report/nm2.pdf"' in response.text
    assert "Greta &lt;b&gt;Gerwig&lt;/b&gt;" in response.text
    assert "<b>" not in response.text


def test_no_match_says_so_and_keeps_the_query(client, imdb):
    response = client.get("/", params={"q": "Nobody <Here>"})
    assert response.status_code == 200
    assert "No one found matching" in response.text
    assert 'value="Nobody &lt;Here&gt;"' in response.text


def test_html_report_links_cdn_thumbnails_and_is_cacheable(client, imdb):
    response = client.get("/report/nm0634240.html")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "s-maxage" in response.headers["cache-control"]
    assert "Christopher Nolan" in response.text
    assert 'src="https://m.media-amazon.com/images/M/opp._V1_QL75_UX400_.jpg"' in response.text
    assert "data:image" not in response.text


def test_pdf_report(client, imdb, monkeypatch):
    # fpdf downloads images itself, so give it none to fetch
    monkeypatch.setattr(web, "get_director", lambda nm_id: Director(id=nm_id, name="Christopher Nolan"))
    monkeypatch.setattr(web, "get_directed_films", lambda nm_id: [Movie(id="tt1", title="Oppenheimer", year=2023, worldwide_gross=975_811_333)])
    response = client.get("/report/nm0634240.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == "inline; filename*=UTF-8''Christopher%20Nolan.pdf"
    assert response.content.startswith(b"%PDF")


@pytest.mark.parametrize("path", ["/report/nm0634240.html", "/report/nm0634240.pdf"])
def test_pdf_and_html_both_fail_on_a_director_without_films(client, imdb, monkeypatch, path):
    monkeypatch.setattr(web, "get_directed_films", lambda nm_id: [])
    response = client.get(path)
    assert response.status_code == 404
    assert "has no released theatrical features" in response.text


def test_unknown_id_is_a_404_page(client, imdb):
    response = client.get("/report/nm9999999.html")
    assert response.status_code == 404
    assert "No one on IMDb with id" in response.text


def test_malformed_id_never_reaches_imdb(client, monkeypatch):
    monkeypatch.setattr(web, "get_director", lambda nm_id: pytest.fail("looked up"))
    response = client.get("/report/not-an-id.html")
    assert response.status_code == 404
    assert "isn&#x27;t an IMDb name id" in response.text


def test_imdb_failure_is_a_502_page(client, monkeypatch):
    def refuse(nm_id):
        raise RuntimeError("IMDb returned 403 (access rules may have changed)")

    monkeypatch.setattr(web, "get_director", refuse)
    response = client.get("/report/nm0634240.html")
    assert response.status_code == 502
    assert "A request to IMDb failed: IMDb returned 403" in response.text


def test_api_docs_are_not_exposed(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
