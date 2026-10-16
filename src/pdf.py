"""Render the Box Office Summary PDF from a Director + list[Movie].

Faithful port of the original project.py layout (same coordinates/fonts),
but fed by typed domain objects and with images letterbox-fitted into their
boxes (keep_aspect_ratio) instead of pre-cropped. Money is printed with
formatting.money ($0 -> "-"). Aggregates come from the movies module.
"""

from fpdf import FPDF
from fpdf.enums import XPos

from . import movies
from .chart import render_chart
from .formatting import money
from .models import Director, Movie

MM_PER_INCH = 25.4

# With more films than this, the chart page turns landscape and drops the
# header, so crowded tick labels get the room instead of the plot.
PORTRAIT_CHART_MAX_FILMS = 15


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
        self.show_header = True  # turned off for a landscape chart page

    def header(self):
        if not self.show_header:
            return
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
        self.cell(0, 0, money(movies.total_worldwide(self.films)))
        self.ln(20)

    def footer(self):
        # Placed from the page's bottom and centre so it also fits a landscape
        # page (portrait A4: rule at y=289 from x=88 to 122, text at y=290).
        bottom, middle = self.h - 9, self.w / 2
        self.line(middle - 17, bottom + 1, middle + 17, bottom + 1)
        self.set_font("Courier", "B", 13)
        self.set_y(bottom + 2)
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
    pdf.cell(50, 0, money(amount), align="C")


def make_pdf(director: Director, films: list[Movie]) -> PDF:
    pdf = PDF(director, films)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    ordered = pdf.films  # already worldwide-descending

    # --- Page 1 body: totals ---
    _summary_line(pdf, "Total Domestic Box Office: ", money(movies.total_domestic(ordered)))
    _summary_line(pdf, "Total International Box Office: ", money(movies.total_international(ordered)))
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
                money(movie.budget),
                money(movie.domestic_gross),
                money(movie.worldwide_gross),
            ])

    # --- Last page: chart, filling the box under the header (or, for many
    # films, a whole landscape page without it) ---
    if ordered:
        if len(ordered) > PORTRAIT_CHART_MAX_FILMS:
            pdf.show_header = False
            pdf.add_page(orientation="L")
        else:
            pdf.add_page()
        top = pdf.get_y()
        width = pdf.epw
        height = pdf.page_break_trigger - top - 2  # keep clear of the footer
        chart = render_chart(ordered, (width / MM_PER_INCH, height / MM_PER_INCH))
        pdf.image(chart, x=pdf.l_margin, y=top, w=width, h=height)

    return pdf
