"""Type aliases shared by the whole package.

Aliases of allowed values are plain assignments (not ``type`` statements) so
``typing.get_args`` works on them at runtime: validation reads the allowed values
from here. ``ArrayLike`` is the exception, see its comment.
"""

from collections.abc import Sequence
from typing import Literal

import numpy as np
import numpy.typing as npt
from narwhals.typing import IntoFrame, IntoSeries

# Any table narwhals accepts, eager or lazy: pandas, polars, pyarrow, ...
FrameLike = IntoFrame

# 1-D numeric input of the model-diagnostic plots (true labels, scores, ...).
# A `type` statement is evaluated only when read, never at import: narwhals 2.0
# defines IntoSeries as a string, and with numpy 2.1 a `|` union that includes a
# string raises TypeError, so a plain assignment broke `import easy_viz`.
type ArrayLike = Sequence[float] | npt.NDArray[np.number] | IntoSeries

Orientation = Literal["vertical", "horizontal"]

# How rows are combined per x / color / facet group. "count" needs no y column.
Agg = Literal["sum", "mean", "median", "min", "max", "count"]
