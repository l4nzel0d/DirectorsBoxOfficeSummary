"""The site icon as a <link> tag with the SVG inlined, so single-file pages need no extra request."""

from pathlib import Path
from urllib.parse import quote

_SVG = (Path(__file__).parent / "assets" / "favicon.svg").read_text(encoding="utf-8")

FAVICON_LINK = f'<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,{quote(_SVG)}">'
