"""Time-series plots: how a measure moves along an ordered axis, usually time.

``line_plot`` draws every query-result shape (pre-aggregated, raw rows with
``agg``, long with ``color``, wide with a list ``y``). A time axis is always
continuous: every calendar period between the first and the last is on the
chart, so a period without a row shows as a gap instead of being bridged
silently (decision 0012).

The function runs in stages, each a helper below:
1. ``_check_options``: option checks that need no data
2. ``_data``: intake, types, the x kind, nulls, calendar grain and buckets
3. ``_shape``: aggregation onto one shared x axis (the calendar grid for
   time), missing periods, rolling means, intervals, the overall line
4. ``_draw``: traces, labels, colours, reference lines, axes
"""

import datetime as dt
import math
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from numbers import Real

# Any: values read back from a table (to_dict) are the backend's own Python
# values, and Plotly specs are untyped dicts; neither has a type to name here.
from typing import Any, Literal, cast

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
)
from easy_viz._meta import Role, tag
from easy_viz._typing import (
    Agg,
    FrameLike,
    LineShape,
    MissingPeriods,
    TimeGrain,
    ValueLabels,
)
from easy_viz._validate import (
    check_choice,
    check_conflict,
    check_positive_int,
    check_range,
    check_requires,
    message,
    setting,
    warn_no_effect,
)
from easy_viz._warnings import warn
from easy_viz.plots._shared import (
    AGG_WORDS,
    CI_LEVEL,
    N_BOOT,
    RANDOM_STATE,
    ReferenceLine,
    add_reference_lines,
    check_color_map,
    check_interval_options,
    check_series_colours,
    check_shape,
    check_value_format,
    conflict,
    names,
    plotly_list,
    text,
    value_label,
    warn_hover_with_agg,
)
from easy_viz.stats.intervals import CiMethod, RandomState, interval
from easy_viz.stats.smoothing import rolling_mean
from easy_viz.theme._color import with_alpha
from easy_viz.theme.registry import ThemeName, resolve_theme
from easy_viz.theme.theme import Theme

FUNC = "line_plot"

# Option defaults, named so the no-effect warnings can tell a changed value.
VALUE_FORMAT = None

# show_markers=None draws markers when no series has more drawn points than
# this: on a short line each point is a measurement worth seeing, on a long one
# markers crowd into a thick band (the report notebook's rule).
MARKER_LIMIT = 30

# Opacity of the raw line under a rolling mean: the data stays readable, but
# the eye follows the smoothed line drawn at full strength over it.
_FADED = 0.35
# Fill opacity of a confidence band, and of the area under a line: light
# enough that lines and other series' fills show through.
_BAND_ALPHA = 0.2
_AREA_ALPHA = 0.15
# Line width of highlighted series, and of the overall line, as a multiple of
# the theme's line width: one step heavier than the series around them.
_EMPHASIS = 1.5
_OVERALL = 2.0
# Room either side of the first and last x position, as a share of the span:
# about one default marker at the default width, so end markers clear the axis
# line, without Plotly's 5 % strip of empty axis.
_X_MARGIN = 0.005
# The x range around a single date, which has no span to take a margin of.
_SINGLE_DATE_PAD = dt.timedelta(days=1)
# Height a value label takes above or below its point, as a share of the value
# range: one line of label text on a plot area of default height. A label
# whose side holds another line's point or label within this moves across.
_LABEL_ROOM = 0.06
# Log axes: Plotly labels every digit of each power of ten (2, 3, ... 9) when
# a range spans up to about three of them, which crowds the axis. From one
# power of ten up to this many, only 1, 2 and 5 are labelled; beyond, only
# the powers of ten.
_LOG_DIGIT_DECADES = 4.0

# Legend names of the overall line (decision 0012): with agg it is the aggregate
# over all rows; without, only the mean of the series' values, and named so.
OVERALL = "Overall"
MEAN_OF_SERIES = "Mean of series"
# Legend group of the dimmed series under highlight: one entry for all of
# them ("16 others"), so the legend lists what the chart is about.
_DIMMED_GROUP = "dimmed"

# Words for a calendar grain: the subtitle's adjective, and how the unified
# hover names a period (d3 time format, as Plotly reads it).
_GRAIN_ADJECTIVE: dict[str, str] = {
    "hour": "hourly",
    "day": "daily",
    "week": "weekly",
    "month": "monthly",
    "quarter": "quarterly",
    "year": "yearly",
}
_PERIOD_HOVER: dict[str, str] = {
    "hour": "%{x|%a %Y-%m-%d %H:00}",
    "day": "%{x|%a %Y-%m-%d}",
    "week": "Week of %{x|%Y-%m-%d}",
    "month": "%{x|%b %Y}",
    "quarter": "%{x|Q%q %Y}",
    "year": "%{x|%Y}",
}


@dataclass(frozen=True, slots=True)
class _Options:
    """Every option of one ``line_plot`` call, so the stages share one value."""

    x: str
    ys: list[str]
    color: str | None
    hover: list[str]
    agg: Agg | None
    time_grain: TimeGrain | Literal["auto"] | None
    missing_periods: MissingPeriods | None
    ci: CiMethod | None
    ci_level: float
    n_boot: int
    random_state: RandomState
    rolling: int | None
    show_markers: bool | None
    line_shape: LineShape
    fill_area: bool
    show_values: bool | ValueLabels
    value_format: str | None
    highlight: list[str]
    color_map: Mapping[str, str] | None
    overall_line: bool
    avg_line: bool
    target: float | None
    events: Mapping[str | float | dt.date | dt.datetime, str] | None
    log_x: bool
    log_y: bool
    rangeslider: bool
    x_title: str | None
    y_title: str | None

    @property
    def wide(self) -> bool:
        """Several measure columns, one series each."""
        return len(self.ys) > 1

    @property
    def multi(self) -> bool:
        """Whether the call asks for several series."""
        return self.color is not None or self.wide

    @property
    def gap_mode(self) -> MissingPeriods:
        """How empty periods are drawn; the default draws gaps."""
        return self.missing_periods or "gap"


@dataclass(frozen=True, slots=True)
class _Lines:
    """What ``line_plot`` draws: one row per series, one column per x position.

    Arrays hold NaN where a series has no point at an x position.
    """

    xs: list[object]  # x positions in drawing order: dates, numbers or categories
    kind: _data.ColumnKind
    grain: TimeGrain | None  # the calendar of a continuous time axis
    series: list[str]
    values: npt.NDArray[np.float64]  # as drawn: empty periods are 0 with "zero"
    observed: npt.NDArray[np.bool_]  # whether a row gave the value
    n: npt.NDArray[np.float64] | None  # rows behind each point, when agg is set
    low: npt.NDArray[np.float64] | None  # interval bounds, when ci is set
    high: npt.NDArray[np.float64] | None
    rolled: npt.NDArray[np.float64] | None  # the rolling mean, when rolling is set
    overall: npt.NDArray[np.float64] | None  # the overall line (rolled with rolling)
    hover: list[list[list[tuple[str, str]]]]  # extra hover lines per point
    empty: int  # periods without a row inside a series' own span

    @property
    def gridded(self) -> bool:
        """Whether x is a calendar grid, where a missing value is an empty period."""
        return self.grain is not None


