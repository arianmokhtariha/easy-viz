"""The only module that touches user tables: intake, checks, normalisation, agg.

A plot function turns whatever table the user passed into a validated,
normalised narwhals ``DataFrame`` with a few calls, in this order::

    frame = load(df, func, {"x": x, "y": y, "color": color, "hover": hover})
    require_numeric(frame, func, {"y": y})
    frame = parse_time(frame, func, "x", x)
    frame = drop_nulls(frame, func)
    frame, values = aggregate(frame, func, {"x": x, "color": color}, ys, agg)

A time axis adds :func:`infer_grain`, :func:`truncate_time` and
:func:`period_grid`: the calendar periods that keep it continuous.

Everything runs on the user's own backend through narwhals (decision 0004);
:func:`to_float_array` is the exit to numpy where statistics start.
"""

import datetime as dt
import difflib
import re
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from numbers import Real
from typing import Any, Literal, get_args

import narwhals as nw
import numpy as np
import numpy.typing as npt
from narwhals.exceptions import DuplicateError

from easy_viz._typing import Agg, FrameLike, TimeGrain
from easy_viz._validate import check_choice, message, setting
from easy_viz._warnings import warn

# Any: frames are generic over the user's native table type, which is only
# known at runtime (pandas, polars, pyarrow, ...). Nothing here touches it.
Frame = nw.DataFrame[Any]

# What a slot holds: one column, a list of columns (y, hover), or unused.
Columns = str | Sequence[str] | None

# How a column is drawn: on a value axis, a time axis or as categories.
ColumnKind = Literal["numeric", "temporal", "categorical"]

# Missing-column messages list at most this many available columns.
MAX_LISTED_COLUMNS = 20

# The ISO forms rule 5 recognises: a date, optionally with a time to the
# minute, second or microsecond. Offsets and other ISO forms stay strings.
_ISO_DATE = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?)?"
)

_AGG_EXPR: dict[str, Callable[[nw.Expr], nw.Expr]] = {
    "sum": nw.Expr.sum,
    "mean": nw.Expr.mean,
    "min": nw.Expr.min,
    "max": nw.Expr.max,
    "count": nw.Expr.count,
}


def _slot_columns(func: str, param: str, value: Columns) -> list[str]:
    """Return the column names a slot holds, raising for a malformed slot."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list | tuple) or not all(
        isinstance(column, str) for column in value
    ):
        raise TypeError(
            message(
                func,
                f"{setting(param, value)} is not a column name",
                "Pass a column name or a list of column names",
            )
        )
    if not value:
        raise ValueError(
            message(
                func,
                f"{setting(param, value)} names no columns",
                "Pass at least one column name",
            )
        )
    return list(value)


def _label(param: str, value: Columns, column: str) -> str:
    """Name a column as the user passed it: ``color='region'``, or within a list."""
    if isinstance(value, str):
        return setting(param, value)
    return f"{column!r} in {setting(param, value)}"


def _missing_column(
    func: str, param: str, value: Columns, column: str, available: list[str]
) -> str:
    """Message for a slot naming a column the table doesn't have."""
    fix = ""
    names = [name for name in available if isinstance(name, str)]
    match = difflib.get_close_matches(column, names, n=1)
    if match:
        fix = f"Did you mean {match[0]!r}? "
    listed = ", ".join(repr(name) for name in available[:MAX_LISTED_COLUMNS])
    more = len(available) - MAX_LISTED_COLUMNS
    if more > 0:
        listed += f" and {more} more"
    fix += f"Available columns: {listed}"
    return message(func, f"{_label(param, value, column)} is not a column of df", fix)


def _native_column_names(df: object) -> list[str]:
    """Column names of a table narwhals refused; empty if it exposes none.

    Reads pyarrow's ``column_names`` or pandas' ``columns``.
    """
    # pyarrow's column_names is a list. On pandas, df.column_names would be a
    # column of that name, so anything but a list falls through to .columns.
    names = getattr(df, "column_names", None)
    if not isinstance(names, list):
        names = getattr(df, "columns", None)
    return [str(name) for name in names] if names is not None else []


