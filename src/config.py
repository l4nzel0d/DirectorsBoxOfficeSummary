"""Configuration and credentials for the IMDb (RapidAPI) client."""

import os

from dotenv import load_dotenv

load_dotenv()

RAPIDAPI_HOST = "imdb8.p.rapidapi.com"
API_KEY = os.getenv("API_KEY")


def headers() -> dict[str, str]:
    """Build the auth headers for a RapidAPI request.

    Raises a clear error if the key is missing, rather than letting the
    request fail later with an opaque 401/403.
    """
    if not API_KEY:
        raise RuntimeError("API_KEY is not set. Add it to your .env file.")
    return {
        "x-rapidapi-key": API_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST,
        "Content-Type": "application/json",
    }
