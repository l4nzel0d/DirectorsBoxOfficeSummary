"""Render the Box Office Summary PDF from a Director + list[Movie].

Faithful port of the original project.py layout (same coordinates/fonts),
but fed by typed domain objects and with images letterbox-fitted into their
boxes (keep_aspect_ratio) instead of pre-cropped. The $0 -> "-" display rule
lives here, in _money(). Aggregates come from the movies module.
"""

from fpdf import FPDF
from fpdf.enums import XPos

from . import movies
from .chart import render_chart
from .models import Director, Movie


def _money(amount: int) -> str:
    """Format an amount as USD, or '-' when it's 0 (missing/unknown)."""
    return "-" if amount == 0 else f"${amount:,}"


def _split_name(name: str) -> tuple[str, str]:
    """First word vs. the rest, for the two-line header. Single-word names
    return ('Name', '') so the second line is simply blank."""
    first, _, rest = name.partition(" ")
    return first, rest


class PDF(FPDF):
    def __init__(self, director: Director, films: list[Movie]):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.director = director
        # Worldwide-descending drives both the header's "top" film and the table.
        self.films = movies.by_worldwide_desc(films)
        self.set_left_margin(12)
        self.set_right_margin(12)

    def header(self):
        self.set_font("Courier", "BI", 32)
        self.cell(0, 10, "Box Office Summary", align="C")

        # Director portrait, fitted into a fixed box (no crop).
        if self.director.image_url:
            self.image(self.director.image_url, 12, 36, 48, 62, keep_aspect_ratio=True)

        name_x = 65
        name_box_width = 210 - 10 - 65
        first, rest = _split_name(self.director.name)
        self.set_font("Helvetica", "B", 45)
        self.set_xy(name_x, 43)
        self.cell(name_box_width, 0, first)
        if rest:
            self.set_xy(name_x, 57)
            self.cell(name_box_width, 0, rest)

        self.set_font("Helvetica", "I", 24)
        self.set_xy(name_x, 70)
        self.cell(0, 0, "as Director")
        self.line(name_x + 2, 76, 198, 76)

        self.set_font("Helvetica", "", 22)
        self.set_xy(name_x, 85)
        self.cell(0, 0, "Total Worldwide Box Office:")
        self.set_font("Helvetica", "B", 22)
        self.set_xy(name_x, 94)
        self.cell(0, 0, _money(movies.total_worldwide(self.films)))
        self.ln(20)

    def footer(self):
        self.set_y(288)
        self.line(88, 289, 122, 289)
        self.set_font("Courier", "B", 13)
        self.set_y(290)
        self.set_x(20)
        self.cell(0, 4, f"Page {self.page_no()}/{{nb}}", align="C")


def _summary_line(pdf: PDF, label: str, value: str):
    pdf.set_font("Helvetica", "", 18)
    pdf.cell(0, 0, label, new_x=XPos.WCONT)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 0, value, new_x=XPos.LMARGIN)
    pdf.ln(10)


def _top_movie(pdf: PDF, x: int, label: str, movie: Movie, amount: int):
    """One of the three 'top film' columns: label, poster, dollar value."""
    pdf.set_xy(x, 156)
    pdf.multi_cell(50, 7, label, align="C")
    if movie.poster_url:
        pdf.image(movie.poster_url, x, 180, 50, 75, keep_aspect_ratio=True)
    pdf.set_xy(x, 263)
    pdf.cell(50, 0, _money(amount), align="C")


def make_pdf(director: Director, films: list[Movie]) -> PDF:
    pdf = PDF(director, films)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    ordered = pdf.films  # already worldwide-descending

    # --- Page 1 body: totals ---
    _summary_line(pdf, "Total Domestic Box Office: ", _money(movies.total_domestic(ordered)))
    _summary_line(pdf, "Total International Box Office: ", _money(movies.total_international(ordered)))
    _summary_line(pdf, "Feature Films:  ", f"{len(ordered)}")

    # --- Page 1: top three films ---
    top_ww = movies.top_by_worldwide(ordered)
    top_dom = movies.top_by_domestic(ordered)
    top_open = movies.top_by_opening(ordered)
    if top_ww:
        _top_movie(pdf, 12, "Highest Grossing Worldwide", top_ww, top_ww.worldwide_gross)
        _top_movie(pdf, 78, "Highest Grossing Domestically", top_dom, top_dom.domestic_gross)
        _top_movie(pdf, 144, "Biggest Domestic Openning", top_open, top_open.opening_weekend)

    # --- Page 2+: filmography table ---
    pdf.add_page()
    pdf.set_font("Helvetica", "", 14)
    with pdf.table(col_widths=(13, 30, 25, 30, 30)) as table:
        table.row(["Rank", "Movie", "Budget", "Domestic Gross", "Worldwide Gross"])
        for rank, movie in enumerate(ordered, start=1):
            table.row([
                str(rank),
                movie.title,
                _money(movie.budget),
                _money(movie.domestic_gross),
                _money(movie.worldwide_gross),
            ])

    # --- Chart ---
    chart = render_chart(ordered)
    if chart is not None:
        pdf.image(chart, w=186)

    return pdf