def load(df: FrameLike, func: str, slots: Mapping[str, Columns]) -> Frame:
    """Turn the user's table into a normalised narwhals frame of the used columns.

    Accepts anything narwhals accepts, eager or lazy (lazy frames are
    collected: chart data is small). Only the columns named in ``slots`` are
    kept, in slot order and without repeats; then SQL types are normalised
    (see Notes). The user's table is never modified.

    Parameters
    ----------
    df : FrameLike
        The table the user passed.
    func : str
        Public function name, for messages.
    slots : Mapping[str, Columns]
        Parameter name to what the user passed for it: a column name, a list
        of names, or ``None`` (slot unused).

    Returns
    -------
    narwhals.DataFrame
        The used columns, normalised.

    Raises
    ------
    TypeError
        If ``df`` is not a table, or a slot holds something other than column
        names.
    ValueError
        If a slot is an empty list, names a missing column (with a close
        match when there is one), or ``df`` has no rows.

    Notes
    -----
    Normalisation (conventions, query-result shapes rule 6):

    - ``Decimal`` columns (SQL ``numeric``) become ``Float64``.
    - ``Date`` columns become ``Datetime``.
    - pandas ``object`` columns are inspected: all ``decimal.Decimal`` / real
      numbers become ``Float64`` (what ``pd.read_sql`` returns for
      ``numeric``); all ``datetime.date`` / naive ``datetime`` values become
      ``Datetime`` (what drivers return for ``DATE``). Others are left as is.
    - Nullable and Arrow-backed dtypes need no cast: narwhals already reports
      them as the standard dtypes, and :func:`drop_nulls` and
      :func:`to_float_array` handle their missing values.
    """
    try:
        native = nw.from_native(df)
    except DuplicateError:
        # narwhals refuses the whole table, even if the repeated name is unused:
        # typical of SELECT * over a join.
        names = Counter(_native_column_names(df))
        repeated = ", ".join(repr(name) for name, n in names.items() if n > 1)
        raise ValueError(
            message(
                func,
                f"df has duplicate column names ({repeated or 'unknown'})",
                "Give every column a unique name in the query, e.g. "
                "SELECT a.id AS a_id",
            )
        ) from None
    except TypeError:
        raise TypeError(
            message(
                func,
                f"df is a {type(df).__name__}, not a table",
                "Pass a pandas, polars or pyarrow DataFrame, or another table "
                "narwhals supports",
            )
        ) from None
    available = native.collect_schema().names()
    used: list[str] = []
    for param, value in slots.items():
        for column in _slot_columns(func, param, value):
            if column not in available:
                raise ValueError(_missing_column(func, param, value, column, available))
            if column not in used:
                used.append(column)
    selected = native.select(used)
    frame = selected.collect() if isinstance(selected, nw.LazyFrame) else selected
    if len(frame) == 0:
        raise ValueError(
            message(func, "df has no rows", "Pass a table with at least one row")
        )
    return _normalise(frame)


def _object_target(series: nw.Series[Any]) -> nw.dtypes.DType | None:
    """Pick the dtype a pandas ``object`` column's values call for (None: keep)."""
    values = series.drop_nulls().to_list()
    if not values:
        return None
    if all(
        not isinstance(value, bool) and isinstance(value, Decimal | Real)
        for value in values
    ):
        return nw.Float64()
    # Time-zone-aware datetimes are left alone: one column may mix zones.
    if all(
        isinstance(value, dt.date)
        and (not isinstance(value, dt.datetime) or value.tzinfo is None)
        for value in values
    ):
        return nw.Datetime()
    return None


def _normalise(frame: Frame) -> Frame:
    """Cast SQL-flavoured dtypes to the standard ones (see :func:`load`)."""
    casts: list[nw.Expr] = []
    for name, dtype in frame.schema.items():
        target: nw.dtypes.DType | None = None
        if isinstance(dtype, nw.Decimal):
            target = nw.Float64()
        elif isinstance(dtype, nw.Date):
            target = nw.Datetime()
        elif isinstance(dtype, nw.Object) and frame.implementation.is_pandas_like():
            # Other backends (polars' Object) refuse these casts; such a column
            # stays as it is and fails the dtype checks with a clear message.
            target = _object_target(frame[name])
        if target is not None:
            casts.append(nw.col(name).cast(target))
    return frame.with_columns(casts) if casts else frame


