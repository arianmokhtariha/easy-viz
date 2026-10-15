"""Comparison plots: one value per category, side by side.

``bar_plot`` draws every query-result shape (pre-aggregated, raw rows with
``agg``, long with ``color``, wide with a list ``y``) and carries the statistics
needed to compare groups honestly: confidence intervals and small-group flags.

The function runs in stages, each a helper below:
1. ``_check_options``: option checks that need no data
2. ``_data``: intake, types, nulls (the shared table pipeline)
3. ``_shape``: aggregation, ordering, "Other", counts and intervals, into a
   grid of bars (series x categories)
4. ``_draw``: traces, labels, colours, reference lines, layout
"""

import dataclasses
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

# Any: values read back from a table (to_dict) are the backend's own Python
# values, and Plotly specs are untyped dicts; neither has a type to name here.
from typing import Any

import narwhals as nw
import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

from easy_viz import _data
from easy_viz._layout import (
    apply_base_layout,
    auto_height,
    d3_format,
    escape_text,
    format_value,
    text_px,
)
from easy_viz._meta import tag
from easy_viz._typing import (
    Agg,
    BarMode,
    FrameLike,
    Orientation,
    SortBy,
    TextPosition,
    ValueColoring,
)
from easy_viz._validate import (
    check_choice,
    check_conflict,
    check_positive_int,
    check_range,
    check_requires,
    is_set,
    message,
    setting,
    warn_no_effect,
)
from easy_viz.config import get_config
from easy_viz.stats.intervals import CiMethod, Interval, RandomState, interval
from easy_viz.theme._color import ACCEPTED_FORMS, is_color
from easy_viz.theme.registry import ThemeName, resolve_theme
from easy_viz.theme.theme import Theme

FUNC = "bar_plot"

# Option defaults, named so the no-effect warnings can tell a changed value.
CI_LEVEL = 0.95
N_BOOT = 2000
RANDOM_STATE = 0
MIN_N = 30
BARGAP = 0.15
BARGROUPGAP = 0.1
VALUE_FORMAT = None

OTHER = "Other"

# How an aggregate is named in titles and hover text ("Mean order_value").
_AGG_WORDS: dict[str, str] = {
    "sum": "Total",
    "mean": "Mean",
    "median": "Median",
    "min": "Min",
    "max": "Max",
    "count": "Count",
}

# Hatching marks bars built from too few rows: a pattern, not a colour, so it
# reads in every colour mode and both themes.
_FLAG_PATTERN = "/"
_FLAG = "⚠"
# Share of a flagged bar the stripes cover. Thin stripes in the plot area's colour
# read as gaps in the bar, so labels inside it stay on the bar's own colour.
_FLAG_SOLIDITY = 0.25


@dataclass(frozen=True, slots=True)
class _Options:
    """Every option of one ``bar_plot`` call, so the stages share one value."""

    x: str
    ys: list[str]
    color: str | None
    hover: list[str]
    agg: Agg | None
    ci: CiMethod | None
    ci_level: float
    n_boot: int
    random_state: RandomState
    min_n: int | None
    sort_by: SortBy | None
    ascending: bool
    top_n: int | None
    other: bool
    orientation: Orientation
    barmode: BarMode
    bargap: float
    bargroupgap: float
    show_values: bool
    value_format: str | None
    text_position: TextPosition | None
    show_pct_of_total: bool
    show_n: bool
    highlight: list[str]
    color_map: Mapping[str, str] | None
    color_by_value: ValueColoring | None
    colorscale: str | Sequence[tuple[float, str]] | None
    color_midpoint: float | None
    avg_line: bool
    target: float | None
    x_title: str | None
    y_title: str | None
    width: int | None

    @property
    def wide(self) -> bool:
        """Several measure columns, one series each."""
        return len(self.ys) > 1

    @property
    def multi(self) -> bool:
        """Whether the call asks for several series."""
        return self.color is not None or self.wide

    @property
    def flags_small_groups(self) -> bool:
        """Whether bars from fewer than ``min_n`` rows are flagged."""
        return self.min_n is not None and self.agg in ("mean", "median")


@dataclass(frozen=True, slots=True)
class _Bars:
    """What ``bar_plot`` draws: one row per series, one column per category.

    Arrays hold NaN where a series has no bar for a category.
    """

    categories: list[object]  # x values in drawing order; the "Other" label last
    other_label: str | None
    series: list[str]
    values: npt.NDArray[np.float64]
    n: npt.NDArray[np.float64] | None  # rows behind each bar, when agg is set
    low: npt.NDArray[np.float64] | None  # interval bounds, when ci is set
    high: npt.NDArray[np.float64] | None
    hover: list[list[list[tuple[str, str]]]]  # extra hover lines per bar
    total: int  # categories in the data, before top_n


