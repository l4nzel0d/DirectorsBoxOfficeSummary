"""Tests for src/movies.py — the domain layer.

Three layers:
  1. Pure unit tests for the helpers (no network, no mocking).
  2. Unit tests for find_director / get_directed_films with imdb_api mocked
     at the module boundary (monkeypatch).
  3. Opt-in integration tests against the live API (run with --integration).
"""

import json
from pathlib import Path

import pytest

from src import imdb_api, movies
from src.movies import (
    Director,
    Movie,
    _amount,
    _bare_title_id,
    _build_movie,
    _opening_weekend,
    find_director,
    get_directed_films,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text())


# --------------------------------------------------------------------------- #
# Layer 1: pure helpers
# --------------------------------------------------------------------------- #


class TestBareTitleId:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("/title/tt15398776/", "tt15398776"),
            ("/title/tt0154506/", "tt0154506"),
            ("/title/tt0000001", "tt0000001"),  # no trailing slash
            ("tt0000001", "tt0000001"),  # already bare
        ],
    )
    def test_strips_wrapper(self, raw, expected):
        assert _bare_title_id(raw) == expected

    def test_unmatched_passes_through(self):
        assert _bare_title_id("garbage") == "garbage"


class TestAmount:
    def test_reads_nested_money(self):
        node = {"total": {"amount": 5, "currency": "USD"}}
        assert _amount(node, "total") == 5

    def test_budget_shape(self):
        node = {"budget": {"totalBudget": {"amount": 90, "currency": "USD"}}}
        assert _amount(node, "budget", "totalBudget") == 90

    def test_missing_intermediate_key_is_zero(self):
        assert _amount({"total": {}}, "total", "nope") == 0

    def test_none_node_is_zero(self):
        # mirrors Rebel Moon's "domesticGross": null
        assert _amount({"domesticGross": None}, "domesticGross", "total") == 0

    def test_no_amount_key_is_zero(self):
        assert _amount({"total": {"currency": "USD"}}, "total") == 0

    def test_float_amount_coerced_to_int(self):
        assert _amount({"total": {"amount": 12.0}}, "total") == 12
        assert isinstance(_amount({"total": {"amount": 12.0}}, "total"), int)

    def test_non_dict_midway_is_zero(self):
        assert _amount({"total": 7}, "total", "amount") == 0

    def test_empty_dict_is_zero(self):
        assert _amount({}, "anything") == 0


class TestOpeningWeekend:
    def test_normal_edge(self):
        box = {
            "openingWeekendGrosses": {
                "edges": [{"node": {"gross": {"total": {"amount": 28_638_131}}}}]
            }
        }
        assert _opening_weekend(box) == 28_638_131

    def test_empty_edges_is_zero(self):
        assert _opening_weekend({"openingWeekendGrosses": {"edges": []}}) == 0

    def test_missing_key_is_zero(self):
        assert _opening_weekend({}) == 0

    def test_none_value_is_zero(self):
        assert _opening_weekend({"openingWeekendGrosses": None}) == 0


class TestBuildMovie:
    def test_full_film_and_box(self):
        film = {
            "id": "/title/tt15398776/",
            "title": "Oppenheimer",
            "year": 2023,
            "image": {"url": "http://img/opp.jpg"},
        }
        box = load_fixture("box_office_oppenheimer.json")
        movie = _build_movie(film, box)
        assert movie.id == "tt15398776"  # stripped
        assert movie.title == "Oppenheimer"
        assert movie.year == 2023
        assert movie.poster_url == "http://img/opp.jpg"
        assert movie.budget == 100_000_000
        assert movie.domestic_gross == 330_078_895
        assert movie.worldwide_gross == 975_811_333
        assert movie.opening_weekend > 0

    def test_following_has_zero_opening(self):
        film = {"id": "/title/tt0154506/", "title": "Following", "year": 1998}
        box = load_fixture("box_office_following.json")
        movie = _build_movie(film, box)
        assert movie.worldwide_gross > 0
        assert movie.opening_weekend == 0  # empty edges

    def test_rebel_moon_has_zero_grosses(self):
        film = {"id": "/title/tt14998742/", "title": "Rebel Moon", "year": 2023}
        box = load_fixture("box_office_rebel_moon.json")
        movie = _build_movie(film, box)
        assert movie.budget == 90_000_000
        assert movie.domestic_gross == 0  # null in fixture
        assert movie.worldwide_gross == 0
        assert movie.opening_weekend == 0

    def test_missing_image_and_year(self):
        film = {"id": "/title/tt0000002/", "title": "Kept Two"}
        movie = _build_movie(film, {})
        assert movie.year is None
        assert movie.poster_url is None
        assert movie.budget == movie.domestic_gross == movie.worldwide_gross == 0


# --------------------------------------------------------------------------- #
# Layer 2: find_director / get_directed_films with imdb_api mocked
# --------------------------------------------------------------------------- #