def column_kind(frame: Frame, column: str) -> ColumnKind:
    """Classify a column as numeric, temporal (Date/Datetime) or categorical.

    Categorical is everything else: strings (any backend's string types),
    Categorical/Enum, Boolean and leftover ``object`` columns. Boolean counts
    as categorical, not numeric: ``True``/``False`` are labels on a chart.
    """
    dtype = frame.schema[column]
    if dtype.is_numeric():
        return "numeric"
    if isinstance(dtype, nw.Datetime | nw.Date):
        return "temporal"
    return "categorical"


def require_numeric(frame: Frame, func: str, slots: Mapping[str, Columns]) -> None:
    """Raise ``TypeError`` if a column in ``slots`` is not numeric.

    Call after :func:`load`, so decimals already count as numbers.
    """
    for param, value in slots.items():
        for column in _slot_columns(func, param, value):
            if column_kind(frame, column) != "numeric":
                dtype = type(frame.schema[column]).__name__
                raise TypeError(
                    message(
                        func,
                        f"{_label(param, value, column)} has dtype {dtype}, but "
                        f"{param} must be numeric",
                        "Pass a numeric column, or cast it in the query",
                    )
                )


def parse_time(frame: Frame, func: str, param: str, column: str | None) -> Frame:
    """Turn a string column of ISO dates into ``Datetime`` (rule 5).

    The column converts only when every non-null value is an ISO date
    (``2026-01-31``, ``2026-01-31 12:00``, ``2026-01-31T12:00:00.5``) and a
    real calendar date. If only some are, the column stays categorical and
    an ``EasyVizWarning`` says how many values are not dates: easy-viz never
    guesses which ones the user meant. Other dtypes are returned unchanged.

    Parameters
    ----------
    frame : narwhals.DataFrame
        Output of :func:`load`.
    func, param : str
        Public function and parameter names, for messages.
    column : str or None
        The column to convert; ``None`` returns ``frame`` unchanged.

    Returns
    -------
    narwhals.DataFrame
        ``frame``, with ``column`` converted when it holds ISO dates.
    """
    if column is None or not isinstance(frame.schema[column], nw.String):
        return frame
    # Parsing distinct values in Python is strict (no rolled-over dates such
    # as 2026-02-30) and identical on every backend; time columns have few
    # distinct values even when rows are many.
    parsed: dict[str, dt.datetime] = {}
    rejected: list[object] = []
    for text in frame[column].drop_nulls().unique(maintain_order=True).to_list():
        try:
            # A pandas object column is typed String from a sample of its
            # values, so a later number can still turn up here.
            if not isinstance(text, str) or not _ISO_DATE.fullmatch(text):
                raise ValueError
            parsed[text] = dt.datetime.fromisoformat(text)
        except ValueError:
            rejected.append(text)
    if not parsed:
        return frame
    if rejected:
        warn(
            message(
                func,
                f"{setting(param, column)} looks like dates, but {len(rejected)} of "
                f"its {len(parsed) + len(rejected)} distinct values are not ISO "
                f"dates (e.g. {rejected[0]!r}), so it is drawn as categories",
                "Fix or filter those values in the query to get a time axis",
            )
        )
        return frame
    return frame.with_columns(
        nw.col(column).replace_strict(parsed, return_dtype=nw.Datetime())
    )


# --- calendar periods (time_grain) -------------------------------------------

# The grains, finest first, as TimeGrain lists them.
_GRAINS: tuple[TimeGrain, ...] = get_args(TimeGrain)

# Periods are numbered in numpy: cast to a calendar unit, shift, divide by a
# size. Day 0 of numpy's calendar (1970-01-01) was a Thursday, so a shift of 3
# days makes every 7-day block start on a Monday; month 0 is January 1970, so
# blocks of 3 months start on Jan/Apr/Jul/Oct 1.
_PERIODS: dict[TimeGrain, tuple[str, int, int]] = {
    "hour": ("datetime64[h]", 1, 0),
    "day": ("datetime64[D]", 1, 0),
    "week": ("datetime64[D]", 7, 3),
    "month": ("datetime64[M]", 1, 0),
    "quarter": ("datetime64[M]", 3, 0),
    "year": ("datetime64[Y]", 1, 0),
}

