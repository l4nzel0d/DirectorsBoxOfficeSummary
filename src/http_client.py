"""Shared HTTP POST with retry, used by the IMDb GraphQL client.

Lives below the client so the retry policy stays separate from the queries.
Returns parsed JSON; a real 4xx surfaces as requests.HTTPError.
"""

import time

import requests

from . import config


def post_json(url: str, payload: dict, headers: dict | None = None) -> dict:
    for attempt in range(config.MAX_RETRIES):
        last_attempt = attempt == config.MAX_RETRIES - 1
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=config.TIMEOUT)
        except (requests.ConnectionError, requests.Timeout):
            if last_attempt:
                raise
        else:
            # Retry transient server/throttle statuses; let everything else
            # (success or a real 4xx) fall through to raise_for_status/return.
            if not (response.status_code in config.RETRY_STATUSES and not last_attempt):
                response.raise_for_status()
                return response.json()

        time.sleep(config.BACKOFF_BASE * 2**attempt)

    # Unreachable: the loop either returns or raises on the last attempt.
    raise RuntimeError("retry loop exited without returning")
