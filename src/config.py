"""Configuration for the IMDb GraphQL client.

All the data (name search, director, filmography, box office) comes from IMDb's
unofficial GraphQL endpoint. It needs no key, only the client-name header
below. Every response carries IMDb's disclaimer: "Public, commercial, and/or
non-private use of the IMDb data provided by this API is not allowed" — so this
tool is for personal, non-commercial use only.
"""

IMDB_GRAPHQL_URL = "https://caching.graphql.imdb.com/"

# Without this header IMDb answers with a bare 403 HTML page; any value passes.
IMDB_HEADERS = {"x-imdb-client-name": "imdb-web-next"}

# The host occasionally drops connections or throttles; retry a few times with
# exponential backoff so one transient blip doesn't abort a run. 403 is
# deliberately absent: it means IMDb changed its access rules, and retrying
# won't help.
TIMEOUT = 30
MAX_RETRIES = 4
BACKOFF_BASE = 1.0  # seconds: waits 1, 2, 4 ... between attempts
RETRY_STATUSES = {429, 500, 502, 503, 504}