# Microseconds: the finest unit Python's datetime, numpy and every backend share.
_TIME_UNIT = "datetime64[us]"


def _period_index(
    values: npt.NDArray[np.datetime64], grain: TimeGrain
) -> npt.NDArray[np.int64]:
    """Give each value its period number; consecutive periods count up by one.

    numpy's unit casts floor, also before 1970, and the integer division
    floors too, so every value lands in the period that contains it.
    """
    unit, size, shift = _PERIODS[grain]
    return (values.astype(unit).astype(np.int64) + shift) // size


def _period_start(
    index: npt.NDArray[np.int64], grain: TimeGrain
) -> npt.NDArray[np.datetime64]:
    """Turn period numbers (see :func:`_period_index`) back into period starts."""
    unit, size, shift = _PERIODS[grain]
    return (index * size - shift).astype(unit).astype(_TIME_UNIT)


def _wall_clock(frame: Frame, column: str) -> npt.NDArray[np.datetime64]:
    """Return a temporal column as naive ``datetime64[us]``, missing as NaT.

    A time-zone-aware column gives its local wall-clock times: a calendar
    period ("the day of 2026-03-29") is a period of the column's own zone,
    not of UTC.
    """
    series = frame[column]
    dtype = series.dtype
    if isinstance(dtype, nw.Datetime) and dtype.time_zone is not None:
        series = series.dt.replace_time_zone(None)
    return np.asarray(series.to_numpy(), dtype=_TIME_UNIT)


def _show_time(value: np.datetime64) -> str:
    """Show a moment in a message: a plain date at midnight, else date and time."""
    moment: dt.datetime = value.astype(_TIME_UNIT).item()
    return str(moment.date()) if moment.time() == dt.time() else str(moment)


def truncate_time(frame: Frame, column: str, grain: TimeGrain) -> Frame:
    """Floor a temporal column to the start of its calendar period.

    Periods start at midnight; weeks on Monday (as SQL's
    ``date_trunc('week', ...)``), quarters on Jan/Apr/Jul/Oct 1. Missing
    values stay missing. The same numpy code runs for every backend.

    Parameters
    ----------
    frame : narwhals.DataFrame
        A frame whose ``column`` is temporal (``Date`` or ``Datetime``).
    column : str
        The column to truncate.
    grain : TimeGrain
        The period: ``"hour"``, ``"day"``, ``"week"``, ``"month"``,
        ``"quarter"`` or ``"year"``.

    Returns
    -------
    narwhals.DataFrame
        ``frame`` with ``column`` replaced by naive ``Datetime("us")`` period
        starts. A time-zone-aware column is truncated in its own wall-clock
        time and loses its zone (see :func:`_wall_clock`).
    """
    values = _wall_clock(frame, column)
    present = ~np.isnat(values)
    floored = values.copy()
    floored[present] = _period_start(_period_index(values[present], grain), grain)
    namespace = nw.get_native_namespace(frame)
    return frame.with_columns(
        nw.new_series(column, floored, nw.Datetime("us"), backend=namespace)
    )


