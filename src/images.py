"""Download IMDb CDN images (portrait, posters) as data URIs.

Used for the HTML page, which embeds every image so it is a single file that
works offline. Images are requested as thumbnails through the CDN's resize
suffix, so a poster costs tens of KB instead of a few MB. Images are cosmetic:
a download that fails is simply left out (the page shows a placeholder),
unlike the API data, which fails fast.
"""

import base64
import re
from concurrent.futures import ThreadPoolExecutor

import requests

from .http_client import get

# m.media-amazon.com URLs end in "._V1_<params>.jpg"; the params resize/crop.
_V1_SUFFIX = re.compile(r"\._V1_.*\.(jpg|png)$")
_WORKERS = 8


def thumbnail_url(url: str, width: int) -> str:
    """The CDN URL of `url` scaled to `width` pixels wide (75% JPEG quality).
    URLs without the usual suffix are returned unchanged."""
    return _V1_SUFFIX.sub(rf"._V1_QL75_UX{width}_.\1", url)


def _data_uri(url: str, width: int) -> str | None:
    try:
        response = get(thumbnail_url(url, width))
    except requests.RequestException:
        return None
    mime = response.headers.get("Content-Type", "").split(";")[0].strip()
    if not mime.startswith("image/"):
        return None
    return f"data:{mime};base64,{base64.b64encode(response.content).decode('ascii')}"


def fetch_data_uris(urls, width: int = 400) -> dict[str, str]:
    """Download each distinct non-empty URL (in parallel) as a `width`-pixel
    thumbnail. Returns {original url: data URI}; failed downloads are absent."""
    unique = list(dict.fromkeys(url for url in urls if url))
    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        uris = pool.map(lambda url: _data_uri(url, width), unique)
    return {url: uri for url, uri in zip(unique, uris) if uri}