def bar_plot(
    df: FrameLike,
    x: str,
    y: str | list[str] | None = None,
    *,
    color: str | None = None,
    hover: str | list[str] | None = None,
    agg: Agg | None = None,
    ci: CiMethod | None = None,
    ci_level: float = CI_LEVEL,
    n_boot: int = N_BOOT,
    random_state: RandomState = RANDOM_STATE,
    min_n: int | None = MIN_N,
    sort_by: SortBy | None = None,
    ascending: bool = False,
    top_n: int | None = None,
    other: bool = False,
    orientation: Orientation = "vertical",
    barmode: BarMode = "group",
    bargap: float = BARGAP,
    bargroupgap: float = BARGROUPGAP,
    show_values: bool = True,
    value_format: str | None = VALUE_FORMAT,
    text_position: TextPosition | None = None,
    show_pct_of_total: bool = False,
    show_n: bool = False,
    highlight: str | list[str] | None = None,
    color_map: Mapping[str, str] | None = None,
    color_by_value: ValueColoring | None = None,
    colorscale: str | Sequence[tuple[float, str]] | None = None,
    color_midpoint: float | None = None,
    avg_line: bool = False,
    target: float | None = None,
    title: str | None = None,
    subtitle: str | None = None,
    x_title: str | None = None,
    y_title: str | None = None,
    width: int | None = None,
    height: int | None = None,
    theme: ThemeName | Theme | None = None,
) -> go.Figure:
    """Compare a value across categories: which are biggest, and by how much.

    One bar per category of ``x``. The table can come straight from a query in
    any shape: one row per category (plotted as-is), raw rows (``agg``), series
    stacked in a column (``color``) or side by side in several columns (a list
    ``y``). With ``agg="mean"`` or ``"median"`` the bars can carry confidence
    intervals and flag groups built from too few rows, so differences that
    aren't real don't look real.

    Parameters
    ----------
    df : DataFrame-like
        The query result: pandas, polars, pyarrow, a DuckDB result, or anything
        else narwhals accepts. Never modified.
    x : str
        Category column, one bar (or cluster of bars) per value. Date, datetime
        and ISO-date text columns give a time axis, always in time order.
    y : str, list of str or None, default None
        Measure column, or several (wide format: one series per column, named
        after it). May be omitted only with ``agg="count"``. Conflicts with
        ``color`` when it is a list.
    color : str or None, default None
        Column that splits the bars into coloured series (long format), drawn
        side by side or stacked (``barmode``). Conflicts with a list ``y``, and
        can't be ``x`` itself: to colour the bars, use ``highlight`` or
        ``color_by_value``.
    hover : str, list of str or None, default None
        Extra columns shown on hover. Only with ``agg=None``: a combined bar has
        no single value for them, so with ``agg`` they are ignored with a warning
        (and their missing values drop no rows).
    agg : {"sum", "mean", "median", "min", "max", "count"} or None, default None
        ``None`` plots each row as-is and raises if an ``x``/``color``
        combination repeats. Otherwise rows are combined per bar; ``"count"``
        counts rows and needs no ``y``.
    ci : {"bootstrap", "sem"} or None, default None
        Error bars: a confidence interval around each bar. ``"bootstrap"``
        works for the mean and the median, ``"sem"`` (mean ± z·standard error)
        for the mean only. Needs ``agg="mean"`` or ``"median"``, and
        ``barmode="group"``. Bars from a single row get no error bar.
    ci_level : float, default 0.95
        Confidence level, strictly between 0 and 1.
    n_boot : int, default 2000
        Bootstrap resamples per bar (``ci="bootstrap"`` only).
    random_state : int, numpy Generator or None, default 0
        Seed of the bootstrap (``ci="bootstrap"`` only). The fixed default
        draws the same intervals on every run; ``None`` draws new ones.
    min_n : int or None, default 30
        With ``agg="mean"`` or ``"median"``, bars built from fewer rows than
        this are hatched and marked ⚠: their value is unreliable. ``None``
        turns the flag off.
    sort_by : {"value", "x"} or None, default None
        ``None`` keeps the query's order. ``"value"`` orders categories by bar
        value (with several series: by the category's value over all its rows,
        or the sum of its bars when ``agg=None``); ``"x"`` by the category
        itself. Conflicts with a time ``x``.
    ascending : bool, default False
        Sort direction for ``sort_by``; the default puts the largest first.
    top_n : int or None, default None
        Keep the first N categories after sorting. Conflicts with a time ``x``.
    other : bool, default False
        With ``top_n``, add one "Other" bar for the categories cut. With raw
        rows it uses the same ``agg``, so it is right for every aggregate. With
        ``agg=None`` the cut values are added up: right for totals and counts,
        wrong for averages and rates.
    orientation : {"vertical", "horizontal"}, default "vertical"
        ``"horizontal"`` puts categories down the page, the first one at the
        top: good for long labels and many categories.
    barmode : {"group", "stack", "percent"}, default "group"
        How several series share a category: side by side, stacked (with the
        total above each stack), or stacked to 100 % (each segment's share).
        ``"percent"`` needs values of 0 or more. A single series is drawn as
        ``"group"``, with a warning.
    bargap : float, default 0.15
        Gap between categories, as a fraction of a category's width (0 to 1).
    bargroupgap : float, default 0.1
        Gap between the bars of one category (several series side by side).
    show_values : bool, default True
        Write each bar's value on it (its share with ``barmode="percent"``).
        Labels are never shrunk below a readable size: a stacked segment too
        small for its label shows none, and side-by-side bars too narrow for
        their labels show none at all, rather than labels on only some bars.
        The hover always has the value.
    value_format : str or None, default None
        Python format spec for values in labels, hover and reference lines,
        e.g. ``",.0f"`` or ``".1%"``. ``None``: three significant digits with
        k, M, B for thousands, millions, billions (``862k``, ``1.08M``).
    text_position : {"outside", "inside", "auto"} or None, default None
        Where labels sit. ``None``: outside for side-by-side bars; inside for
        stacked ones; inside at the base of the bar with ``ci``, clear of the
        error bars.
    show_pct_of_total : bool, default False
        Add each bar's share of the sum of all bars drawn to its label and
        hover. Conflicts with ``barmode="percent"``.
    show_n : bool, default False
        Add each bar's row count ("n=42") to its label. Needs ``agg``; the
        count is in the hover whenever ``agg`` is set.
    highlight : str, list of str or None, default None
        Categories to emphasise; the other bars use the theme's dimmed colour.
        One series only: conflicts with ``color``, a list ``y`` and
        ``color_by_value``, and with a time ``x``.
    color_map : mapping of str to str or None, default None
        A fixed colour per series (``color`` value or ``y`` column), so a
        category looks the same in every chart. Hex, ``rgb()`` or ``rgba()``;
        must cover every series drawn, may hold others.
    color_by_value : {"sequential", "diverging", "sign"} or None, default None
        Colour each bar by its own value: ``"sequential"`` low to high, with a
        colour bar; ``"diverging"`` in two directions from ``color_midpoint``;
        ``"sign"`` in the theme's positive and negative colours either side of
        it. One series only: conflicts with ``color``, a list ``y``,
        ``highlight`` and ``color_map``.
    colorscale : str, list of (float, str) or None, default None
        Any Plotly colour scale (a name such as ``"Viridis"``, or stops) for
        ``color_by_value="sequential"`` or ``"diverging"``. ``None`` uses the
        theme's scale.
    color_midpoint : float or None, default None
        The value where ``"diverging"`` and ``"sign"`` change colour; ``None``
        means 0.
    avg_line : bool, default False
        Dashed line at the average bar (of the stack totals when stacked),
        "Other" left out. Conflicts with ``barmode="percent"``.
    target : float or None, default None
        Dotted line at a target value, labelled. Conflicts with
        ``barmode="percent"``.
    title : str or None, default None
        ``None`` builds one ("Mean order_value by variant"); ``""`` shows none.
    subtitle : str or None, default None
        ``None`` states what the chart does to the data: sorting, cut
        categories, the interval method, the flag; ``""`` shows none.
    x_title, y_title : str or None, default None
        Axis titles of the ``x`` and ``y`` slots, wherever ``orientation``
        draws them. ``None`` uses the column name (``y`` with its aggregate);
        ``""`` shows none.
    width, height : int or None, default None
        Size in px. ``width=None`` uses ``ev.get_config().width``;
        ``height=None`` is 0.4 x the width, taller when horizontal bars need it.
    theme : {"dark", "light"}, Theme or None, default None
        Theme for this chart; ``None`` uses the global one (``ev.set_theme``).

    Returns
    -------
    plotly.graph_objects.Figure
        A plain figure; finish anything the options don't cover on it.

    Raises
    ------
    ValueError
        For a missing column, a repeated category with ``agg=None``, conflicting
        options (the message names both), or values ``barmode="percent"``
        can't draw.
    TypeError
        If ``y`` is not numeric or ``df`` is not a table.

    Trace roles
    -----------
    - ``data``: the bars, one trace per series; ``group`` is the series name
      (``None`` for a single series). Error bars belong to these traces.
    - ``reference``: the average line (``group="average"``), the target line
      (``group="target"``) and the totals above stacked bars
      (``group="total"``).

    Examples
    --------
    Revenue per region, as the query returns it:

    >>> import easy_viz as ev
    >>> fig = ev.bar_plot(sales, "region", "revenue")  # doctest: +SKIP

    Raw orders, the six biggest categories and the rest as "Other":

    >>> ev.bar_plot(orders, "category", "revenue", agg="sum",
    ...             sort_by="value", top_n=6, other=True)  # doctest: +SKIP

    Mean order value per variant, with bootstrap intervals, by device:

    >>> ev.bar_plot(checkouts, "variant", "order_value", color="device",
    ...             agg="mean", ci="bootstrap")  # doctest: +SKIP
    """
    o = _Options(
        x=x,
        ys=_names(y),
        color=color,
        hover=_names(hover),
        agg=agg,
        ci=ci,
        ci_level=ci_level,
        n_boot=n_boot,
        random_state=random_state,
        min_n=min_n,
        sort_by=sort_by,
        ascending=ascending,
        top_n=top_n,
        other=other,
        orientation=orientation,
        barmode=barmode,
        bargap=bargap,
        bargroupgap=bargroupgap,
        show_values=show_values,
        value_format=value_format,
        text_position=text_position,
        show_pct_of_total=show_pct_of_total,
        show_n=show_n,
        highlight=_names(highlight),
        color_map=color_map,
        color_by_value=color_by_value,
        colorscale=colorscale,
        color_midpoint=color_midpoint,
        avg_line=avg_line,
        target=target,
        x_title=x_title,
        y_title=y_title,
        width=width,
    )
    check_choice(FUNC, "barmode", o.barmode, BarMode)
    if not o.multi and o.barmode != "group":
        # One series has nothing to stack: draw it plainly, and say so.
        warn_no_effect(FUNC, "barmode", o.barmode, "with a single series")
        o = dataclasses.replace(o, barmode="group")
    _check_options(o, y=y, highlight=highlight, width=width, height=height)
    chosen = resolve_theme(theme, caller=FUNC)
    # With agg, hover has no effect: it isn't loaded, so its nulls can't drop rows
    # that the bars are computed from (only used columns count, rule 7).
    used_hover = hover if agg is None else None
    frame = _data.load(df, FUNC, {"x": x, "y": y, "color": color, "hover": used_hover})
    _data.require_numeric(frame, FUNC, {"y": y})
    frame = _data.parse_time(frame, FUNC, "x", x)
    is_time = _data.column_kind(frame, x) == "temporal"
    if is_time:
        _check_time_axis(o, highlight)
    frame = _data.drop_nulls(frame, FUNC)
    bars = _shape(frame, o)
    _check_bars(o, bars, chosen, highlight)
    fig = _draw(o, bars, chosen, is_time)
    labels = _value_label(o)
    apply_base_layout(
        fig,
        title=title if title is not None else _auto_title(o, labels),
        subtitle=subtitle if subtitle is not None else _auto_subtitle(o, bars),
        width=width,
        height=height,
        theme=chosen,
    )
    if height is None:
        fig.update_layout(
            height=auto_height(
                width,
                theme=chosen,
                title=fig.layout.title.text,
                subtitle=fig.layout.title.subtitle.text,
                bands=len(bars.categories) if o.orientation == "horizontal" else 0,
            )
        )
    return fig