def infer_grain(frame: Frame, func: str, column: str) -> TimeGrain:
    """Read the calendar grain of a temporal column from its values.

    The grain is the coarsest one that every distinct value starts a period
    of (hour: whole hours; day: midnight; week: midnight on Monday; month:
    midnight on the 1st; quarter: the 1st of Jan/Apr/Jul/Oct; year: Jan 1),
    provided the two closest distinct values are exactly one period apart.
    Missing periods elsewhere don't matter: monthly data without March is
    still ``"month"``. A single distinct value gives its coarsest grain.
    Time-zone-aware values are read in their own wall-clock time.

    Parameters
    ----------
    frame : narwhals.DataFrame
        A frame whose ``column`` is temporal, with at least one non-null value.
    func : str
        Public function name, for messages.
    column : str
        The time column.

    Returns
    -------
    TimeGrain
        The grain the values sit on.

    Raises
    ------
    ValueError
        If the grain is ambiguous: a value is not on a whole hour (raw
        timestamps), or the closest values are more than one period apart
        (every other day, every two weeks). The message names ``time_grain``
        and the column, and suggests a grain to bucket into, or
        ``time_grain=None`` to draw the points as they are.
    """
    values = _wall_clock(frame, column)
    distinct = np.unique(values[~np.isnat(values)])
    aligned = [
        grain
        for grain in _GRAINS
        if np.array_equal(
            _period_start(_period_index(distinct, grain), grain), distinct
        )
    ]
    problem = f"time_grain='auto' finds no calendar grain in {column!r}"
    as_they_are = "time_grain=None to draw the points as they are"
    if not aligned:
        hours = _period_start(_period_index(distinct, "hour"), "hour")
        off = distinct[hours != distinct][0]
        raise ValueError(
            message(
                func,
                f"{problem}: {_show_time(off)} is not on a whole hour",
                f"Set time_grain to bucket the dates (e.g. time_grain='day'), or "
                f"{as_they_are}",
            )
        )
    grain = aligned[-1]
    steps = np.diff(_period_index(distinct, grain))
    if steps.size and steps.min() != 1:
        at = int(np.argmin(steps))
        position = _GRAINS.index(grain)
        fix = f"Set {as_they_are}"
        if position + 1 < len(_GRAINS):
            coarser = _GRAINS[position + 1]
            fix = (
                f"Set time_grain to bucket them (e.g. time_grain={coarser!r}), or "
                f"{as_they_are}"
            )
        raise ValueError(
            message(
                func,
                f"{problem}: its dates fall on {grain} starts, but no two are one "
                f"{grain} apart (closest: {_show_time(distinct[at])} and "
                f"{_show_time(distinct[at + 1])})",
                fix,
            )
        )
    return grain


def period_grid(
    start: dt.datetime, end: dt.datetime, grain: TimeGrain
) -> list[dt.datetime]:
    """Every period start from ``start`` to ``end``, both included.

    Calendar-correct: months, quarters and years step by the calendar, not
    by a fixed number of days. The plot draws one point per period, so
    periods without a row show as gaps (D3 of plan 0004).

    Parameters
    ----------
    start, end : datetime.datetime
        Naive period starts of ``grain`` (e.g. from :func:`truncate_time`),
        ``start <= end``.
    grain : TimeGrain
        The period.

    Returns
    -------
    list[datetime.datetime]
        The period starts, in order.

    Raises
    ------
    ValueError
        If ``start`` or ``end`` is not a period start, or ``start > end``.
    """
    bounds = np.array([start, end], dtype=_TIME_UNIT)
    first, last = _period_index(bounds, grain)
    starts = _period_start(np.arange(first, last + 1, dtype=np.int64), grain)
    if not starts.size or starts[0] != bounds[0] or starts[-1] != bounds[1]:
        raise ValueError(
            message(
                "period_grid",
                f"{start} and {end} are not {grain} starts in order",
                "Pass truncated values (truncate_time), start first",
            )
        )
    grid: list[dt.datetime] = starts.tolist()
    return grid


def _missing(frame: Frame, column: str) -> nw.Expr:
    """Flag missing values: null, or NaN in a float column.

    A SQL NULL becomes NaN in pandas float columns, while polars and pyarrow
    keep NaN distinct from null; both mean "no value" to a chart.
    """
    expr = nw.col(column).is_null()
    if frame.schema[column].is_float():
        expr = expr | nw.col(column).is_nan()
    return expr


def drop_nulls(frame: Frame, func: str) -> Frame:
    """Drop rows with a missing value in any column of ``frame``, announced.

    ``frame`` holds only the used columns (see :func:`load`), so only those
    count. Warns with the number of rows dropped, out of how many, and the
    count per column; silent when nothing is dropped.

    Raises
    ------
    ValueError
        If every row has a missing value.
    """
    masks = {column: _missing(frame, column) for column in frame.columns}
    # to_dict, not row(0): before narwhals 2.13, row() returns pyarrow scalars,
    # and a scalar holding 0 is truthy.
    counts = frame.select(
        mask.sum().alias(column) for column, mask in masks.items()
    ).to_dict(as_series=False)
    per_column = {column: int(count) for column, (count,) in counts.items() if count}
    if not per_column:
        return frame
    kept = frame.filter(~nw.any_horizontal(*masks.values(), ignore_nulls=False))
    total, dropped = len(frame), len(frame) - len(kept)
    where = ", ".join(f"{count} in {column!r}" for column, count in per_column.items())
    if len(kept) == 0:
        raise ValueError(
            message(
                func,
                f"all {total} rows have a missing value ({where})",
                "Filter or fill NULLs in the query",
            )
        )
    warn(
        message(
            func,
            f"dropped {dropped} of {total} rows with missing values ({where})",
            "Filter or fill NULLs in the query to avoid this",
        )
    )
    return kept


