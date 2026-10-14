"""Type aliases shared by the whole package.

Aliases are plain assignments (not ``type`` statements) so ``typing.get_args``
works on them at runtime: validation reads the allowed values from here.
"""

from collections.abc import Sequence
from typing import Literal

import numpy as np
import numpy.typing as npt
from narwhals.typing import IntoFrame, IntoSeries

# Any table narwhals accepts, eager or lazy: pandas, polars, pyarrow, ...
FrameLike = IntoFrame

# 1-D numeric input of the model-diagnostic plots (true labels, scores, ...).
ArrayLike = Sequence[float] | npt.NDArray[np.number] | IntoSeries

Orientation = Literal["vertical", "horizontal"]

# How rows are combined per x / color / facet group. "count" needs no y column.
Agg = Literal["sum", "mean", "median", "min", "max", "count"]