# --- 1. option checks ----------------------------------------------------------------


def _names(value: str | list[str] | None) -> list[str]:
    """Return a slot or option given as one name or several, as a list."""
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)


def _check_options(
    o: _Options,
    *,
    y: object,
    highlight: object,
    width: int | None,
    height: int | None,
) -> None:
    """Check every option that needs no data, before any table work."""
    for param, value, alias in (
        ("agg", o.agg, Agg),
        ("ci", o.ci, CiMethod),
        ("sort_by", o.sort_by, SortBy),
        ("text_position", o.text_position, TextPosition),
        ("color_by_value", o.color_by_value, ValueColoring),
    ):
        if value is not None:
            check_choice(FUNC, param, value, alias)
    check_choice(FUNC, "orientation", o.orientation, Orientation)
    check_choice(FUNC, "barmode", o.barmode, BarMode)

    # The query-result shape (conventions, rules 2 and 3).
    if not o.ys and o.agg != "count":
        raise ValueError(
            message(
                FUNC,
                "y is not set",
                "Pass the measure column as y, or use agg='count' to count rows",
            )
        )
    if o.color is not None and o.color == o.x:
        raise ValueError(
            message(
                FUNC,
                f"{setting('color', o.color)} is the same column as x",
                "color splits each category into series; to colour the bars "
                "themselves, use highlight or color_by_value",
            )
        )
    if o.wide and o.color is not None:
        raise ValueError(
            message(
                FUNC,
                f"{setting('y', y)} cannot be combined with "
                f"{setting('color', o.color)}",
                "Pick one shape: a list y for one column per series, or color "
                "for series stacked in one column",
            )
        )

    _check_statistics(o)
    _check_ordering_and_layout(o, width=width, height=height)
    _check_labels(o)
    _check_colour(o, highlight=highlight)
    lines: tuple[tuple[str, object], ...] = (
        ("avg_line", o.avg_line),
        ("target", o.target),
    )
    for line, line_value in lines:
        if is_set(line_value) and o.barmode == "percent":
            raise ValueError(_mode_conflict(line, line_value, "barmode", o.barmode))
    if o.target is not None:
        check_range(FUNC, "target", o.target)


