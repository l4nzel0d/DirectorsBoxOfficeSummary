"""Pure tests for the HTML output: page, SVG chart, money formatting and the
CDN thumbnail URL. No network: films and images are built by hand."""

from src.formatting import money, money_short
from src.html_page import make_html
from src.images import thumbnail_url
from src.models import Director, Movie
from src.svg_chart import render_svg_chart

NOLAN = Director(id="nm0634240", name="Christopher Nolan", image_url="https://img/nolan.jpg")
OPPENHEIMER = Movie(
    id="tt15398776",
    title="Oppenheimer",
    year=2023,
    poster_url="https://img/opp.jpg",
    budget=100_000_000,
    domestic_gross=330_078_895,
    worldwide_gross=975_811_333,
    opening_weekend=82_455_420,
)
FOLLOWING = Movie(id="tt0154506", title="Following", year=1998, worldwide_gross=240_495)


def test_money_formats():
    assert money(0) == "-"
    assert money(975_811_333) == "$975,811,333"
    assert money_short(0) == "-"
    assert money_short(500) == "$500"
    assert money_short(48_482) == "$48K"
    assert money_short(975_811_333) == "$975.8M"
    assert money_short(999_950_000) == "$1.00B"
    assert money_short(6_123_456_789) == "$6.12B"


def test_thumbnail_url():
    base = "https://m.media-amazon.com/images/M/MV5BNjE3@@"
    assert thumbnail_url(f"{base}._V1_.jpg", 400) == f"{base}._V1_QL75_UX400_.jpg"
    assert thumbnail_url(f"{base}._V1_UY1200_CR85,0,630,1200_AL_.jpg", 300) == f"{base}._V1_QL75_UX300_.jpg"
    assert thumbnail_url("https://example.com/poster.jpg", 400) == "https://example.com/poster.jpg"


def test_page_shows_totals_and_escapes_titles():
    tricky = Movie(id="tt1", title="Tom & Jerry <Live>", year=2001, worldwide_gross=1_000)
    page = make_html(NOLAN, [OPPENHEIMER, tricky])
    assert "<title>Christopher Nolan · Box Office Summary</title>" in page
    assert "$975,812,333" in page  # total worldwide, exact
    assert "Tom &amp; Jerry &lt;Live&gt;" in page
    assert "<Live>" not in page


def test_zero_amounts_show_as_dash():
    page = make_html(NOLAN, [FOLLOWING])
    table = page[page.index("<table"):]
    assert table.count('<td class="num none" data-sort="">-</td>') == 3  # budget, opening, domestic
    assert "$0" not in table


def test_images_embed_or_fall_back_to_placeholders():
    uri = "data:image/jpeg;base64,AAAA"
    page = make_html(NOLAN, [OPPENHEIMER], {OPPENHEIMER.poster_url: uri})
    assert f'src="{uri}"' in page
    assert 'class="portrait placeholder"' in page  # portrait wasn't downloaded
    assert "https://img/" not in page  # never hotlinked


def test_highlight_with_no_amount_is_skipped():
    page = make_html(NOLAN, [FOLLOWING])  # no domestic gross, no opening weekend
    assert "Highest Grossing Worldwide" in page
    assert "Highest Grossing Domestically" not in page
    assert "Biggest Domestic Openning" not in page


def test_empty_filmography_renders():
    page = make_html(NOLAN, [])
    assert "Christopher Nolan" in page
    assert "<svg" not in page
    assert "<table" not in page


def test_chart_has_one_column_per_film_in_career_order():
    svg = render_svg_chart([OPPENHEIMER, FOLLOWING])
    assert svg.count('class="hit"') == 2
    assert svg.index('data-title="Following"') < svg.index('data-title="Oppenheimer"')
    # Following has no domestic gross: one domestic dot (Oppenheimer's) only.
    assert svg.count('class="dot domestic"') == 1


def test_chart_is_none_without_films():
    assert render_svg_chart([]) is None