def line_plot(
    df: FrameLike,
    x: str,
    y: str | list[str] | None = None,
    *,
    color: str | None = None,
    hover: str | list[str] | None = None,
    agg: Agg | None = None,
    time_grain: TimeGrain | Literal["auto"] | None = "auto",
    missing_periods: MissingPeriods | None = None,
    ci: CiMethod | None = None,
    ci_level: float = CI_LEVEL,
    n_boot: int = N_BOOT,
    random_state: RandomState = RANDOM_STATE,
    rolling: int | None = None,
    show_markers: bool | None = None,
    line_shape: LineShape = "linear",
    fill_area: bool = False,
    show_values: bool | ValueLabels = False,
    value_format: str | None = VALUE_FORMAT,
    highlight: str | list[str] | None = None,
    color_map: Mapping[str, str] | None = None,
    overall_line: bool = False,
    avg_line: bool = False,
    target: float | None = None,
    events: Mapping[str | float | dt.date | dt.datetime, str] | None = None,
    log_x: bool = False,
    log_y: bool = False,
    rangeslider: bool = False,
    title: str | None = None,
    subtitle: str | None = None,
    x_title: str | None = None,
    y_title: str | None = None,
    width: int | None = None,
    height: int | None = None,
    theme: ThemeName | Theme | None = None,
) -> go.Figure:
    """Show how a value moves along an ordered axis: trends, breaks, seasons.

    One line per series over ``x``, usually time. The table can come straight
    from a query in any shape: one row per period (plotted as-is), raw rows to
    bucket into days, weeks or months (``agg``), series stacked in a column
    (``color``) or side by side in several columns (a list ``y``). A time axis
    is always continuous: every period between the first and the last is on
    the chart, so a period the query has no row for shows as a gap, never as a
    line that quietly bridges it.

    Parameters
    ----------
    df : DataFrame-like
        The query result: pandas, polars, pyarrow, a DuckDB result, or anything
        else narwhals accepts. Never modified.
    x : str
        The axis column. Date, datetime and ISO-date text columns give a time
        axis; numbers a numeric axis; both are drawn in order. Text keeps the
        query's order (``ORDER BY``), so ``Mon, Tue, ...`` or funnel steps stay
        as they are.
    y : str, list of str or None, default None
        Measure column, or several (wide format: one line per column, named
        after it). May be omitted only with ``agg="count"``. Conflicts with
        ``color`` when it is a list.
    color : str or None, default None
        Column that splits the rows into one line per value (long format).
        Conflicts with a list ``y``, and can't be ``x`` itself.
    hover : str, list of str or None, default None
        Extra columns shown on hover. Only with ``agg=None``: a combined point
        has no single value for them, so with ``agg`` they are ignored with a
        warning (and their missing values drop no rows).
    agg : {"sum", "mean", "median", "min", "max", "count"} or None, default None
        ``None`` plots each row as-is and raises if an ``x`` (per series)
        repeats, also after bucketing into ``time_grain``. Otherwise rows are
        combined per point; ``"count"`` counts rows and needs no ``y``.
    time_grain : {"hour", "day", "week", "month", "quarter", "year"}, "auto" \
or None, default "auto"
        The calendar of a time ``x``. Dates are bucketed into this period
        (weeks start on Monday, as SQL's ``date_trunc('week', ...)``), and
        every period from the first to the last is on the axis. ``"auto"``
        reads the grain from the dates: the calendar grain they all sit on,
        whose step is the smallest gap between them; dates on no regular grid
        (raw timestamps, every other day) raise and ask for a grain; a single
        date shows no step, so it gets no calendar. ``None`` draws the points
        as they are, with no calendar. Points are placed by wall-clock time, so
        a time-zone-aware ``x`` with hours (an hourly grain, or ``None`` with
        times other than midnight) whose span crosses a daylight-saving change
        raises: convert it to UTC in the query, or use ``"day"`` or coarser.
        A grain other than
        ``"auto"`` needs a time ``x``.
    missing_periods : {"gap", "zero", "connect"} or None, default None
        How a period of the calendar without a row is drawn: ``"gap"`` breaks
        the line, ``"zero"`` draws 0 (right for counts and sums: no orders is
        zero orders), ``"connect"`` bridges it (points only where data exists).
        ``None`` draws gaps and warns how many periods are empty. Has no effect
        without a calendar (warned). ``"zero"`` conflicts with ``log_y``.
    ci : {"bootstrap", "sem"} or None, default None
        A shaded confidence band around each line. ``"bootstrap"`` works for
        the mean and the median, ``"sem"`` (mean ± z·standard error) for the
        mean only. Needs ``agg="mean"`` or ``"median"``; conflicts with
        ``rolling``. Points from a single row break the band.
    ci_level : float, default 0.95
        Confidence level, strictly between 0 and 1.
    n_boot : int, default 2000
        Bootstrap resamples per point (``ci="bootstrap"`` only).
    random_state : int, numpy Generator or None, default 0
        Seed of the bootstrap (``ci="bootstrap"`` only). The fixed default
        draws the same band on every run; ``None`` draws a new one.
    rolling : int or None, default None
        Draw the trailing mean over this many periods (or points, without a
        calendar) over each line; the raw line stays, faded. On a calendar the
        window counts periods, so ``rolling=7`` on daily data is always 7 days,
        also across empty ones. ``1`` is the value itself: it is ignored,
        with a warning. Conflicts with ``ci``.
    show_markers : bool or None, default None
        Markers on the data points. ``None``: markers when no series has more
        than 30 points. Without markers, a point between two empty periods
        still gets one, so no value is invisible.
    line_shape : {"linear", "spline", "hv", "vh", "hvh", "vhv"}, default "linear"
        How the line runs between points: straight, smoothed, or in steps.
    fill_area : bool, default False
        Shade the area between each line and zero. Conflicts with ``log_y``.
    show_values : bool or {"last", "ends", "extremes"}, default False
        Write values on the line the reader follows (the rolling mean when
        ``rolling`` is set): ``True`` on every point, ``"last"`` on the last,
        ``"ends"`` on the first and last, ``"extremes"`` on each series' max
        (above) and min (below). A label sits on the side of its point away
        from its line, and moves across when another line's point or label
        is close beside it at the same ``x``. With ``highlight``, only the
        highlighted series are labelled. The hover always has every value.
    value_format : str or None, default None
        Python format spec for values in labels, hover and reference lines,
        e.g. ``",.0f"`` or ``".1%"``. ``None``: four significant digits with
        k, M, B for thousands, millions, billions (``862.3k``, ``1.082M``).
    highlight : str, list of str or None, default None
        Series to emphasise (``color`` values or ``y`` columns): they keep
        their colours and are drawn slightly heavier, on top; the others use
        the theme's dimmed colour. Needs several series. Dimmed series need no
        colour of their own, so it also makes charts with many series possible;
        two or more share one legend entry ("16 others").
    color_map : mapping of str to str or None, default None
        A fixed colour per series (``color`` value or ``y`` column), so a
        series looks the same in every chart. Hex, ``rgb()`` or ``rgba()``;
        must cover every series drawn in colour (the highlighted ones, with
        ``highlight``), may hold others. Needs several series.
    overall_line : bool, default False
        One extra, heavier line in the theme's neutral colour: all series
        together at each ``x``. With ``agg``, the same aggregate over every row
        at that ``x`` ("Overall": a true total, mean, median or count); with
        ``agg=None``, only the mean of the series' values ("Mean of series").
        Needs ``color``; conflicts with a list ``y`` (averaging different
        measures means nothing).
    avg_line : bool, default False
        Dashed line at the mean of every point drawn, all series together.
    target : float or None, default None
        Dotted line at a target value, labelled.
    events : mapping of x value to str, or None, default None
        Labelled vertical lines at given ``x`` values, e.g.
        ``{"2025-04-01": "Price +12 %"}``. Keys are ISO-date strings, dates or
        datetimes for a time ``x``, numbers for a numeric ``x``, categories for
        a text ``x``; each must lie within the drawn ``x`` range.
    log_x : bool, default False
        Log-scale the x axis. Needs a numeric ``x``.
    log_y : bool, default False
        Log-scale the y axis. Every value drawn must be above 0, and so must
        both ends of a ``ci`` band (a band is never clipped: that would
        misstate the interval) and a ``target``. Conflicts with ``fill_area``
        and ``missing_periods="zero"``.
    rangeslider : bool, default False
        A range slider under the x axis, to zoom into a stretch of a long
        series. Needs a time or numeric ``x``.
    title : str or None, default None
        ``None`` builds one ("Total revenue over month by region"); ``""``
        shows none.
    subtitle : str or None, default None
        ``None`` states what the chart does to the data: the calendar grain,
        empty periods, the rolling window, the interval method, what the
        overall line is; ``""`` shows none.
    x_title, y_title : str or None, default None
        Axis titles. ``None`` uses the column name (``y`` with its
        aggregate); ``""`` shows none.
    width, height : int or None, default None
        Size in px. ``width=None`` uses ``ev.get_config().width``;
        ``height=None`` is 0.4 x the width.
    theme : {"dark", "light"}, Theme or None, default None
        Theme for this chart; ``None`` uses the global one (``ev.set_theme``).
        Line width and marker size come from it.

    Returns
    -------
    plotly.graph_objects.Figure
        A plain figure; finish anything the options don't cover on it.

    Raises
    ------
    ValueError
        For a missing column, a repeated ``x`` with ``agg=None``, dates on no
        calendar grain with ``time_grain="auto"``, conflicting options (the
        message names both), more coloured series than the theme has colours,
        or values ``log_y`` can't draw.
    TypeError
        If ``y`` is not numeric or ``df`` is not a table.

    Trace roles
    -----------
    - ``data``: the lines, one trace per series; ``group`` is the series name
      (``None`` for a single series). Value labels belong to these traces (to
      the rolling line's, with ``rolling``).
    - ``trendline``: the rolling mean of each series (``group`` = series).
    - ``ci``: the confidence band, two traces per series (upper bound, then
      the lower bound filled up to it; ``group`` = series).
    - ``reference``: the overall line (``group="overall"``), the average line
      (``group="average"``), the target line (``group="target"``) and the
      event lines (``group="event"``).

    Examples
    --------
    Daily orders as the query returns them, with a 7-day rolling mean and the
    day of a price change marked:

    >>> import easy_viz as ev
    >>> fig = ev.line_plot(daily, "day", "orders", rolling=7,
    ...                    events={"2025-04-01": "Price +12 %"})  # doctest: +SKIP

    Raw orders bucketed into weeks, one line per category, empty weeks as 0:

    >>> ev.line_plot(orders, "ordered_at", "revenue", color="category",
    ...              agg="sum", time_grain="week",
    ...              missing_periods="zero")  # doctest: +SKIP

    Mean order value per month with a bootstrap band:

    >>> ev.line_plot(orders, "month", "order_value", agg="mean",
    ...              ci="bootstrap")  # doctest: +SKIP
    """
    o = _Options(
        x=x,
        ys=names(y),
        color=color,
        hover=names(hover),
        agg=agg,
        time_grain=time_grain,
        missing_periods=missing_periods,
        ci=ci,
        ci_level=ci_level,
        n_boot=n_boot,
        random_state=random_state,
        rolling=rolling,
        show_markers=show_markers,
        line_shape=line_shape,
        fill_area=fill_area,
        show_values=show_values,
        value_format=value_format,
        highlight=names(highlight),
        color_map=color_map,
        overall_line=overall_line,
        avg_line=avg_line,
        target=target,
        events=events,
        log_x=log_x,
        log_y=log_y,
        rangeslider=rangeslider,
        x_title=x_title,
        y_title=y_title,
    )
    _check_options(o, y=y, highlight=highlight, width=width, height=height)
    if o.rolling == 1:
        # Warned as having no effect, so it has none: no second line, no
        # "1-day rolling mean" in the subtitle.
        o = replace(o, rolling=None)
    chosen = resolve_theme(theme, caller=FUNC)
    # With agg, hover has no effect: it isn't loaded, so its nulls can't drop rows
    # that the lines are computed from (only used columns count, rule 7).
    used_hover = hover if agg is None else None
    frame = _data.load(df, FUNC, {"x": x, "y": y, "color": color, "hover": used_hover})
    _data.require_numeric(frame, FUNC, {"y": y})
    frame = _data.parse_time(frame, FUNC, "x", x)
    kind = _data.column_kind(frame, x)
    _check_x_kind(o, kind)
    frame = _data.drop_nulls(frame, FUNC)
    grain: TimeGrain | None = None
    if kind == "temporal" and o.time_grain == "auto":
        if _single_date(frame, x):
            # One date shows no step: any grain read from it would be a guess,
            # so it is drawn without a calendar, as with time_grain=None.
            if o.missing_periods is not None:
                warn_no_effect(
                    FUNC, "missing_periods", o.missing_periods,
                    "with a single date (no calendar, so no empty periods)",
                )  # fmt: skip
        else:
            grain = _data.infer_grain(frame, FUNC, x)
    elif kind == "temporal" and o.time_grain is not None:
        # Not "auto" (the branch above): a grain, checked in _check_options.
        grain = cast(TimeGrain, o.time_grain)
    if kind == "temporal":
        _check_daylight_saving(frame, o, grain)
    if grain is not None:
        # Idempotent on dates already on the grain; buckets raw timestamps.
        frame = _data.truncate_time(frame, x, grain)
    lines = _shape(frame, o, kind, grain)
    _check_lines(o, lines, chosen, highlight)
    if lines.empty and o.missing_periods is None:
        assert grain is not None  # empty periods exist only on a calendar
        multi = " in at least one series" if len(lines.series) > 1 else ""
        warn(
            message(
                FUNC,
                f"{lines.empty} of {len(lines.xs)} {grain}s have no row{multi} and "
                "are drawn as gaps",
                "Set missing_periods='gap' to keep the gaps without this warning, "
                "'zero' to draw them as 0, or 'connect' to bridge them",
            )
        )
    events_at = _event_positions(o, lines)
    fig = _draw(o, lines, chosen, events_at)
    apply_base_layout(
        fig,
        title=title if title is not None else _auto_title(o),
        subtitle=subtitle if subtitle is not None else _auto_subtitle(o, lines),
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
            )
        )
    return fig


