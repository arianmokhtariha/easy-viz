"""Figure layout shared by every plot: title block, sizing, subplot-grid geometry."""

import math
import re
from typing import NamedTuple

import plotly.graph_objects as go

from easy_viz._validate import check_positive_int
from easy_viz.config import get_config
from easy_viz.theme.theme import Theme, build_template

# Height of one text line as a multiple of its font size: what Plotly needs to stack
# the title and subtitle without overlap. A typographic ratio, not a style choice.
_LINE_HEIGHT = 1.5

# Height over width of a single-panel chart: 560 px at the default 1400 px width,
# the original module's size. A proportion, so a narrower figure keeps its shape.
_ASPECT = 0.4

# Text lines one category band takes in a chart that stacks categories down the
# page (horizontal bars): the tick label plus the gap to the next one.
_BAND_LINES = 2

# Average glyph width as a share of the font size (Arial-like fonts): good enough
# to tell whether a label fits a bar, not to place text.
_GLYPH_WIDTH = 0.6

# Python format types that need an int: decimal, binary, octal, hex, locale number.
_INTEGER_TYPES = frozenset("dboxXn")

# Suffixes of the automatic value format: thousands, millions, billions, trillions.
_SUFFIXES = ("", "k", "M", "B", "T")

# The line breaks Plotly honours in text: <br>, <br/>, <br />, any letter case.
_LINE_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)


class GridGeometry(NamedTuple):
    """Subplot-grid layout from :func:`grid_geometry`."""

    n_rows: int
    n_cols: int
    h_spacing: float
    v_spacing: float
    height: int


def escape_text(text: str) -> str:
    """Make user text safe for Plotly by escaping every ``$``.

    Two ``$`` anywhere in a string switch Plotly into LaTeX mode, which garbles
    text like ``"Revenue from $1M to $3M"``. The HTML entity renders as a plain
    ``$``. Other HTML is left alone, so users can still pass ``<b>`` on purpose.

    Parameters
    ----------
    text : str
        Any title, label or annotation the user supplied.

    Returns
    -------
    str
        ``text`` with each ``$`` replaced by ``&#36;``.
    """
    return text.replace("$", "&#36;")


def format_value(value: float, spec: str | None) -> str:
    """Format a number for a label or hover text.

    Parameters
    ----------
    value : float
        The number.
    spec : str or None
        A Python format spec (``",.0f"``), or ``None`` for the automatic format:
        three significant digits, with k, M, B or T for thousands, millions,
        billions and trillions (``862k``, ``1.08M``, ``-2.5k``, ``0.42``). Python
        specs have no such suffixes, and ``.3g`` alone writes ``8.62e+05``.

    Returns
    -------
    str
        The formatted value.
    """
    if spec is not None:
        # Integer types (",d" for counts) refuse floats: round, as the spec asks.
        if spec[-1:] in _INTEGER_TYPES:
            return format(round(value), spec)
        return format(value, spec)
    step, scaled = 0, value
    # Rounding can carry into the next unit (999,999 is 1e+03k), so test the
    # rounded text, not the raw value.
    while step < len(_SUFFIXES) - 1 and abs(float(f"{scaled:.3g}")) >= 1000:
        step += 1
        scaled = value / 1000**step
    return f"{scaled:.3g}{_SUFFIXES[step]}"


# Python format specs that mean the same in d3-format, which Plotly uses for axis
# ticks: an optional sign, thousands separators and precision, and a fixed-point,
# percent or exponent type. Other specs differ between the two languages.
_SHARED_SPEC = re.compile(r"[+\- ]?,?(?:\.\d+)?[f%e]")


def d3_format(spec: str | None) -> str | None:
    """Return ``spec`` as a Plotly tick format when it means the same there.

    Python format specs and d3-format agree on the common forms (``",.0f"``,
    ``"+.1%"``, ``".2e"``), so axis ticks can match the labels. For any other
    spec, and for ``None``, return ``None`` and leave Plotly's own tick format.
    """
    if spec is not None and _SHARED_SPEC.fullmatch(spec):
        return spec
    return None


def text_px(text: str, font_size: int) -> float:
    """Estimate the width in px of ``text`` (its longest ``<br>`` line)."""
    lines = _LINE_BREAK.split(text)
    return max(len(line) for line in lines) * font_size * _GLYPH_WIDTH


def _width(width: int | None) -> int:
    """Return ``width``, or the configured default when it is ``None``."""
    return get_config().width if width is None else width


