"""Figure layout shared by every plot: title block, sizing, subplot-grid geometry."""

import math
from typing import NamedTuple

import plotly.graph_objects as go

from easy_viz._validate import check_positive_int
from easy_viz.config import get_config
from easy_viz.theme.theme import Theme, build_template

# Height of one text line as a multiple of its font size: what Plotly needs to stack
# the title and subtitle without overlap. A typographic ratio, not a style choice.
_LINE_HEIGHT = 1.5


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


def _title_margin(theme: Theme, *, title: bool, subtitle: bool) -> int:
    """Top margin in px that fits the title block and the gap below it.

    Parameters
    ----------
    theme : Theme
        Source of the font sizes and the ``title_top_px``/``title_gap_px``
        spacing.
    title, subtitle : bool
        Whether each line is shown.

    Returns
    -------
    int
        Margin from the figure's top edge to the plot area.
    """
    lines = (theme.title_font_size if title else 0) + (
        theme.subtitle_font_size if subtitle else 0
    )
    return round(theme.title_top_px + lines * _LINE_HEIGHT + theme.title_gap_px)


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
    fit whichever lines are shown.

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
        margin={"t": _title_margin(theme, title=bool(title), subtitle=bool(subtitle))},
        width=_width(width),
    )
    if height is not None:
        fig.update_layout(height=height)