# --- 1. option checks ----------------------------------------------------------------


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
        ("missing_periods", o.missing_periods, MissingPeriods),
    ):
        if value is not None:
            check_choice(FUNC, param, value, alias)
    if o.time_grain is not None and o.time_grain != "auto":
        check_choice(FUNC, "time_grain", o.time_grain, TimeGrain)
    check_choice(FUNC, "line_shape", o.line_shape, LineShape)
    check_shape(
        FUNC,
        x=o.x,
        y=y,
        ys=o.ys,
        color=o.color,
        agg=o.agg,
        same_column_fix="color splits the rows into one line per value; to "
        "emphasise some x values, use events",
    )
    check_interval_options(
        FUNC,
        ci=o.ci,
        agg=o.agg,
        ci_level=o.ci_level,
        n_boot=o.n_boot,
        random_state=o.random_state,
    )
    if o.rolling is not None:
        check_positive_int(FUNC, "rolling", o.rolling)
        check_conflict(FUNC, ci=o.ci, rolling=o.rolling)
        if o.rolling == 1:
            warn_no_effect(
                FUNC, "rolling", o.rolling, "(a 1-period mean is the value itself)",
                "Use a window of 2 or more, or remove it",
            )  # fmt: skip
    _check_drawing(o)
    _check_colour(o, highlight=highlight)
    _check_lines_options(o)
    for param, size in (("width", width), ("height", height)):
        if size is not None:
            check_positive_int(FUNC, param, size)