class TestFindDirector:
    def test_picks_top_candidate(self, monkeypatch):
        candidates = [
            {"id": "nm0634240", "l": "Christopher Nolan", "i": {"imageUrl": "http://p.jpg"}},
            {"id": "nm9999999", "l": "Someone Else"},
        ]
        monkeypatch.setattr(imdb_api, "search_director", lambda q: candidates)
        d = find_director("Nolan")
        assert d == Director(id="nm0634240", name="Christopher Nolan", image_url="http://p.jpg")

    def test_candidate_without_image(self, monkeypatch):
        monkeypatch.setattr(
            imdb_api, "search_director", lambda q: [{"id": "nm1", "l": "No Image"}]
        )
        d = find_director("whoever")
        assert d.image_url is None

    def test_empty_results_returns_none(self, monkeypatch):
        monkeypatch.setattr(imdb_api, "search_director", lambda q: [])
        assert find_director("nobody") is None

    def test_passes_query_through(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(
            imdb_api, "search_director", lambda q: seen.update(q=q) or [{"id": "nm1", "l": "X"}]
        )
        find_director("Greta Gerwig")
        assert seen["q"] == "Greta Gerwig"


class TestGetDirectedFilms:
    def _stub_box(self, monkeypatch, box=None):
        """Record each tconst get_box_office is called with; return `box`."""
        calls = []

        def fake(tconst):
            calls.append(tconst)
            return box if box is not None else {}

        monkeypatch.setattr(imdb_api, "get_box_office", fake)
        return calls

    def test_filters_to_directed_released_movies(self, monkeypatch):
        monkeypatch.setattr(
            imdb_api, "get_filmography", lambda nconst: load_fixture("filmography_mixed.json")
        )
        calls = self._stub_box(monkeypatch)
        result = get_directed_films("nm_any")
        # Only the two director/released/movie rows survive.
        assert [m.title for m in result] == ["Kept One", "Kept Two No Year No Image"]
        # ...and box office was fetched once per kept film, with stripped ids, in order.
        assert calls == ["tt0000001", "tt0000002"]

    def test_preserves_filmography_order(self, monkeypatch):
        monkeypatch.setattr(
            imdb_api, "get_filmography", lambda nconst: load_fixture("filmography_mixed.json")
        )
        self._stub_box(monkeypatch)
        result = get_directed_films("nm_any")
        assert [m.id for m in result] == ["tt0000001", "tt0000002"]

    def test_keeps_zero_gross_films(self, monkeypatch):
        # decision: zero-gross films are NOT dropped
        film = {
            "category": "director",
            "status": "released",
            "titleType": "movie",
            "id": "/title/tt14998742/",
            "title": "Rebel Moon",
            "year": 2023,
        }
        monkeypatch.setattr(imdb_api, "get_filmography", lambda nconst: [film])
        self._stub_box(monkeypatch, box=load_fixture("box_office_rebel_moon.json"))
        result = get_directed_films("nm_any")
        assert len(result) == 1
        assert result[0].worldwide_gross == 0
        assert result[0].domestic_gross == 0

    def test_empty_filmography(self, monkeypatch):
        monkeypatch.setattr(imdb_api, "get_filmography", lambda nconst: [])
        self._stub_box(monkeypatch)
        assert get_directed_films("nm_any") == []

    def test_no_directed_films(self, monkeypatch):
        only_acting = [
            {"category": "actor", "status": "released", "titleType": "movie",
             "id": "/title/tt1/", "title": "Acted"}
        ]
        monkeypatch.setattr(imdb_api, "get_filmography", lambda nconst: only_acting)
        calls = self._stub_box(monkeypatch)
        assert get_directed_films("nm_any") == []
        assert calls == []  # no box-office calls when nothing qualifies

    def test_fail_fast_propagates(self, monkeypatch):
        film = {
            "category": "director", "status": "released", "titleType": "movie",
            "id": "/title/tt1/", "title": "Boom",
        }
        monkeypatch.setattr(imdb_api, "get_filmography", lambda nconst: [film])

        def boom(tconst):
            raise RuntimeError("network down")

        monkeypatch.setattr(imdb_api, "get_box_office", boom)
        with pytest.raises(RuntimeError, match="network down"):
            get_directed_films("nm_any")


# --------------------------------------------------------------------------- #
# Layer 3: integration (live API) — run with: pytest --integration
# --------------------------------------------------------------------------- #


@pytest.mark.integration
class TestLiveAPI:
    @pytest.mark.parametrize(
        "query, expected_id",
        [
            ("Christopher Nolan", "nm0634240"),
            ("Greta Gerwig", "nm1950086"),
        ],
    )
    def test_find_director_resolves_known_ids(self, query, expected_id):
        assert find_director(query).id == expected_id

    def test_find_director_peele(self):
        d = find_director("Jordan Peele")
        assert d is not None
        assert d.name == "Jordan Peele"
        assert d.id.startswith("nm")

    @pytest.mark.parametrize(
        "director_id, expected_count",
        [
            ("nm0634240", 12),  # Nolan
            ("nm1950086", 4),   # Gerwig
            ("nm10533874", 2),  # Curry Barker
        ],
    )
    def test_directed_film_counts(self, director_id, expected_count):
        films = get_directed_films(director_id)
        assert len(films) == expected_count
        # every film is well-formed: titled, int money fields
        for m in films:
            assert m.title
            assert all(
                isinstance(v, int)
                for v in (m.budget, m.domestic_gross, m.worldwide_gross, m.opening_weekend)
            )

    def test_following_has_zero_opening_in_context(self):
        films = get_directed_films("nm0634240")
        following = next(m for m in films if m.id == "tt0154506")
        assert following.opening_weekend == 0
        assert following.worldwide_gross > 0
