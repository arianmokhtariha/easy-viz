"""Type aliases shared by the whole package.

Aliases are plain assignments (not ``type`` statements) so ``typing.get_args``
works on them at runtime: validation reads the allowed values from here.
"""

from typing import Literal

from narwhals.typing import IntoFrame

# Any table narwhals accepts, eager or lazy: pandas, polars, pyarrow, ...
FrameLike = IntoFrame

Orientation = Literal["vertical", "horizontal"]

# How rows are combined per x / color / facet group. "count" needs no y column.
Agg = Literal["sum", "mean", "median", "min", "max", "count"]

# How categories are ordered: by bar value, or by the x value itself.
SortBy = Literal["value", "x"]

# Several series side by side, stacked, or stacked to 100 % per category.
BarMode = Literal["group", "stack", "percent"]

# Where value labels sit relative to their bar (Plotly's names).
TextPosition = Literal["outside", "inside", "auto"]

# How marks are coloured by their own value: a low-to-high scale, two directions
# from a midpoint, or the theme's positive/negative colours.
ValueColoring = Literal["sequential", "diverging", "sign"]

# Calendar periods a time axis is bucketed into. Weeks start on Monday, as in
# SQL's date_trunc('week', ...); quarters on Jan/Apr/Jul/Oct 1. Finest first:
# _data reads this order.
TimeGrain = Literal["hour", "day", "week", "month", "quarter", "year"]

# How a line chart draws a period of its calendar that has no row: a break in
# the line, a zero, or a line bridging it.
MissingPeriods = Literal["gap", "zero", "connect"]

# How a line runs between its points (Plotly's line.shape): straight, smoothed,
# or in steps (horizontal-vertical and its variants).
LineShape = Literal["linear", "spline", "hv", "vh", "hvh", "vhv"]

# Which points of a line get their value written on them, besides all (True)
# or none (False): the last one, the first and last, each series' max and min.
ValueLabels = Literal["last", "ends", "extremes"]