def _check_drawing(o: _Options) -> None:
    """Check markers, labels, fills and the log axes."""
    for param, value in (
        ("fill_area", o.fill_area),
        ("log_x", o.log_x),
        ("log_y", o.log_y),
        ("rangeslider", o.rangeslider),
        ("overall_line", o.overall_line),
        ("avg_line", o.avg_line),
    ):
        if not isinstance(value, bool):
            raise TypeError(
                message(
                    FUNC, f"{setting(param, value)} is not valid", "Use True or False"
                )
            )
    if o.show_markers is not None and not isinstance(o.show_markers, bool):
        raise TypeError(
            message(
                FUNC,
                f"{setting('show_markers', o.show_markers)} is not valid",
                "Use True, False, or None for automatic",
            )
        )
    if isinstance(o.show_values, str):
        check_choice(FUNC, "show_values", o.show_values, ValueLabels)
    elif not isinstance(o.show_values, bool):
        raise TypeError(
            message(
                FUNC,
                f"{setting('show_values', o.show_values)} is not valid",
                "Use True, False, 'last', 'ends' or 'extremes'",
            )
        )
    check_value_format(FUNC, o.value_format)
    warn_hover_with_agg(FUNC, o.hover, o.agg, "point")
    if o.log_y:
        check_conflict(FUNC, fill_area=o.fill_area, log_y=o.log_y)
        if o.missing_periods == "zero":
            raise ValueError(
                conflict(FUNC, "missing_periods", "zero", "log_y", o.log_y)
            )


def _check_colour(o: _Options, *, highlight: object) -> None:
    """Check highlight and color_map."""
    if highlight is not None:
        if not all(isinstance(h, str) for h in o.highlight) or not o.highlight:
            raise TypeError(
                message(
                    FUNC,
                    f"{setting('highlight', highlight)} is not a series name",
                    "Pass a value of color (or a column of y) as text, or a list "
                    "of them",
                )
            )
        if not o.multi:
            raise ValueError(
                message(
                    FUNC,
                    f"{setting('highlight', highlight)} needs several series",
                    "Set color, or pass a list y, to draw several lines",
                )
            )
    check_color_map(FUNC, o.color_map, multi=o.multi, fix="Set color, or pass a list y")


def _check_lines_options(o: _Options) -> None:
    """Check the overall line, the reference lines and the events."""
    if o.overall_line and o.wide:
        raise ValueError(
            message(
                FUNC,
                f"overall_line=True cannot be combined with {setting('y', o.ys)}",
                "The overall line combines one measure across series; averaging "
                "different columns means nothing. Use color for series of one "
                "measure, or remove overall_line",
            )
        )
    check_requires(
        FUNC, "overall_line", o.overall_line, needs="color", needs_value=o.color
    )
    if o.target is not None:
        check_range(FUNC, "target", o.target)
        if o.log_y and o.target <= 0:
            raise ValueError(
                message(
                    FUNC,
                    f"{setting('target', o.target)} cannot be drawn with "
                    "log_y=True: a log axis has no 0 or negative values",
                    "Remove log_y, or set a target above 0",
                )
            )
    if o.events is not None:
        if not isinstance(o.events, Mapping):
            raise TypeError(
                message(
                    FUNC,
                    f"{setting('events', o.events)} is not a mapping",
                    "Pass a dict of x value to label, e.g. "
                    "{'2025-04-01': 'Price +12 %'}",
                )
            )
        for key, label in o.events.items():
            if not isinstance(label, str):
                raise TypeError(
                    message(
                        FUNC,
                        f"events[{key!r}]={label!r} is not a label",
                        "Give every event a text label",
                    )
                )


def _check_x_kind(o: _Options, kind: _data.ColumnKind) -> None:
    """Check the options that depend on what kind of axis ``x`` gives."""
    described = {
        "temporal": "a time column",
        "numeric": "a numeric column",
        "categorical": "a text column",
    }[kind]
    x_is = f"{setting('x', o.x)} is {described}"
    if o.log_x and kind != "numeric":
        raise ValueError(
            message(
                FUNC,
                f"log_x=True needs a numeric x, but {x_is}",
                "Remove log_x, or pass a numeric x",
            )
        )
    if o.rangeslider and kind == "categorical":
        raise ValueError(
            message(
                FUNC,
                f"rangeslider=True needs a time or numeric x, but {x_is}",
                "Remove rangeslider, or pass a date or numeric x",
            )
        )
    if kind != "temporal" and o.time_grain not in ("auto", None):
        raise ValueError(
            message(
                FUNC,
                f"{setting('time_grain', o.time_grain)} needs a time x, but {x_is}",
                "Remove time_grain, or pass a date column as x",
            )
        )
    if o.missing_periods is not None:
        if kind != "temporal":
            warn_no_effect(
                FUNC, "missing_periods", o.missing_periods,
                f"without a calendar: {x_is}",
            )  # fmt: skip
        elif o.time_grain is None:
            warn_no_effect(
                FUNC, "missing_periods", o.missing_periods,
                "with time_grain=None (no calendar, so no empty periods)",
            )  # fmt: skip


def _check_lines(o: _Options, lines: _Lines, theme: Theme, highlight: object) -> None:
    """Check what needs the shaped data: series names, colours, log values."""
    missing = [h for h in o.highlight if h not in lines.series]
    if missing:
        listed = ", ".join(repr(s) for s in lines.series)
        raise ValueError(
            message(
                FUNC,
                f"{setting('highlight', highlight)} names {missing[0]!r}, which is "
                f"not a series",
                f"Use one of {listed}",
            )
        )
    check_series_colours(
        FUNC,
        _coloured(o, lines),
        o.color_map,
        theme,
        "Filter the query to fewer series, or highlight the ones that matter "
        "(dimmed series need no colour of their own); or pass color_map, or use "
        "a theme with a longer colorway",
    )
    if o.log_y:
        drawn = [lines.values]
        if lines.overall is not None:
            drawn.append(lines.overall[np.newaxis, :])
        values = np.concatenate([d.ravel() for d in drawn])
        bad = int(np.sum(values[~np.isnan(values)] <= 0))
        if bad:
            raise ValueError(
                message(
                    FUNC,
                    f"log_y=True needs values above 0, but {bad} drawn value"
                    f"{'s are' if bad > 1 else ' is'} 0 or less",
                    "Remove log_y, or filter those rows in the query",
                )
            )
        # A band's lower ends can reach 0 or below while every value is above
        # it (a wide interval of a small group). Clipping them would misstate
        # the interval, so it is refused.
        if lines.low is not None:
            ends = int(np.sum(lines.low[~np.isnan(lines.low)] <= 0))
            if ends:
                raise ValueError(
                    message(
                        FUNC,
                        f"log_y=True cannot draw {ends} confidence-band "
                        f"end{'s' if ends > 1 else ''} at or below 0 "
                        f"({setting('ci', o.ci)}): a log axis has no 0 or "
                        "negative values",
                        "Remove log_y to see the whole band, or remove ci",
                    )
                )


def _check_daylight_saving(
    frame: _data.Frame, o: _Options, grain: TimeGrain | None
) -> None:
    """Raise when hours of a time-zone-aware x cross a daylight-saving change.

    Points are placed by wall-clock time. Across a change the wall clock
    repeats an hour (autumn: two rows on one position, one silently lost or
    summed) or skips one (spring: an hour that never existed shown as empty).
    Positions of a day or coarser are local calendar days, which stay right.
    """
    if grain is not None:
        below_a_day = grain == "hour"
    else:
        moments = _data.time_array(frame, o.x)
        moments = moments[~np.isnat(moments)]
        below_a_day = bool(np.any(moments != moments.astype("datetime64[D]")))
    if not below_a_day or not _data.utc_offset_changes(frame, o.x):
        return
    zone = frame.schema[o.x].time_zone  # type: ignore[attr-defined]
    raise ValueError(
        message(
            FUNC,
            f"{setting('x', o.x)} is in time zone {zone!r} and its hours cross a "
            f"daylight-saving change, so with {setting('time_grain', o.time_grain)} "
            "an hour repeats or is skipped on the wall clock",
            "Convert the column to UTC (or a fixed offset) in the query, or set "
            "time_grain='day' or coarser",
        )
    )