def aggregate(
    frame: Frame,
    func: str,
    keys: Mapping[str, str | None],
    values: Sequence[str],
    agg: Agg | None,
) -> tuple[Frame, list[str]]:
    """Check that keys are unique (``agg=None``) or aggregate ``values`` per key.

    Groups keep the order in which each key combination first appears, on
    every backend, so the query's ``ORDER BY`` controls the chart. Rows are
    never sorted here, not even by time: a plot that connects points (lines)
    sorts a temporal ``x`` itself.

    Parameters
    ----------
    frame : narwhals.DataFrame
        Output of :func:`drop_nulls`.
    func : str
        Public function name, for messages.
    keys : Mapping[str, str or None]
        Parameter name to grouping column (``x``, ``color``, facets);
        ``None`` entries are skipped. At least one must be set.
    values : Sequence[str]
        The ``y`` column(s). May be empty for ``agg="count"``.
    agg : Agg or None
        ``None`` keeps rows as-is; otherwise how each group is combined.
        ``"count"`` counts rows: per ``values`` column, or as one column
        named ``"count"`` (made unique if a key has that name) when
        ``values`` is empty.

    Returns
    -------
    tuple[narwhals.DataFrame, list[str]]
        The frame (keys and values only when aggregated; other columns such
        as hover are dropped, since a group has no single value for them)
        and the names of its value columns.

    Raises
    ------
    ValueError
        With ``agg=None``, if a key combination repeats: names ``agg``, says
        how many combinations repeat and shows the first one.
    """
    key_columns = list(dict.fromkeys(c for c in keys.values() if c is not None))
    if not key_columns:
        raise ValueError(
            message(func, "aggregate needs at least one key column", "Pass x")
        )
    if agg is not None:
        check_choice(func, "agg", agg, Agg)
    values = list(dict.fromkeys(values))
    overlap = [column for column in values if column in key_columns]
    if overlap:
        raise ValueError(
            message(
                func,
                f"{overlap[0]!r} is used both as y and to group the data",
                "Use different columns for y and for x, color or facets",
            )
        )
    order = nw.generate_temporary_column_name(8, frame.columns)
    indexed = frame.with_row_index(order)
    if agg is None:
        _check_unique(indexed, func, keys, key_columns, order)
        return frame, values

    dropped = [c for c in frame.columns if c not in key_columns and c not in values]
    if dropped:
        names = ", ".join(repr(column) for column in dropped)
        warn(
            message(
                func,
                f"{setting('agg', agg)} combines rows, so {names} has no single "
                "value per group and is not shown",
                "Remove it, or aggregate it in the query",
            )
        )
    if not values and agg != "count":
        raise ValueError(
            message(
                func,
                f"{setting('agg', agg)} needs y",
                "Set y, or use agg='count' to count rows",
            )
        )
    if values:
        outputs = list(values)
        exprs = [] if agg == "median" else [_AGG_EXPR[agg](nw.col(c)) for c in values]
    else:
        name = "count"
        while name in key_columns:
            name += "_"
        outputs, exprs = [name], [nw.len().alias(name)]
    grouped = (
        indexed.group_by(key_columns)
        .agg(*exprs, nw.col(order).min())
        .sort(order)
        .drop(order)
    )
    if agg == "median" and values:
        namespace = nw.get_native_namespace(frame)
        medians = _group_medians(indexed, key_columns, values, order)
        grouped = grouped.with_columns(
            nw.new_series(c, medians[c], nw.Float64(), backend=namespace)
            for c in values
        )
    return grouped.select(*key_columns, *outputs), outputs


