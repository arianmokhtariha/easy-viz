"""Smoothing of a series: the trailing rolling mean drawn over a noisy line.

The semantics are pandas' ``Series.rolling(window, min_periods=1).mean()``, so
an analyst gets the number they would compute in a notebook, without easy-viz
depending on pandas.
"""

import numpy as np
import numpy.typing as npt

from easy_viz._validate import check_positive_int


def rolling_mean(
    values: npt.NDArray[np.float64], window: int
) -> npt.NDArray[np.float64]:
    """Return the trailing mean over the last ``window`` positions at each point.

    Equal to pandas' ``Series(values).rolling(window, min_periods=1).mean()``:
    the window counts positions, not values, and missing values inside it are
    skipped. A caller that wants a window in calendar time (7 days, not 7 rows)
    passes the series on its full calendar grid, with NaN for empty periods.

    Parameters
    ----------
    values : 1-D array of float
        The series in drawing order. NaN marks a missing value. Infinities are
        treated as missing too, as pandas does: no mean can be drawn from them.
    window : int
        Number of positions in the window, the current one included; 1 or
        more. ``1`` returns the values unchanged (infinities as NaN).

    Returns
    -------
    1-D array of float
        Same length as ``values``. Position ``i`` is the mean of the finite
        values among positions ``max(0, i - window + 1)`` to ``i``; NaN when
        there are none. Edge cases: an empty array gives an empty array; a
        window longer than the series gives the expanding mean.

    Raises
    ------
    ValueError
        If ``window`` is not a whole number of 1 or more.
    """
    check_positive_int("rolling_mean", "window", window)
    data = np.asarray(values, dtype=np.float64)
    finite = np.isfinite(data)
    # Running sums with a leading 0, so the sum over positions (start, end] is
    # cumsum[end] - cumsum[start]. Missing values add 0 to the sum and the count.
    sums = np.concatenate(([0.0], np.cumsum(np.where(finite, data, 0.0))))
    counts = np.concatenate(([0], np.cumsum(finite)))
    end = np.arange(1, len(data) + 1)
    start = np.maximum(end - window, 0)
    window_sum = sums[end] - sums[start]
    window_count = counts[end] - counts[start]
    means: npt.NDArray[np.float64] = np.full(len(data), np.nan)
    np.divide(window_sum, window_count, out=means, where=window_count > 0)
    return means