def _series_colour(o: _Options, name: str, coloured: list[str], theme: Theme) -> str:
    """Colour of a series drawn in colour: its ``color_map`` entry, else colorway.

    ``color_map`` is read first: with it, there can be more coloured series
    than the colorway has colours (``_check_lines`` allows that).
    """
    if o.color_map is not None and name in o.color_map:
        return o.color_map[name]
    return theme.colorway[coloured.index(name)]


def _single_date(frame: _data.Frame, column: str) -> bool:
    """Whether a time column holds one distinct moment only."""
    return int(np.unique(_data.time_array(frame, column)).size) == 1


def _coloured(o: _Options, lines: _Lines) -> list[str]:
    """Return the series drawn in a colour of their own (the rest are dimmed)."""
    if o.highlight:
        return [s for s in lines.series if s in o.highlight]
    return list(lines.series)


# --- 3. shaping ----------------------------------------------------------------------


def _shape(
    frame: _data.Frame,
    o: _Options,
    kind: _data.ColumnKind,
    grain: TimeGrain | None,
) -> _Lines:
    """Aggregate onto one shared x axis; add rolling means, bands, the overall line."""
    key_params = {"x": o.x, "color": o.color}
    key_columns = [c for c in (o.x, o.color) if c is not None]
    table, value_columns = _data.aggregate(frame, FUNC, key_params, o.ys, o.agg)
    rows = table.to_dict(as_series=False)
    series = (
        list(dict.fromkeys(str(v) for v in rows[o.color]))
        if o.color is not None
        else list(value_columns)
    )
    xs, positions = _axis(table, rows[o.x], o.x, kind, grain)
    # Python x values (as to_dict gives them) to their axis position, for the
    # other tables built from the same frame: counts, intervals, overall.
    at: dict[object, int] = {}
    for value, position in zip(rows[o.x], positions, strict=True):
        at[value] = position
    which = {name: index for index, name in enumerate(series)}
    shape = (len(series), len(xs))
    values = np.full(shape, np.nan)
    hover: list[list[list[tuple[str, str]]]] = [[[] for _ in xs] for _ in series]

    def cells(table_rows: Mapping[str, list[Any]], i: int) -> list[tuple[int, int]]:
        """Return the (series, position) cells row ``i`` of a table fills."""
        position = at[table_rows[o.x][i]]
        if o.color is not None:
            return [(which[str(table_rows[o.color][i])], position)]
        return [(k, position) for k in range(len(series))]

    for i in range(len(table)):
        for s, p in cells(rows, i):
            values[s, p] = rows[value_columns[s if o.wide else 0]][i]
            if o.agg is None:
                hover[s][p] = [(h, text(rows[h][i])) for h in o.hover]
    observed = ~np.isnan(values)
    empty = _empty_periods(observed) if grain is not None else 0
    if grain is not None and o.gap_mode == "zero":
        values = np.where(observed, values, 0.0)

    n = low = high = None
    if o.agg is not None:
        n = np.full(shape, np.nan)
        counted, count_columns = _data.aggregate(
            frame.select(*key_columns, *o.ys), FUNC, key_params, o.ys, "count"
        )
        count_rows = counted.to_dict(as_series=False)
        for i in range(len(counted)):
            for s, p in cells(count_rows, i):
                n[s, p] = count_rows[count_columns[0]][i]
    if o.ci is not None and o.agg in ("mean", "median"):
        low, high = np.full(shape, np.nan), np.full(shape, np.nan)
        for k, column in enumerate(o.ys):
            for key, sample in _data.group_arrays(frame, key_columns, column).items():
                s = which[str(key[1])] if o.color is not None else k
                result = interval(
                    sample,
                    statistic=o.agg,
                    method=o.ci,
                    level=o.ci_level,
                    n_boot=o.n_boot,
                    random_state=o.random_state,
                )
                low[s, at[key[0]]] = result.low
                high[s, at[key[0]]] = result.high

    gridded = grain is not None
    overall = None
    if o.overall_line:
        overall = _overall(frame, o, values, at, len(xs))
        if gridded and o.gap_mode == "zero":
            overall = np.nan_to_num(overall)
    rolled = None
    if o.rolling is not None:
        rolled = np.vstack([_roll(v, o.rolling, gridded) for v in values])
        if overall is not None:
            overall = _roll(overall, o.rolling, gridded)
    return _Lines(
        xs, kind, grain, series, values, observed, n, low, high, rolled, overall,
        hover, empty,
    )  # fmt: skip


def _axis(
    table: _data.Frame,
    raw: Sequence[object],
    column: str,
    kind: _data.ColumnKind,
    grain: TimeGrain | None,
) -> tuple[list[object], list[int]]:
    """Return the x positions in drawing order, and each table row's position.

    Time on a calendar: every period from the first to the last. Time without
    one, and numbers: the distinct values, sorted. Text: the distinct values
    in first-appearance (query) order.
    """
    if kind == "categorical":
        order = {value: index for index, value in enumerate(dict.fromkeys(raw))}
        return list(order), [order[value] for value in raw]
    if kind == "temporal":
        moments = _data.time_array(table, column)
        if grain is not None:
            first, last = moments.min().item(), moments.max().item()
            grid = np.array(_data.period_grid(first, last, grain), dtype=moments.dtype)
        else:
            grid = np.unique(moments)
        positions = np.searchsorted(grid, moments)
        return list(grid.tolist()), positions.tolist()
    numbers = _data.to_float_array(table, column)
    distinct = np.unique(numbers)
    return list(distinct.tolist()), np.searchsorted(distinct, numbers).tolist()


def _empty_periods(observed: npt.NDArray[np.bool_]) -> int:
    """Count the periods empty in some series between its first and last value.

    Before a series starts or after it ends nothing is drawn, so nothing can be
    misread; a hole inside it is what a bridging line would hide.
    """
    inside = np.zeros_like(observed)
    for s, row in enumerate(observed):
        present = np.flatnonzero(row)
        if present.size:
            inside[s, present[0] : present[-1] + 1] = True
    return int(np.any(inside & ~observed, axis=0).sum())


def _overall(
    frame: _data.Frame,
    o: _Options,
    values: npt.NDArray[np.float64],
    at: Mapping[object, int],
    size: int,
) -> npt.NDArray[np.float64]:
    """Compute the overall line: all rows per x with agg, else the series' mean."""
    if o.agg is None:
        with warnings.catch_warnings():
            # A position no series has a value at is NaN, which is what we want.
            warnings.simplefilter("ignore", RuntimeWarning)
            mean: npt.NDArray[np.float64] = np.nanmean(values, axis=0)
        return mean
    combined, columns = _data.aggregate(
        frame.select(o.x, *o.ys), FUNC, {"x": o.x}, o.ys, o.agg
    )
    rows = combined.to_dict(as_series=False)
    overall = np.full(size, np.nan)
    for value, result in zip(rows[o.x], rows[columns[0]], strict=True):
        overall[at[value]] = result
    return overall


def _roll(
    values: npt.NDArray[np.float64], window: int, gridded: bool
) -> npt.NDArray[np.float64]:
    """Return the rolling mean of a line, where the line itself has a value.

    On a calendar the window counts periods (empty ones included, as NaN);
    without one it counts the series' own points.
    """
    present = ~np.isnan(values)
    rolled = np.full(len(values), np.nan)
    if gridded:
        rolled[present] = rolling_mean(values, window)[present]
    else:
        rolled[present] = rolling_mean(values[present], window)
    return rolled


# --- 4. drawing ----------------------------------------------------------------------