def _mode_conflict(param: str, value: object, other: str, other_value: object) -> str:
    """Build the standard message for two options set together."""
    return message(
        FUNC,
        f"{setting(param, value)} cannot be combined with "
        f"{setting(other, other_value)}",
        "Remove one of them",
    )


def _check_statistics(o: _Options) -> None:
    """Check ``ci``, its settings and the small-group flag."""
    if o.ci is not None:
        if o.agg not in ("mean", "median"):
            raise ValueError(
                message(
                    FUNC,
                    f"{setting('ci', o.ci)} needs agg='mean' or agg='median', got "
                    f"{setting('agg', o.agg)}",
                    "Pass the raw rows with agg='mean' or 'median', or remove ci",
                )
            )
        if o.ci == "sem" and o.agg == "median":
            raise ValueError(
                message(
                    FUNC,
                    "ci='sem' cannot be combined with agg='median'",
                    "The standard error describes a mean: use ci='bootstrap', or "
                    "agg='mean'",
                )
            )
        if o.barmode != "group":
            raise ValueError(_mode_conflict("ci", o.ci, "barmode", o.barmode))
    check_range(FUNC, "ci_level", o.ci_level, low=0, high=1, include_low=False,
                include_high=False)  # fmt: skip
    check_positive_int(FUNC, "n_boot", o.n_boot)
    seed = o.random_state
    if not (
        seed is None
        or isinstance(seed, np.random.Generator)
        or (isinstance(seed, int) and not isinstance(seed, bool) and seed >= 0)
    ):
        raise ValueError(
            message(
                FUNC,
                f"{setting('random_state', seed)} is not valid",
                "Use a whole number of 0 or more, a numpy Generator, or None",
            )
        )
    if o.min_n is not None:
        check_positive_int(FUNC, "min_n", o.min_n)

    if o.ci is None and o.ci_level != CI_LEVEL:
        warn_no_effect(FUNC, "ci_level", o.ci_level, "without ci")
    if o.ci != "bootstrap":
        if o.n_boot != N_BOOT:
            warn_no_effect(FUNC, "n_boot", o.n_boot, "unless ci='bootstrap'")
        if not (isinstance(seed, int) and seed == RANDOM_STATE):
            warn_no_effect(FUNC, "random_state", seed, "unless ci='bootstrap'")
    if not o.flags_small_groups and o.min_n not in (MIN_N, None):
        warn_no_effect(FUNC, "min_n", o.min_n, "unless agg is 'mean' or 'median'")


def _check_ordering_and_layout(
    o: _Options, *, width: int | None, height: int | None
) -> None:
    """Check ordering, truncation, bar layout and size."""
    if o.top_n is not None:
        check_positive_int(FUNC, "top_n", o.top_n)
    check_requires(FUNC, "other", o.other, needs="top_n", needs_value=o.top_n)
    if o.ascending and o.sort_by is None:
        warn_no_effect(FUNC, "ascending", o.ascending, "without sort_by")
    for param, value in (("bargap", o.bargap), ("bargroupgap", o.bargroupgap)):
        check_range(FUNC, param, value, low=0, high=1, include_high=False)
    if not o.multi and o.bargroupgap != BARGROUPGAP:
        warn_no_effect(FUNC, "bargroupgap", o.bargroupgap, "with a single series")
    for param, size in (("width", width), ("height", height)):
        if size is not None:
            check_positive_int(FUNC, param, size)


def _check_labels(o: _Options) -> None:
    """Check the value labels and their format."""
    try:
        format_value(1234.5, o.value_format)
    except (ValueError, TypeError):
        raise ValueError(
            message(
                FUNC,
                f"{setting('value_format', o.value_format)} is not a Python "
                "format spec",
                "Use one such as '.3g', ',.0f' or '.1%'",
            )
        ) from None
    check_requires(FUNC, "show_n", o.show_n, needs="agg", needs_value=o.agg)
    if o.hover and o.agg is not None:
        shown = o.hover[0] if len(o.hover) == 1 else o.hover
        warn_no_effect(
            FUNC,
            "hover",
            shown,
            f"with {setting('agg', o.agg)}: a combined bar has no single value for it",
        )
    if o.show_pct_of_total and o.barmode == "percent":
        raise ValueError(
            _mode_conflict("show_pct_of_total", True, "barmode", o.barmode)
        )
    if o.text_position is not None and not (o.show_values or o.show_n):
        warn_no_effect(
            FUNC, "text_position", o.text_position, "without labels",
            "Set show_values=True, or remove it",
        )  # fmt: skip


