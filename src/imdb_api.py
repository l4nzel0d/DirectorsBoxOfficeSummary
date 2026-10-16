"""Thin client over IMDb's GraphQL API (caching.graphql.imdb.com).

Each function makes one logical call and returns the parsed JSON (or a slice of
it). Shaping/normalizing the data lives elsewhere — this module is only
responsible for talking to the API. The API is undocumented and introspection
is blocked, so the field names below come from known working queries.

Failures are loud: a 403 (IMDb changed its access rules) or a GraphQL `errors`
array raises RuntimeError, so partial data never becomes a silently wrong PDF.
"""

import requests

from . import config
from .http_client import post_json

# Credits per page; Nolan has 18 directing credits, Hitchcock 69.
PAGE_SIZE = 250

SEARCH = """
query Search($term: String!) {
  mainSearch(first: 20, options: { searchTerm: $term, type: NAME, includeAdult: false }) {
    edges { node { entity { ... on Name {
      id
      nameText { text }
      primaryProfessions { category { id text } }
      knownForV2(limit: 3) { credits { title { titleText { text } releaseYear { year } } } }
      meterRanking { currentRank }
    } } } }
  }
}
"""

NAME = """
query Name($id: ID!) {
  name(id: $id) { id nameText { text } primaryImage { url } }
}
"""

CREDITS = """
query Credits($id: ID!, $first: Int!, $after: ID) {
  name(id: $id) {
    credits(first: $first, after: $after, filter: { categories: ["director"] }) {
      pageInfo { hasNextPage endCursor }
      edges { node { title {
        id
        titleText { text }
        titleType { id }
        releaseYear { year }
        productionStatus { currentProductionStage { id } }
        primaryImage { url }
        productionBudget { budget { amount currency } }
        domestic: lifetimeGross(boxOfficeArea: DOMESTIC) { total { amount currency } }
        worldwide: lifetimeGross(boxOfficeArea: WORLDWIDE) { total { amount currency } }
        openingWeekendGross(boxOfficeArea: DOMESTIC) { gross { total { amount currency } } }
      } } }
    }
  }
}
"""


def _query(query: str, variables: dict) -> dict:
    try:
        body = post_json(
            config.IMDB_GRAPHQL_URL,
            {"query": query, "variables": variables},
            config.IMDB_HEADERS,
        )
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 403:
            raise RuntimeError(
                "IMDb refused the request (HTTP 403); its GraphQL access rules may have changed."
            ) from exc
        raise
    if body.get("errors"):
        messages = "; ".join(e.get("message", "unknown error") for e in body["errors"])
        raise RuntimeError(f"IMDb GraphQL error: {messages}")
    return body["data"]


def search_names(term: str) -> list[dict]:
    """Search people by name via mainSearch (up to 20, IMDb's relevance order).

    Returns the flat list of raw Name entities; each has:
      - id:                 the IMDb name id (e.g. "nm0634240")
      - nameText.text:      display name
      - primaryProfessions: [{category: {id, text}}], e.g. id "director",
                            text "Director"
      - knownForV2.credits: [{title: {titleText.text, releaseYear.year}}]
      - meterRanking:       {currentRank} STARmeter rank (lower is more
                            popular), or null for unranked people
    """
    data = _query(SEARCH, {"term": term})
    return [edge["node"]["entity"] for edge in data["mainSearch"]["edges"]]


def get_name(name_id: str) -> dict | None:
    """Fetch a person by bare IMDb name id (e.g. "nm0634240").

    Returns the raw Name node: id, nameText.text, primaryImage.url (either may
    be null). An unknown id comes back as a node whose nameText is null.
    """
    return _query(NAME, {"id": name_id})["name"]


def get_directing_credits(name_id: str) -> list[dict]:
    """List the titles a person directed, following pagination to the end.

    Returns the flat list of raw Title nodes; each has:
      - id, titleText.text, titleType.id (e.g. "movie", "short"),
        releaseYear.year, primaryImage.url
      - productionStatus.currentProductionStage.id (e.g. "released",
        "abandoned", "in_production")
      - productionBudget.budget:        Money {amount, currency}
      - domestic.total:                 Money (alias of lifetimeGross DOMESTIC)
      - worldwide.total:                Money (alias of lifetimeGross WORLDWIDE)
      - openingWeekendGross.gross.total: Money (domestic opening weekend)
    Any of these may be null. Grosses are USD; budgets can be in local currency.
    """
    titles: list[dict] = []
    variables = {"id": name_id, "first": PAGE_SIZE}
    while True:
        name = _query(CREDITS, variables)["name"]
        credits = (name or {}).get("credits") or {}
        titles.extend(edge["node"]["title"] for edge in credits.get("edges") or [])
        page = credits.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            return titles
        variables = {**variables, "after": page["endCursor"]}