def _event_positions(o: _Options, lines: _Lines) -> list[tuple[object, str]]:
    """Read each ``events`` key as a value of the x axis, and check its range."""
    if not o.events:
        return []
    xs = lines.xs
    if lines.kind == "categorical":
        labels = {text(value): value for value in xs}
        found = []
        for key, label in o.events.items():
            if not isinstance(key, str) or key not in labels:
                shown = ", ".join(repr(k) for k in list(labels)[:10])
                raise ValueError(
                    message(
                        FUNC,
                        f"events has the key {key!r}, which is not a value of "
                        f"{setting('x', o.x)}",
                        f"Use one of {shown}",
                    )
                )
            found.append((labels[key], label))
        return found
    first, last = xs[0], xs[-1]
    span = f"{text(first)} to {text(last)}"
    found = []
    for key, label in o.events.items():
        position = _event_value(o, lines, key, span)
        inside = first <= position <= last  # type: ignore[operator]
        if lines.grain is not None and isinstance(position, dt.datetime):
            # Any moment within the last period is still on the chart.
            inside = first <= _data.floor_time(position, lines.grain) <= last  # type: ignore[operator]
        if not inside:
            raise ValueError(
                message(
                    FUNC,
                    f"events has the key {key!r}, outside the x range ({span})",
                    "Use x values within the data, or filter the events",
                )
            )
        found.append((position, label))
    return found


def _event_value(o: _Options, lines: _Lines, key: object, span: str) -> object:
    """Turn one ``events`` key into a number or a naive datetime, as x is."""
    wrong = message(
        FUNC,
        f"events has the key {key!r}, which is not a "
        f"{'date' if lines.kind == 'temporal' else 'number'} like "
        f"{setting('x', o.x)} ({span})",
        "Use ISO-date strings or dates for a time x, numbers for a numeric x",
    )
    if lines.kind == "numeric":
        if isinstance(key, bool) or not isinstance(key, Real):
            raise ValueError(wrong)
        return float(key)
    if isinstance(key, str):
        try:
            return dt.datetime.fromisoformat(key).replace(tzinfo=None)
        except ValueError:
            raise ValueError(wrong) from None
    if isinstance(key, dt.datetime):
        return key.replace(tzinfo=None)
    if isinstance(key, dt.date):
        return dt.datetime.combine(key, dt.time())
    raise ValueError(wrong)


def _series_name(o: _Options, lines: _Lines, s: int) -> str:
    """Legend name of series ``s``: its value, its column, or what it measures."""
    if o.multi:
        return lines.series[s]
    return value_label(o.agg, o.ys)


def _window(o: _Options, lines: _Lines) -> str:
    """'7-day mean' (on a calendar) or '7-point mean'."""
    unit = lines.grain or "point"
    return f"{o.rolling}-{unit} mean"


def _draw(
    o: _Options,
    lines: _Lines,
    theme: Theme,
    events_at: Sequence[tuple[object, str]],
) -> go.Figure:
    """Build the line, band and reference traces, and the axes."""
    categorical = lines.kind == "categorical"
    xs: list[object] = (
        [escape_text(text(value)) for value in lines.xs] if categorical else lines.xs
    )
    connect = not lines.gridded or o.gap_mode == "connect"
    counts = np.sum(~np.isnan(lines.values), axis=1)
    markers = (
        bool(np.all(counts <= MARKER_LIMIT))
        if o.show_markers is None
        else o.show_markers
    )
    coloured = _coloured(o, lines)
    dimmed_count = len(lines.series) - len(coloured)
    # Two or more dimmed series share one legend entry ("16 others"), shown on
    # the first one drawn: the legend lists what the chart is about.
    grouped = dimmed_count > 1
    entries = len(coloured) + (1 if grouped else dimmed_count)
    legend = entries + (1 if lines.overall is not None else 0) > 1
    followed = lines.rolled if lines.rolled is not None else lines.values
    # Labels go on the line the reader follows; dimmed series carry none.
    labels = _place_labels(
        o, lines, followed, [name in coloured for name in lines.series]
    )

    # Dimmed series first, so the highlighted ones are drawn over them.
    order = sorted(range(len(lines.series)), key=lambda s: lines.series[s] in coloured)
    fig = go.Figure()
    for s in order:
        name = lines.series[s]
        dimmed = name not in coloured
        colour = (
            _series_colour(o, name, coloured, theme) if not dimmed else theme.dimmed
        )
        width = theme.line_width * (_EMPHASIS if o.highlight and not dimmed else 1)
        group = name if o.multi else None
        legend_name = escape_text(_series_name(o, lines, s))
        # Dimmed series are background: markers on them would only add clutter.
        style = _Style(
            colour, width, markers and not dimmed, connect, group, legend_name, s + 1
        )
        if dimmed and grouped:
            first = s == order[0]
            style = replace(
                style,
                name=f"{dimmed_count} others" if first else legend_name,
                legend_group=_DIMMED_GROUP,
                # After the highlighted series, before the overall line.
                rank=len(lines.series) + 1,
                in_legend=first,
            )
        if lines.low is not None and lines.high is not None:
            for trace in _band(o, lines, s, xs, style):
                fig.add_trace(trace)
        smoothed = lines.rolled is not None
        fig.add_trace(
            _line(
                o, lines, xs, lines.values[s],
                # Under a rolling mean the raw line is background: no markers.
                replace(style, markers=style.markers and not smoothed), theme,
                role="data",
                hovers=_hovers(o, lines, s),
                faded=smoothed,
                labels=None if smoothed else labels[s],
            )
        )  # fmt: skip
        if lines.rolled is not None:
            window = escape_text(f"{_series_name(o, lines, s)}, {_window(o, lines)}")
            if not (dimmed and grouped):
                style = replace(style, name=window)
            fig.add_trace(
                _line(
                    o, lines, xs, followed[s], style, theme,
                    role="trendline",
                    hovers=_simple_hovers(o, window, followed[s]),
                    labels=labels[s],
                )
            )  # fmt: skip

    if lines.overall is not None:
        label = OVERALL if o.agg is not None else MEAN_OF_SERIES
        if lines.rolled is not None:
            label = f"{label}, {_window(o, lines)}"
        style = _Style(
            theme.neutral, theme.line_width * _OVERALL, markers, connect,
            "overall", label, len(lines.series) + 2,
        )  # fmt: skip
        fig.add_trace(
            _line(
                o, lines, xs, lines.overall, style, theme,
                role="reference",
                hovers=_simple_hovers(o, label, lines.overall),
                labels=None,
            )
        )  # fmt: skip

    references: list[ReferenceLine] = []
    if o.avg_line:
        average = float(np.nanmean(lines.values))
        label = f"Average: {format_value(average, o.value_format)}"
        references.append(
            ReferenceLine("average", average, label, theme.reference, "dash")
        )
    if o.target is not None:
        label = f"Target: {format_value(o.target, o.value_format)}"
        references.append(
            ReferenceLine(
                "target", float(o.target), label, theme.reference_secondary, "dot"
            )
        )
    add_reference_lines(fig, references, theme, on="y")
    add_reference_lines(
        fig,
        [
            ReferenceLine(
                "event",
                escape_text(text(value)) if categorical else value,
                escape_text(label),
                theme.reference_secondary,
                "longdash",
            )
            for value, label in events_at
        ],
        theme,
        on="x",
    )
    fig.update_layout(
        xaxis=_x_axis(o, lines, xs, [value for value, _ in events_at]),
        yaxis=_y_axis(o, lines),
        hovermode="x unified",
        showlegend=legend,
        legend={
            "title": {"text": escape_text(o.color) if o.color else ""},
            "traceorder": "normal",
        },
    )
    if not legend:
        fig.update_traces(showlegend=False)
    return fig


