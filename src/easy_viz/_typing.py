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