def _check_colour(o: _Options, *, highlight: object) -> None:
    """Check the colour options: highlight, color_map, value colouring."""
    series_shape = {"color": o.color, "y": o.ys if o.wide else None}
    for param, value in (
        ("highlight", highlight),
        ("color_by_value", o.color_by_value),
    ):
        for shape, shape_value in series_shape.items():
            check_conflict(FUNC, **{param: value, shape: shape_value})
    check_conflict(FUNC, highlight=highlight, color_by_value=o.color_by_value)
    check_conflict(FUNC, color_by_value=o.color_by_value, color_map=o.color_map)
    if highlight is not None and not all(isinstance(h, str) for h in o.highlight):
        raise TypeError(
            message(
                FUNC,
                f"{setting('highlight', highlight)} is not a category name",
                "Pass a category of x as text, or a list of them",
            )
        )
    if o.color_map is not None:
        if not o.multi:
            raise ValueError(
                message(
                    FUNC,
                    "color_map needs several series",
                    "Set color, or pass a list y; to colour categories, use "
                    "highlight or color_by_value",
                )
            )
        for name, value in o.color_map.items():
            if not isinstance(value, str) or not is_color(value):
                raise ValueError(
                    message(
                        FUNC,
                        f"color_map[{name!r}]={value!r} is not a colour easy-viz "
                        "can read",
                        f"Use {ACCEPTED_FORMS}",
                    )
                )
    check_requires(
        FUNC, "colorscale", o.colorscale,
        needs="color_by_value", needs_value=o.color_by_value,
    )  # fmt: skip
    check_requires(
        FUNC, "color_midpoint", o.color_midpoint,
        needs="color_by_value", needs_value=o.color_by_value,
    )  # fmt: skip
    if o.colorscale is not None:
        if o.color_by_value == "sign":
            warn_no_effect(
                FUNC, "colorscale", o.colorscale, "with color_by_value='sign'"
            )
        try:
            go.bar.Marker(colorscale=o.colorscale)
        except ValueError:
            raise ValueError(
                message(
                    FUNC,
                    f"{setting('colorscale', o.colorscale)} is not a colour scale",
                    "Use a Plotly scale name such as 'Viridis', or a list of "
                    "(position, colour) stops from 0 to 1",
                )
            ) from None
    if o.color_midpoint is not None:
        check_range(FUNC, "color_midpoint", o.color_midpoint)
        if o.color_by_value == "sequential":
            warn_no_effect(
                FUNC,
                "color_midpoint",
                o.color_midpoint,
                "with color_by_value='sequential'",
            )


def _check_time_axis(o: _Options, highlight: object) -> None:
    """Raise for options that would reorder or pick out dates on a time axis."""
    for param, value in (
        ("sort_by", o.sort_by),
        ("top_n", o.top_n),
        ("highlight", highlight),
    ):
        if value is not None:
            raise ValueError(
                message(
                    FUNC,
                    f"{setting(param, value)} cannot be used with "
                    f"{setting('x', o.x)}, a time column",
                    "A time axis is always in time order: remove "
                    f"{param}, or cast x to text in the query",
                )
            )


def _check_bars(o: _Options, bars: _Bars, theme: Theme, highlight: object) -> None:
    """Check what needs the shaped data: values, categories, series."""
    if o.barmode == "percent" and np.nanmin(bars.values) < 0:
        raise ValueError(
            message(
                FUNC,
                "barmode='percent' needs values of 0 or more, but some are negative",
                "Use barmode='stack' or 'group', or filter the negative values",
            )
        )
    if o.highlight:
        shown = {_text(category) for category in bars.categories}
        missing = [h for h in o.highlight if h not in shown]
        if missing:
            cut = " (top_n may have cut it)" if o.top_n is not None else ""
            raise ValueError(
                message(
                    FUNC,
                    f"{setting('highlight', highlight)} names {missing[0]!r}, "
                    f"which is not a category drawn{cut}",
                    "Check the spelling against the values of x",
                )
            )
    if o.color_map is not None:
        uncovered = [s for s in bars.series if s not in o.color_map]
        if uncovered:
            raise ValueError(
                message(
                    FUNC,
                    f"color_map has no colour for {uncovered[0]!r} "
                    f"({len(uncovered)} series without one)",
                    "Add every series to color_map",
                )
            )
    elif len(bars.series) > len(theme.colorway):
        raise ValueError(
            message(
                FUNC,
                f"{len(bars.series)} series need {len(bars.series)} colours, but "
                f"the theme has {len(theme.colorway)}",
                "Filter the query to fewer series, pass color_map, or use a theme "
                "with a longer colorway",
            )
        )


# --- 3. shaping ----------------------------------------------------------------------


def _shape(frame: _data.Frame, o: _Options) -> _Bars:
    """Aggregate, order and cut the categories; attach counts and intervals."""
    key_params = {"x": o.x, "color": o.color}
    key_columns = [c for c in (o.x, o.color) if c is not None]
    table, value_columns = _data.aggregate(frame, FUNC, key_params, o.ys, o.agg)
    rows = table.to_dict(as_series=False)
    series = (
        list(dict.fromkeys(str(v) for v in rows[o.color]))
        if o.color is not None
        else list(value_columns)
    )
    categories: list[object] = list(dict.fromkeys(rows[o.x]))
    total = len(categories)
    if o.sort_by == "value":
        weight = _category_weights(frame, rows, o, value_columns)
        categories.sort(key=lambda c: weight[c], reverse=not o.ascending)
    elif o.sort_by == "x":
        categories = _sorted_naturally(categories, reverse=not o.ascending)
    kept = categories if o.top_n is None else categories[: o.top_n]
    cut = categories[len(kept) :]

    # The "Other" bar: the cut categories, combined like every other bar.
    other_label: str | None = None
    rest: _data.Frame | None = None
    other_rows: dict[str, list[Any]] = {}
    if o.other and cut:
        other_label = OTHER
        if OTHER in {_text(c) for c in kept}:
            other_label = f"{OTHER} ({len(cut)} categories)"
        source = frame if o.agg is not None else table
        rest = (
            source.filter(nw.col(o.x).is_in(cut))
            .select(*key_columns, *o.ys)
            .with_columns(nw.lit(other_label).alias(o.x))
        )
        other_table, _ = _data.aggregate(rest, FUNC, key_params, o.ys, o.agg or "sum")
        other_rows = other_table.to_dict(as_series=False)

    columns: list[object] = [*kept, *([other_label] if other_label else [])]
    which = {name: index for index, name in enumerate(series)}
    shape = (len(series), len(columns))
    values = np.full(shape, np.nan)
    hover: list[list[list[tuple[str, str]]]] = [[[] for _ in columns] for _ in series]
    # Each source fills only its own columns: the main table the kept categories,
    # the cut rows the "Other" bar. A cut category that is itself called "Other"
    # can then never land on the "Other" bar.
    kept_columns: dict[object, int] = {c: index for index, c in enumerate(kept)}
    other_column: dict[object, int] = {other_label: len(kept)} if other_label else {}

    def cell(
        table_rows: Mapping[str, list[Any]], i: int, where: Mapping[object, int]
    ) -> list[tuple[int, int]]:
        """Return the (series, category) positions row ``i`` of a table fills."""
        column = where.get(table_rows[o.x][i])
        if column is None:
            return []
        if o.color is not None:
            return [(which[str(table_rows[o.color][i])], column)]
        return [(k, column) for k in range(len(series))]

    for table_rows, where in ((rows, kept_columns), (other_rows, other_column)):
        for i in range(len(table_rows.get(o.x, []))):
            for s, c in cell(table_rows, i, where):
                values[s, c] = table_rows[value_columns[s if o.wide else 0]][i]
                if o.agg is None and table_rows is rows:
                    hover[s][c] = [(h, _text(rows[h][i])) for h in o.hover]

    sources = [(frame, kept_columns)]
    if rest is not None:
        sources.append((rest, other_column))
    n = low = high = None
    if o.agg is not None:
        n = np.full(shape, np.nan)
        for source, where in sources:
            counted, count_columns = _data.aggregate(
                source.select(*key_columns, *o.ys), FUNC, key_params, o.ys, "count"
            )
            count_rows = counted.to_dict(as_series=False)
            for i in range(len(counted)):
                for s, c in cell(count_rows, i, where):
                    n[s, c] = count_rows[count_columns[0]][i]
    if o.ci is not None and o.agg in ("mean", "median"):
        low, high = np.full(shape, np.nan), np.full(shape, np.nan)
        for source, where in sources:
            for k, column in enumerate(o.ys):
                groups = _data.group_arrays(source, key_columns, column)
                for key, sample in groups.items():
                    c_index = where.get(key[0])
                    if c_index is None:
                        continue
                    s_index = which[str(key[1])] if o.color is not None else k
                    result: Interval = interval(
                        sample,
                        statistic=o.agg,
                        method=o.ci,
                        level=o.ci_level,
                        n_boot=o.n_boot,
                        random_state=o.random_state,
                    )
                    low[s_index, c_index] = result.low
                    high[s_index, c_index] = result.high
    return _Bars(columns, other_label, series, values, n, low, high, hover, total)


