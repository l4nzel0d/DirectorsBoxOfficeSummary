"""Shared HTTP with retry, used by the IMDb GraphQL client and the image
downloader.

Lives below the clients so the retry policy stays separate from the queries.
A real 4xx surfaces as requests.HTTPError.
"""

import time

import requests

from . import config


def _request(method: str, url: str, **kwargs) -> requests.Response:
    for attempt in range(config.MAX_RETRIES):
        last_attempt = attempt == config.MAX_RETRIES - 1
        try:
            response = requests.request(method, url, timeout=config.TIMEOUT, **kwargs)
        except (requests.ConnectionError, requests.Timeout):
            if last_attempt:
                raise
        else:
            # Retry transient server/throttle statuses; let everything else
            # (success or a real 4xx) fall through to raise_for_status/return.
            if not (response.status_code in config.RETRY_STATUSES and not last_attempt):
                response.raise_for_status()
                return response

        time.sleep(config.BACKOFF_BASE * 2**attempt)

    # Unreachable: the loop either returns or raises on the last attempt.
    raise RuntimeError("retry loop exited without returning")


def post_json(url: str, payload: dict, headers: dict | None = None) -> dict:
    """POST `payload` as JSON and return the parsed JSON response."""
    return _request("POST", url, json=payload, headers=headers).json()


def get(url: str) -> requests.Response:
    """GET `url` (e.g. an image) and return the successful response."""
    return _request("GET", url)
