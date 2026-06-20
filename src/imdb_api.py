"""Thin client over the imdb8 RapidAPI endpoints.

Each function makes one HTTP call and returns the parsed JSON (or a small
slice of it). Shaping/normalizing the data lives elsewhere — this module is
only responsible for talking to the API.
"""

import time

import requests

from . import config

BASE_URL = f"https://{config.RAPIDAPI_HOST}"
TIMEOUT = 30

# The RapidAPI host occasionally drops connections or throttles; retry a few
# times with exponential backoff so one transient blip doesn't abort a run
# that makes a dozen+ sequential calls.
MAX_RETRIES = 4
BACKOFF_BASE = 1.0  # seconds: waits 1, 2, 4 ... between attempts
RETRY_STATUSES = {429, 500, 502, 503, 504}


def _get(path: str, params: dict) -> dict:
    url = f"{BASE_URL}{path}"
    for attempt in range(MAX_RETRIES):
        last_attempt = attempt == MAX_RETRIES - 1
        try:
            response = requests.get(
                url,
                headers=config.headers(),
                params=params,
                timeout=TIMEOUT,
            )
        except (requests.ConnectionError, requests.Timeout):
            if last_attempt:
                raise
        else:
            # Retry transient server/throttle statuses; let everything else
            # (success or a real 4xx) fall through to raise_for_status/return.
            if not (response.status_code in RETRY_STATUSES and not last_attempt):
                response.raise_for_status()
                return response.json()

        time.sleep(BACKOFF_BASE * 2**attempt)

    # Unreachable: the loop either returns or raises on the last attempt.
    raise RuntimeError("retry loop exited without returning")


def search_director(query: str) -> list[dict]:
    """Search people/titles by name via /auto-complete.

    Returns the raw `d` list of candidates. Each candidate has:
      - id: the IMDb id (e.g. "nm0634240" for a person)
      - l:  display name/label
      - i:  image dict ({imageUrl, height, width}) — may be absent
      - s:  subtitle string (e.g. "Producer, Tenet (2020)")
    """
    data = _get("/auto-complete", {"q": query})
    return data.get("d", [])


def get_filmography(director_id: str) -> list[dict]:
    """List a person's titles via /actors/get-all-filmography.

    `director_id` is a bare IMDb person id (e.g. "nm0634240"), exactly as
    returned by search_director. Returns the raw `filmography` list; each
    entry has:
      - category:  the person's role (e.g. "director", "actor")
      - id:        the title id, wrapped as "/title/tt.../"
      - title:     display title
      - titleType: "movie", "tvSeries", ...
      - status:    "released", "pre production", ...
      - year:      release year (may be absent)
      - image:     poster dict ({url, height, width}) (may be absent)
    """
    data = _get("/actors/get-all-filmography", {"nconst": director_id})
    return data.get("filmography", [])


def get_box_office(title_id: str) -> dict:
    """Fetch budget + gross for a title via /title/v2/get-box-office-summary.

    `title_id` is a bare IMDb title id (e.g. "tt15398776"). Returns the raw
    `data.title` dict. Relevant (all optional) fields:
      - budget.totalBudget.amount
      - domesticGross.total.amount
      - worldwideGross.total.amount
      - openingWeekendGrosses.edges[0].node.gross.total.amount

    Amounts live under nested {amount, currency} "Money" objects.
    """
    data = _get(
        "/title/v2/get-box-office-summary",
        {"tconst": title_id, "country": "US", "language": "en-US"},
    )
    return data.get("data", {}).get("title", {})