def _category_weights(
    frame: _data.Frame,
    rows: Mapping[str, list[Any]],
    o: _Options,
    value_columns: Sequence[str],
) -> dict[object, float]:
    """Return the value each category is sorted by with ``sort_by="value"``.

    With ``agg`` set, the category's own aggregate over all its rows (the
    split by ``color`` ignored), as the original grouped bar plot ordered its
    groups; with ``agg=None``, the sum of its bars.
    """
    weight: dict[object, float] = {}
    if o.agg is None:
        source: Mapping[str, list[Any]] = rows
        columns: Sequence[str] = value_columns
    else:
        overall, columns = _data.aggregate(
            frame.select(o.x, *o.ys), FUNC, {"x": o.x}, o.ys, o.agg
        )
        source = overall.to_dict(as_series=False)
    for i, category in enumerate(source[o.x]):
        total = sum(float(source[c][i]) for c in columns)
        weight[category] = weight.get(category, 0.0) + total
    return weight


def _sorted_naturally(values: list[object], *, reverse: bool) -> list[object]:
    """Sort by the values themselves, or by their text when types don't compare."""
    try:
        return sorted(values, reverse=reverse)  # type: ignore[type-var]
    except TypeError:
        return sorted(values, key=str, reverse=reverse)


# --- 4. drawing ----------------------------------------------------------------------


def _text(value: object) -> str:
    """Show a data value as plain text: dates without a midnight time part."""
    strftime = getattr(value, "strftime", None)
    if strftime is not None and hasattr(value, "hour"):
        midnight = (value.hour, value.minute, value.second) == (0, 0, 0)  # type: ignore[attr-defined]
        return str(strftime("%Y-%m-%d" if midnight else "%Y-%m-%d %H:%M"))
    return str(value)


def _value_label(o: _Options, series: str | None = None) -> str:
    """Name what the bars measure: the y column(s) with their aggregate."""
    if o.agg == "count":
        return _AGG_WORDS["count"]
    names = series if series is not None else ", ".join(o.ys)
    return names if o.agg is None else f"{_AGG_WORDS[o.agg]} {names}"


def _auto_title(o: _Options, value_label: str) -> str:
    """'Mean order_value by variant', plus the split when there is one."""
    split = f", split by {o.color}" if o.color is not None else ""
    return f"{value_label} by {o.x}{split}"


def _auto_subtitle(o: _Options, bars: _Bars) -> str:
    """State everything the chart does to the data, in reading order."""
    parts = []
    if o.sort_by is not None:
        direction = "ascending" if o.ascending else "descending"
        key = "value" if o.sort_by == "value" else o.x
        parts.append(f"sorted by {key} ({direction})")
    shown = len(bars.categories) - (1 if bars.other_label else 0)
    if shown < bars.total:
        rest = f", the rest in {bars.other_label}" if bars.other_label else ""
        # "top" only when the bars are ranked by value; otherwise they are the
        # first ones in the query's (or the category) order.
        which = "top" if o.sort_by == "value" else "first"
        parts.append(f"{which} {shown} of {bars.total} {o.x} values{rest}")
    if o.barmode == "percent":
        parts.append("each bar adds up to 100%")
    if o.ci is not None:
        method = "bootstrap" if o.ci == "bootstrap" else "standard error"
        parts.append(
            f"error bars: {o.ci_level * 100:g}% confidence interval ({method})"
        )
    if _flags(o, bars).any():
        parts.append(f"hatched {_FLAG} = fewer than {o.min_n} rows")
    return " · ".join(parts)


def _flags(o: _Options, bars: _Bars) -> npt.NDArray[np.bool_]:
    """Which bars are built from fewer than ``min_n`` rows."""
    if not o.flags_small_groups or bars.n is None or o.min_n is None:
        return np.zeros(bars.values.shape, dtype=bool)
    return np.asarray(bars.n < o.min_n)