@dataclass(frozen=True, slots=True)
class _Labels:
    """The value labels of one line: text and Plotly text position per point."""

    texts: list[str]  # "" where a point carries no label
    positions: list[str]


@dataclass(frozen=True, slots=True)
class _Style:
    """How one line is drawn, shared by its band, raw line and rolling line."""

    colour: str
    width: float
    markers: bool
    connect: bool
    group: str | None  # the role group: the series name
    name: str  # escaped legend name
    rank: int  # legend position: series order, the dimmed group, then overall
    legend_group: str | None = None  # None: the role group
    in_legend: bool = True  # False for dimmed series behind their group's entry


def _line(
    o: _Options,
    lines: _Lines,
    xs: list[object],
    values: npt.NDArray[np.float64],
    style: _Style,
    theme: Theme,
    *,
    role: Role,
    hovers: list[str],
    faded: bool = False,
    labels: _Labels | None,
) -> go.Scatter:
    """One line trace, with its markers, value labels and area fill."""
    present = ~np.isnan(values)
    # Without markers, a point between two gaps would be invisible: it gets one.
    alone = present & ~np.roll(present, 1) & ~np.roll(present, -1)
    if len(values) > 1:
        alone[0] = present[0] and not present[1]
        alone[-1] = present[-1] and not present[-2]
    elif len(values) == 1:
        alone[0] = bool(present[0])
    isolated = alone if not style.connect else np.zeros_like(alone)
    mode = ["lines"]
    marker: dict[str, Any] = {"color": style.colour, "size": theme.marker_size}
    if style.markers:
        mode.append("markers")
    elif isolated.any():
        mode.append("markers")
        marker["size"] = [theme.marker_size if a else 0 for a in isolated]
    trace_text: dict[str, Any] = {}
    if labels is not None and any(labels.texts):
        mode.append("text")
        trace_text = {
            "text": labels.texts,
            "textposition": labels.positions,
            "textfont": {"size": theme.label_font_size, "color": style.colour},
        }
    fill: dict[str, Any] = {}
    # The area goes under the line the reader follows: the rolling mean, if any.
    if o.fill_area and role != "reference" and not faded:
        fill = {"fill": "tozeroy", "fillcolor": with_alpha(style.colour, _AREA_ALPHA)}
    trace = go.Scatter(
        x=xs,
        y=plotly_list(values),
        name=style.name,
        mode="+".join(mode),
        line={"color": style.colour, "width": style.width, "shape": o.line_shape},
        marker=marker,
        connectgaps=style.connect,
        opacity=_FADED if faded else None,
        legendgroup=style.legend_group or style.group,
        legendrank=style.rank,
        showlegend=style.in_legend and not faded,
        hovertext=hovers,
        hovertemplate="%{hovertext}<extra></extra>",
        cliponaxis=False,
        **trace_text,
        **fill,
    )
    return tag(trace, role, style.group)


def _band(
    o: _Options, lines: _Lines, s: int, xs: list[object], style: _Style
) -> list[go.Scatter]:
    """Build the confidence band of series ``s``: two traces, filled between.

    The upper bound first, then the lower bound with ``fill="tonexty"``, which
    fills up to the trace before it.
    """
    assert lines.low is not None and lines.high is not None
    traces = []
    for bound, fill in ((lines.high[s], None), (lines.low[s], "tonexty")):
        trace = go.Scatter(
            x=xs,
            y=plotly_list(bound),
            mode="lines",
            line={"width": 0, "color": style.colour, "shape": o.line_shape},
            fill=fill,
            fillcolor=with_alpha(style.colour, _BAND_ALPHA),
            connectgaps=style.connect,
            legendgroup=style.legend_group or style.group,
            showlegend=False,
            hoverinfo="skip",
        )
        traces.append(tag(trace, "ci", style.group))
    return traces


def _place_labels(
    o: _Options,
    lines: _Lines,
    followed: npt.NDArray[np.float64],
    labelled: Sequence[bool],
) -> list[_Labels | None]:
    """Choose which points of each line carry a value label, and where.

    Each label first takes the side of its point away from its own line
    (``_label_points``). Labels are then kept apart from the other lines at
    the same x: a label whose side holds another line's point, or a label
    already placed, within ``_LABEL_ROOM`` of the value range moves to the
    other side of its point, if that side is clear. Higher points are placed
    first, so of two close labels the upper one goes above and the lower one
    below. Labels at different x are not compared: Plotly has no collision
    check for text, and a sideways clash needs points closer than a label's
    width.
    """
    if o.show_values is False:
        return [None] * len(followed)
    # Room is measured on the axis scale: in powers of ten on a log axis
    # (log_y has already refused values of 0 or less).
    scaled = np.log10(followed) if o.log_y else followed
    drawn = scaled
    if lines.overall is not None:
        overall = np.log10(lines.overall) if o.log_y else lines.overall
        drawn = np.vstack([scaled, overall])
    finite = drawn[np.isfinite(drawn)]
    room = _LABEL_ROOM * float(finite.max() - finite.min()) if finite.size else 0.0

    wanted = [
        (s, p, above)
        for s, row in enumerate(scaled)
        if labelled[s]
        for p, above in _label_points(o, row)
    ]
    taken: dict[int, list[tuple[float, float]]] = {}
    sides: dict[tuple[int, int], bool] = {}
    for s, p, above in sorted(wanted, key=lambda w: (w[1], -scaled[w[0], w[1]])):
        value = float(scaled[s, p])
        others = [float(v) for k, v in enumerate(drawn[:, p]) if k != s]
        here = taken.setdefault(p, [])
        if not _clear(value, above, room, others, here) and _clear(
            value, not above, room, others, here
        ):
            above = not above
        sides[s, p] = above
        here.append(_label_span(value, above, room))

    result: list[_Labels | None] = []
    for s, row in enumerate(followed):
        if not labelled[s]:
            result.append(None)
            continue
        texts = [""] * len(row)
        positions = ["top center"] * len(row)
        for (k, p), above in sides.items():
            if k == s:
                texts[p] = format_value(float(row[p]), o.value_format)
                positions[p] = f"{'top' if above else 'bottom'} {_lean(lines, p)}"
        result.append(_Labels(texts, positions))
    return result


def _label_span(value: float, above: bool, room: float) -> tuple[float, float]:
    """Return the stretch of the value axis a label takes beside its point."""
    return (value, value + room) if above else (value - room, value)


def _clear(
    value: float,
    above: bool,
    room: float,
    others: Sequence[float],
    taken: Sequence[tuple[float, float]],
) -> bool:
    """Whether a label's side holds no other line's point and no other label."""
    low, high = _label_span(value, above, room)
    if any(low < v < high for v in others if math.isfinite(v)):
        return False
    return all(high <= a or low >= b for a, b in taken)


def _label_points(
    o: _Options, values: npt.NDArray[np.float64]
) -> list[tuple[int, bool]]:
    """Return the labelled points of one line, each with whether it sits above.

    ``"extremes"``: the max above its point, the min below. Otherwise a label
    sits on the side away from its line: above a point at or above the mean
    of its neighbours (a peak, or a bend that opens upwards), below one under
    it. An end point has one neighbour, and the label goes away from it.
    """
    present = np.flatnonzero(np.isfinite(values))
    if not present.size:
        return []
    if o.show_values == "extremes":
        high = int(present[np.argmax(values[present])])
        low = int(present[np.argmin(values[present])])
        return [(high, True)] if high == low else [(high, True), (low, False)]
    if o.show_values == "last":
        chosen = [len(present) - 1]
    elif o.show_values == "ends":
        chosen = sorted({0, len(present) - 1})
    else:  # True: every point
        chosen = list(range(len(present)))
    points = []
    for i in chosen:
        neighbours = [
            values[present[j]] for j in (i - 1, i + 1) if 0 <= j < len(present)
        ]
        mean = float(np.mean(neighbours)) if neighbours else -math.inf
        points.append((int(present[i]), bool(values[present[i]] >= mean)))
    return points