def grid_geometry(
    n_plots: int,
    n_cols: int,
    *,
    width: int | None,
    height: int | None,
    theme: Theme,
    caller: str,
) -> GridGeometry:
    """Compute subplot-grid geometry shared by the grid-based plots.

    Plotly expresses ``horizontal_spacing``/``vertical_spacing`` as a fraction of
    the *whole grid*, not as a gap between neighbouring panels. A fixed
    fraction therefore silently starves large grids: the gaps scale with the
    panel count while the figure does not, so at ``v_spacing=0.12`` with nine
    rows the eight gaps consume 96% of the figure and every subplot collapses to
    ~11 px of drawing area.

    Both gaps are therefore declared as **pixel budgets** (theme fields) and
    converted against the dimension they are measured along, which holds the
    whitespace between panels visually constant however many panels there are.
    Row height is a flat per-row budget for the same reason: every subplot gets
    the same drawing area whether the grid holds two panels or twenty. Each
    spacing is capped at half its axis so gaps can never out-consume the panels,
    even when the caller forces a small ``height``.

    The conversion divides by the full figure size, margins included, as the
    original module did; the budgets were tuned that way, so the drawn gaps come
    out somewhat smaller than their nominal px.

    Parameters
    ----------
    n_plots : int
        Number of subplots to lay out (at least 1).
    n_cols : int
        Requested number of grid columns (at least 1). Fewer plots than columns
        use one column per plot, so a lone panel fills the width.
    width : int or None
        Figure width in px; ``None`` uses ``easy_viz.config``. Converts the
        column gap to a fraction.
    height : int or None
        Caller's figure height in px. ``None`` derives it from the row count.
        Passed in so the conversion uses the height the figure is drawn at.
    theme : Theme
        Source of the pixel budgets (``row_gap_px``, ``col_gap_px``,
        ``row_plot_px``).
    caller : str
        The public function the user called, named in error messages.

    Returns
    -------
    GridGeometry
        ``(n_rows, n_cols, h_spacing, v_spacing, height)``: the spacings go to
        ``make_subplots``, ``height`` to the figure.
    """
    # Sizes are divided by below: reject 0 and negatives with a clear message.
    for param, value in {"n_plots": n_plots, "n_cols": n_cols, "width": width}.items():
        if param != "width" or value is not None:
            check_positive_int(caller, param, value)
    if height is not None:
        check_positive_int(caller, "height", height)
    n_cols = min(n_cols, n_plots)
    n_rows = math.ceil(n_plots / n_cols)
    final_height = (
        height
        if height is not None
        else n_rows * (theme.row_plot_px + theme.row_gap_px)
    )
    v_spacing = (
        min(theme.row_gap_px / final_height, 0.5 / (n_rows - 1)) if n_rows > 1 else 0.0
    )
    h_spacing = (
        min(theme.col_gap_px / _width(width), 0.5 / (n_cols - 1)) if n_cols > 1 else 0.0
    )
    return GridGeometry(n_rows, n_cols, h_spacing, v_spacing, final_height)


def _line_count(text: str | None) -> int:
    """Count the lines ``text`` takes, including ``<br>`` breaks; 0 when empty."""
    return 1 + len(_LINE_BREAK.findall(text)) if text else 0


def _title_margin(theme: Theme, *, title: str | None, subtitle: str | None) -> int:
    """Top margin in px that fits the title block and the gap below it.

    Parameters
    ----------
    theme : Theme
        Source of the font sizes and the ``title_top_px``/``title_gap_px``
        spacing.
    title, subtitle : str or None
        The text shown; each ``<br>`` in it adds a line.

    Returns
    -------
    int
        Margin from the figure's top edge to the plot area.
    """
    title_px = theme.title_font_size * _line_count(title)
    subtitle_px = theme.subtitle_font_size * _line_count(subtitle)
    lines = title_px + subtitle_px
    return round(theme.title_top_px + lines * _LINE_HEIGHT + theme.title_gap_px)


def auto_height(
    width: int | None,
    *,
    theme: Theme,
    title: str | None,
    subtitle: str | None,
    bands: int = 0,
) -> int:
    """Figure height for a single-panel chart called with ``height=None``.

    Parameters
    ----------
    width : int or None
        Figure width in px; ``None`` uses ``easy_viz.config``.
    theme : Theme
        Source of the font and title sizes.
    title, subtitle : str or None
        The title block shown, which takes its share of the height.
    bands : int, default 0
        Categories stacked down the page (horizontal bars). Each needs room
        for its label, so the height grows with them; 0 for charts whose
        categories run across.

    Returns
    -------
    int
        ``width`` x 0.4, or more when the category bands need it.
    """
    height = round(_width(width) * _ASPECT)
    if bands:
        band = theme.font_size * _LINE_HEIGHT * _BAND_LINES
        # Below the bands: the value axis tick labels and its title.
        needed = _title_margin(theme, title=title, subtitle=subtitle) + band * (
            bands + 2
        )
        height = max(height, round(needed))
    return height


def apply_base_layout(
    fig: go.Figure,
    *,
    title: str | None,
    subtitle: str | None,
    width: int | None,
    height: int | None,
    theme: Theme,
) -> None:
    """Apply the theme, the title block and the figure size to ``fig``.

    The title is centred and bold; the subtitle is a smaller, muted second line
    (Plotly's native ``title.subtitle``, so users can restyle it after the
    fact). Both are escaped with :func:`escape_text`. The top margin grows to
    fit whichever lines are shown, including lines added with ``<br>``.

    Parameters
    ----------
    fig : go.Figure
        Figure changed in place.
    title : str or None
        Main title; ``None`` or ``""`` shows none.
    subtitle : str or None
        Second line (the measure or the method note); ``None`` or ``""`` shows
        none.
    width : int or None
        Figure width in px; ``None`` uses ``easy_viz.config``.
    height : int or None
        Figure height in px; ``None`` leaves it unset, so Plotly auto-sizes.
    theme : Theme
        Theme whose template the figure gets.
    """
    fig.update_layout(
        template=build_template(theme),
        title={
            "text": f"<b>{escape_text(title)}</b>" if title else None,
            "subtitle": {"text": escape_text(subtitle) if subtitle else None},
        },
        margin={"t": _title_margin(theme, title=title, subtitle=subtitle)},
        width=_width(width),
    )
    if height is not None:
        fig.update_layout(height=height)