def _draw(o: _Options, bars: _Bars, theme: Theme, is_time: bool) -> go.Figure:
    """Build the bar traces, the reference traces and the axes."""
    horizontal = o.orientation == "horizontal"
    category_key, value_key = ("y", "x") if horizontal else ("x", "y")
    labels: list[object] = [
        c if is_time and c != bars.other_label else escape_text(_text(c))
        for c in bars.categories
    ]
    single = len(bars.series) == 1
    flags = _flags(o, bars)
    stacked = o.barmode in ("stack", "percent")
    inside = stacked or o.ci is not None
    position = o.text_position or ("inside" if inside else "outside")
    totals = np.nansum(bars.values, axis=0)
    grand = float(np.nansum(bars.values))

    labelled = [
        _labels(o, bars, s, labels, totals, grand, flags[s])
        for s in range(len(bars.series))
    ]
    if not horizontal and not stacked and not _labels_fit(o, bars, theme, labelled):
        labelled = [([""] * len(texts), hovers) for texts, hovers in labelled]

    fig = go.Figure()
    for s, name in enumerate(bars.series):
        values = bars.values[s]
        texts, hovers = labelled[s]
        trace = go.Bar(
            name=escape_text(name),
            showlegend=not single,
            orientation="h" if horizontal else "v",
            text=texts,
            textposition=position,
            textangle=0,
            # With error bars, labels sit at the bar's base, clear of the whiskers.
            insidetextanchor="start" if o.ci is not None else "middle",
            textfont={"size": theme.label_font_size},
            cliponaxis=False,
            hovertext=hovers,
            hovertemplate="%{hovertext}<extra></extra>",
            marker=_marker(o, bars, s, theme),
            **{category_key: labels, value_key: _plotly_list(values)},
            **_error_bars(o, bars, s, theme, value_key),
        )
        fig.add_trace(tag(trace, "data", None if single else name))

    # Totals after the reference lines, so their text sits on top of a line.
    _add_reference_lines(fig, o, bars, theme, horizontal)
    if o.barmode == "stack" and not single and o.show_values:
        fig.add_trace(_stack_totals(o, bars, labels, theme, horizontal))

    category_axis: dict[str, Any] = {
        "title": {"text": escape_text(o.x_title if o.x_title is not None else o.x)}
    }
    if not is_time:
        category_axis.update(
            type="category", categoryorder="array", categoryarray=labels
        )
    if horizontal:
        category_axis["autorange"] = "reversed"
    value_title = o.y_title
    if value_title is None:
        value_title = _value_label(o)
        if o.barmode == "percent":
            value_title = f"Share of {value_title[0].lower()}{value_title[1:]}"
    value_axis: dict[str, Any] = {"title": {"text": escape_text(value_title)}}
    tickformat = d3_format(o.value_format)
    if o.barmode == "percent":
        value_axis["ticksuffix"] = "%"
    elif tickformat is not None:
        # The axis reads like the labels: "+5.0%" on both, not "+5.0%" and 0.05.
        value_axis["tickformat"] = tickformat
    fig.update_layout(
        {
            f"{category_key}axis": category_axis,
            f"{value_key}axis": value_axis,
            "barmode": {"group": "group", "stack": "relative", "percent": "stack"}[
                o.barmode
            ],
            "barnorm": "percent" if o.barmode == "percent" else None,
            "bargap": o.bargap,
            "bargroupgap": o.bargroupgap,
            "showlegend": not single,
            "legend": {
                "title": {"text": escape_text(o.color) if o.color else ""},
                "traceorder": "normal",
            },
            # Labels that would need shrinking below the theme's label size hide.
            "uniformtext": {"minsize": theme.label_font_size, "mode": "hide"},
        }
    )
    return fig


# Share of the figure width the plot area takes (the rest: axis titles, tick
# labels and margins), and with a legend beside it. Estimates for the label fit.
_PLOT_SHARE = 0.85
_PLOT_SHARE_WITH_LEGEND = 0.75


def _labels_fit(
    o: _Options,
    bars: _Bars,
    theme: Theme,
    labelled: Sequence[tuple[list[str], list[str]]],
) -> bool:
    """Tell whether the widest label fits the narrowest side-by-side bar.

    Plotly hides each label that doesn't fit on its own, which leaves labels
    on some bars and not others: a chart that reads as broken. The width is an
    estimate, so the check errs towards hiding.
    """
    widest = max(
        (
            text_px(text, theme.label_font_size)
            for texts, _ in labelled
            for text in texts
        ),
        default=0.0,
    )
    n_series = len(bars.series)
    share = _PLOT_SHARE if n_series == 1 else _PLOT_SHARE_WITH_LEGEND
    plot = (get_config().width if o.width is None else o.width) * share
    slot = plot / len(bars.categories) * (1 - o.bargap)
    bar = slot / n_series * (1 - (o.bargroupgap if n_series > 1 else 0))
    return widest <= bar


def _plotly_list(values: npt.NDArray[np.float64]) -> list[float | None]:
    """NaN as None: Plotly draws no bar (and no error bar) for a missing value."""
    return [None if math.isnan(v) else float(v) for v in values]


def _labels(
    o: _Options,
    bars: _Bars,
    s: int,
    labels: Sequence[object],
    totals: npt.NDArray[np.float64],
    grand: float,
    flags: npt.NDArray[np.bool_],
) -> tuple[list[str], list[str]]:
    """Build the label on each bar of series ``s``, and its hover text."""
    texts: list[str] = []
    hovers: list[str] = []
    name = bars.series[s]
    single = len(bars.series) == 1
    for c, value in enumerate(bars.values[s]):
        if math.isnan(value):
            texts.append("")
            hovers.append("")
            continue
        count = bars.n[s, c] if bars.n is not None else math.nan
        share = value / totals[c] if totals[c] else math.nan
        parts = []
        if o.show_values:
            if o.barmode == "percent":
                parts.append(format(share, ".0%"))
            else:
                part = format_value(value, o.value_format)
                if o.show_pct_of_total and grand:
                    part += f" ({value / grand * 100:.1f}%)"
                parts.append(part)
        if o.show_n and not math.isnan(count):
            parts.append(f"n={int(count):,}")
        text = "<br>".join(parts)
        if flags[c]:
            text = f"{text} {_FLAG}".strip()
        texts.append(text)

        category = labels[c]
        lines = [f"{escape_text(o.x)}: <b>{_text(category)}</b>"]
        if not single and o.color is not None:
            lines.append(f"{escape_text(o.color)}: {escape_text(name)}")
        measure = _value_label(o, name if o.wide else None)
        lines.append(f"{escape_text(measure)}: {format_value(value, o.value_format)}")
        if o.barmode == "percent":
            lines.append(f"share of {_text(category)}: {share:.1%}")
        if o.show_pct_of_total and grand:
            lines.append(f"share of total: {value / grand * 100:.1f}%")
        if not math.isnan(count):
            lines.append(f"n = {int(count):,}")
        if bars.low is not None and bars.high is not None:
            low, high = bars.low[s, c], bars.high[s, c]
            if not math.isnan(low):
                lines.append(
                    f"{o.ci_level * 100:g}% CI: {format_value(low, o.value_format)} to "
                    f"{format_value(high, o.value_format)}"
                )
        if flags[c]:
            lines.append(f"{_FLAG} fewer than {o.min_n} rows")
        lines += [f"{escape_text(h)}: {escape_text(v)}" for h, v in bars.hover[s][c]]
        hovers.append("<br>".join(lines))
    return texts, hovers