def _lean(lines: _Lines, p: int) -> str:
    """Where a label leans: inward at the ends of a time or numeric axis.

    The axis starts and ends at the first and last point (``_x_range``), so
    a centred label there would spill over the axis line. A text axis keeps
    half a category of room at each end.
    """
    if lines.kind == "categorical" or len(lines.xs) == 1:
        return "center"
    if p == 0:
        return "right"
    return "left" if p == len(lines.xs) - 1 else "center"


def _hovers(o: _Options, lines: _Lines, s: int) -> list[str]:
    """Hover text of each point of series ``s``: value, rows, interval, extras."""
    # A wide table's series are measures: name them with their aggregate.
    shown = value_label(o.agg, o.ys, lines.series[s]) if o.wide else None
    name = escape_text(shown or _series_name(o, lines, s))
    hovers = []
    for p, value in enumerate(lines.values[s]):
        if math.isnan(value):
            hovers.append("")
            continue
        parts = [f"{name}: <b>{format_value(float(value), o.value_format)}</b>"]
        if not lines.observed[s, p]:
            parts[0] += " (no rows)"
        if lines.n is not None and not math.isnan(lines.n[s, p]):
            parts.append(f"n = {int(lines.n[s, p]):,}")
        if lines.low is not None and lines.high is not None:
            low, high = lines.low[s, p], lines.high[s, p]
            if not math.isnan(low):
                parts.append(
                    f"{o.ci_level * 100:g}% CI: {format_value(low, o.value_format)} "
                    f"to {format_value(high, o.value_format)}"
                )
        parts += [f"{escape_text(h)}: {escape_text(v)}" for h, v in lines.hover[s][p]]
        hovers.append("<br>".join(parts))
    return hovers


def _simple_hovers(
    o: _Options, name: str, values: npt.NDArray[np.float64]
) -> list[str]:
    """Hover text of a derived line (rolling mean, overall): name and value."""
    return [
        ""
        if math.isnan(v)
        else f"{name}: <b>{format_value(float(v), o.value_format)}</b>"
        for v in values
    ]


def _axis_title(title: str) -> str | None:
    """Escape an axis title; ``""`` becomes ``None``, so Plotly reserves no space."""
    return escape_text(title) if title else None


def _x_axis(
    o: _Options, lines: _Lines, xs: list[object], events: list[object]
) -> dict[str, Any]:
    """Build the x axis: type, order, slider, and how the hover names a period."""
    axis: dict[str, Any] = {
        "title": {"text": _axis_title(o.x_title if o.x_title is not None else o.x)}
    }
    if lines.kind == "categorical":
        axis.update(type="category", categoryorder="array", categoryarray=xs)
    elif lines.kind == "temporal":
        axis["type"] = "date"
        if lines.grain is not None:
            axis["unifiedhovertitle"] = {"text": _PERIOD_HOVER[lines.grain]}
    elif o.log_x:
        axis.update(type="log", **_log_ticks(np.asarray(lines.xs, dtype=float)))
    else:
        axis["type"] = "linear"
    if lines.kind != "categorical" and len(xs) > 1:
        axis["range"] = _x_range(o, [*xs, *events])
    elif lines.kind == "temporal":
        # One date: Plotly's autorange is a millisecond either side, ticked in
        # fractions of a second. A day either side, with the date as its tick.
        (only,) = lines.xs
        axis.update(
            range=[only - _SINGLE_DATE_PAD, only + _SINGLE_DATE_PAD],  # type: ignore[operator]
            tickvals=[only],
            ticktext=[escape_text(text(only))],
        )
    if o.rangeslider:
        # The slider autoranges on its own, with the same 5 % padding: give it
        # the axis range, so its window starts out covering the whole slider.
        axis["rangeslider"] = {"visible": True}
        if "range" in axis:
            axis["rangeslider"]["range"] = axis["range"]
    return axis


def _x_range(o: _Options, xs: list[object]) -> list[object]:
    """Span the x positions (and events), with ``_X_MARGIN`` either side.

    Plotly pads the autorange of any trace with markers or text by 5 % of the
    span, so a monthly line over two years would end five weeks before the
    axis does, past a tick with no data. An explicit range keeps the axis on
    the data; markers and labels at the ends stay visible (``cliponaxis``).
    """
    first, last = min(xs), max(xs)  # type: ignore[type-var]
    if isinstance(first, dt.datetime) and isinstance(last, dt.datetime):
        span = (last - first) * _X_MARGIN
        return [first - span, last + span]
    low, high = float(first), float(last)  # type: ignore[arg-type]
    if o.log_x:  # a log axis takes its range in powers of ten
        low, high = math.log10(low), math.log10(high)
    pad = (high - low) * _X_MARGIN
    return [low - pad, high + pad]


def _log_ticks(values: npt.NDArray[np.float64]) -> dict[str, Any]:
    """Tick spacing of a log axis over ``values``, so its labels never crowd.

    Plotly picks it from the axis length, and labels every digit (2, 3, ...
    9) of a range spanning up to about three powers of ten. Below one power
    of ten its own ticks are fine; from one to ``_LOG_DIGIT_DECADES`` only 1,
    2 and 5 are labelled (``"D2"``), beyond that only the powers of ten.
    """
    finite = values[np.isfinite(values) & (values > 0)]
    if not finite.size:
        return {}
    decades = math.log10(float(finite.max())) - math.log10(float(finite.min()))
    if decades < 1:
        return {}
    return {"dtick": "D2" if decades <= _LOG_DIGIT_DECADES else 1}


def _y_axis(o: _Options, lines: _Lines) -> dict[str, Any]:
    """Build the value axis: title, log scale, the labels' format if d3 shares it."""
    title = o.y_title if o.y_title is not None else value_label(o.agg, o.ys)
    axis: dict[str, Any] = {"title": {"text": _axis_title(title)}}
    if o.log_y:
        drawn = [lines.values, lines.rolled, lines.overall, lines.low, lines.high]
        values = np.concatenate([d.ravel() for d in drawn if d is not None])
        axis.update(type="log", **_log_ticks(values))
    tickformat = d3_format(o.value_format)
    if tickformat is not None:
        axis["tickformat"] = tickformat
    return axis


def _auto_title(o: _Options) -> str:
    """'Total revenue over month by region'."""
    split = f" by {o.color}" if o.color is not None else ""
    return f"{value_label(o.agg, o.ys)} over {o.x}{split}"


def _auto_subtitle(o: _Options, lines: _Lines) -> str:
    """State everything the chart does to the data, in reading order."""
    parts = []
    grain = lines.grain
    if grain is not None:
        parts.append(_GRAIN_ADJECTIVE[grain])
        if lines.empty:
            periods = f"{lines.empty} empty {grain}{'s' if lines.empty > 1 else ''}"
            parts.append(
                {
                    "gap": f"{periods} left as gaps",
                    "zero": f"{periods} drawn as 0",
                    "connect": f"lines bridge {periods}",
                }[o.gap_mode]
            )
    if o.rolling is not None:
        unit = grain or "point"
        parts.append(f"{o.rolling}-{unit} rolling mean")
    if o.ci is not None:
        method = "bootstrap" if o.ci == "bootstrap" else "standard error"
        parts.append(f"band: {o.ci_level * 100:g}% confidence interval ({method})")
    if o.overall_line:
        if o.agg is not None:
            word = AGG_WORDS[o.agg].lower()
            parts.append(f"{OVERALL} = {word} of all rows")
        else:
            parts.append(f"{MEAN_OF_SERIES} = average of the lines, not of all rows")
    return " · ".join(parts)