def _check_unique(
    indexed: Frame,
    func: str,
    keys: Mapping[str, str | None],
    key_columns: list[str],
    order: str,
) -> None:
    """Raise if a key combination repeats while ``agg=None`` (rule 1)."""
    rows = nw.generate_temporary_column_name(8, indexed.columns)
    repeats = (
        indexed.group_by(key_columns)
        .agg(nw.len().alias(rows), nw.col(order).min())
        .filter(nw.col(rows) > 1)
        .sort(order)
    )
    if len(repeats) == 0:
        return
    named = {param: column for param, column in keys.items() if column is not None}
    # Python values (see drop_nulls), so pyarrow keys show as 'North', not scalars.
    first = repeats.head(1).to_dict(as_series=False)
    example = ", ".join(f"{column}={_show(first[column][0])}" for column in key_columns)
    params = list(named)
    what = " and ".join([", ".join(params[:-1]), params[-1]] if params[:-1] else params)
    count = len(repeats)
    kind = "value" if len(key_columns) == 1 else "combination"
    many = (
        f"{count} {kind}s of {what} appear"
        if count > 1
        else f"1 {kind} of {what} appears"
    )
    raise ValueError(
        message(
            func,
            f"{many} in more than one row (e.g. {example}), but agg=None plots "
            "each row as-is",
            "Set agg (e.g. agg='sum') to combine them, or return one row per "
            f"{what} from the query",
        )
    )


def _show(value: object) -> str:
    """Show a data value in a message: dates as plain text, the rest as repr."""
    return str(value) if isinstance(value, dt.date) else repr(value)


def _group_medians(
    indexed: Frame, key_columns: list[str], values: Sequence[str], order: str
) -> dict[str, npt.NDArray[np.float64]]:
    """Exact per-group medians, groups in first-appearance order.

    Computed in numpy because narwhals' pyarrow backend aggregates medians
    with ``approximate_median`` (a t-digest), which is wrong for small groups
    (the median of 1 and 3 comes out as 1). One code path for every backend.
    """
    _, group = _group_ids(indexed, key_columns, order)
    sizes = np.bincount(group)
    starts = np.concatenate(([0], np.cumsum(sizes)[:-1]))
    low, high = starts + (sizes - 1) // 2, starts + sizes // 2
    medians: dict[str, npt.NDArray[np.float64]] = {}
    for column in values:
        numbers = to_float_array(indexed, column)
        ranked = numbers[np.lexsort((numbers, group))]
        medians[column] = (ranked[low] + ranked[high]) / 2
    return medians


def _group_ids(
    indexed: Frame, key_columns: Sequence[str], order: str
) -> tuple[npt.NDArray[np.int64], npt.NDArray[np.intp]]:
    """Give each row its group's number, in the order groups first appear.

    Returns the first row index of every group (ascending) and, per row, the
    position of its group in that list. ``order`` is a row-index column.
    """
    first_row = indexed.select(nw.col(order).min().over(*key_columns))[order]
    # first_row sorts in first-appearance order, so group ids follow it too.
    firsts, group = np.unique(first_row.to_numpy(), return_inverse=True)
    return firsts.astype(np.int64), group.astype(np.intp)


def group_arrays(
    frame: Frame, key_columns: Sequence[str], column: str
) -> dict[tuple[object, ...], npt.NDArray[np.float64]]:
    """Split a numeric column into one float array per key combination.

    The raw values behind each bar, for statistics that need more than an
    aggregate (confidence intervals). Keys are tuples of Python values in
    ``key_columns`` order, as ``to_dict`` returns them; the dict keeps the
    order in which groups first appear.
    """
    order = nw.generate_temporary_column_name(8, frame.columns)
    firsts, group = _group_ids(frame.with_row_index(order), key_columns, order)
    keys = frame.select(*key_columns).to_dict(as_series=False)
    numbers = to_float_array(frame, column)
    # One stable sort, then contiguous slices: every group's rows keep their order.
    ranked = numbers[np.argsort(group, kind="stable")]
    bounds = np.cumsum(np.bincount(group, minlength=len(firsts)))[:-1]
    return {
        tuple(keys[name][first] for name in key_columns): values
        for first, values in zip(firsts, np.split(ranked, bounds), strict=True)
    }


def to_float_array(frame: Frame, column: str) -> npt.NDArray[np.float64]:
    """Return a numeric column as a float64 numpy array, missing values as NaN.

    This is where narwhals stops and statistics start (decision 0004).
    """
    series = frame[column].cast(nw.Float64())
    return np.asarray(series.to_numpy(), dtype=np.float64)