def _marker(o: _Options, bars: _Bars, s: int, theme: Theme) -> dict[str, Any]:
    """Colours of series ``s``, by the colour mode, plus the small-group hatch."""
    values = bars.values[s]
    midpoint = o.color_midpoint if o.color_midpoint is not None else 0.0
    marker: dict[str, Any]
    if o.color_by_value in ("sequential", "diverging"):
        default = (
            theme.marker_sequential_scale
            if o.color_by_value == "sequential"
            else theme.marker_diverging_scale
        )
        scale: object = o.colorscale or [list(stop) for stop in default]
        marker = {
            "color": _plotly_list(values),
            "colorscale": scale,
            "showscale": True,
            "colorbar": {
                "title": {"text": escape_text(_value_label(o))},
                "tickformat": d3_format(o.value_format),
            },
        }
        if o.color_by_value == "diverging":
            marker["cmid"] = midpoint
    elif o.color_by_value == "sign":
        marker = {
            "color": [
                theme.neutral
                if math.isnan(v) or v == midpoint
                else theme.positive
                if v > midpoint
                else theme.negative
                for v in values
            ]
        }
    elif len(bars.series) > 1:
        name = bars.series[s]
        color_map = o.color_map or {}
        marker = {"color": color_map.get(name, theme.colorway[s])}
    else:
        emphasis = set(o.highlight)
        colors = []
        for category in bars.categories:
            if emphasis and _text(category) not in emphasis:
                colors.append(theme.dimmed)
            elif category == bars.other_label and bars.other_label is not None:
                colors.append(theme.other)
            else:
                colors.append(theme.colorway[0])
        marker = {"color": colors}
    flags = _flags(o, bars)[s]
    if flags.any():
        marker["pattern"] = {
            "shape": [_FLAG_PATTERN if f else "" for f in flags],
            # Overlay: the stripes sit on the bar's own colour. Plotly's default
            # makes the gaps between them transparent, so a white page shows
            # through and white labels inside the bar disappear.
            "fillmode": "overlay",
            "fgcolor": theme.plot_background,
            "solidity": _FLAG_SOLIDITY,
        }
    return marker


def _error_bars(
    o: _Options, bars: _Bars, s: int, theme: Theme, value_key: str
) -> dict[str, Any]:
    """Asymmetric error bars from the interval bounds, when ``ci`` is set."""
    if bars.low is None or bars.high is None:
        return {}
    values = bars.values[s]
    return {
        f"error_{value_key}": {
            "type": "data",
            "symmetric": False,
            "array": _plotly_list(bars.high[s] - values),
            "arrayminus": _plotly_list(values - bars.low[s]),
            "color": theme.neutral,
        }
    }


def _stack_totals(
    o: _Options,
    bars: _Bars,
    labels: Sequence[object],
    theme: Theme,
    horizontal: bool,
) -> go.Scatter:
    """Totals written past the end of each stack (a text-only trace).

    Plotly has no option for it. Negative segments stack the other way, so the
    total sits beyond whichever end the net value points to.
    """
    values = np.nan_to_num(bars.values)
    positive = np.where(values > 0, values, 0).sum(axis=0)
    negative = np.where(values < 0, values, 0).sum(axis=0)
    net = positive + negative
    anchor = np.where(net >= 0, positive, negative)
    if horizontal:
        where = ["middle right" if t >= 0 else "middle left" for t in net]
        coordinates = {"x": anchor.tolist(), "y": list(labels)}
    else:
        where = ["top center" if t >= 0 else "bottom center" for t in net]
        coordinates = {"x": list(labels), "y": anchor.tolist()}
    trace = go.Scatter(
        mode="text",
        text=[f"<b>{format_value(t, o.value_format)}</b>" for t in net],
        textposition=where,
        textfont={"size": theme.label_font_size, "color": theme.text},
        hoverinfo="skip",
        showlegend=False,
        cliponaxis=False,
        **coordinates,
    )
    return tag(trace, "reference", "total")


def _add_reference_lines(
    fig: go.Figure, o: _Options, bars: _Bars, theme: Theme, horizontal: bool
) -> None:
    """Add the average and target lines, as traces a role can select.

    A line must span the whole category axis, which a trace on that axis can't
    do (its ends sit at the outer bars' centres). Each line is drawn on a
    hidden overlay axis running from 0 to 1 across the plot instead.
    """
    lines = []
    if o.avg_line:
        drawn = bars.values
        if bars.other_label is not None:
            drawn = drawn[:, :-1]
        per_bar = np.nansum(drawn, axis=0) if o.barmode == "stack" else drawn
        average = float(np.nanmean(per_bar))
        label = f"Average: {format_value(average, o.value_format)}"
        lines.append(("average", average, label, theme.reference, "dash"))
    if o.target is not None:
        label = f"Target: {format_value(o.target, o.value_format)}"
        lines.append(("target", float(o.target), label, theme.reference_secondary,
                      "dot"))  # fmt: skip
    for group, value, label, color, dash in lines:
        if horizontal:
            # Above the plot area, where no bar can sit under the label.
            where = {"x": [value, value], "y": [0, 1], "yaxis": "y2"}
            position = "top center"
        else:
            where = {"x": [0, 1], "y": [value, value], "xaxis": "x2"}
            position = "top left"
        trace = go.Scatter(
            mode="lines+text",
            line={"color": color, "dash": dash},
            text=["", label],
            textposition=position,
            textfont={"color": color, "size": theme.label_font_size},
            hovertemplate=f"{label}<extra></extra>",
            showlegend=False,
            cliponaxis=False,
            **where,
        )
        fig.add_trace(tag(trace, "reference", group))
    if lines:
        overlay = {"overlaying": "y" if horizontal else "x", "range": [0, 1],
                   "visible": False, "fixedrange": True}  # fmt: skip
        fig.update_layout({"yaxis2" if horizontal else "xaxis2": overlay})
