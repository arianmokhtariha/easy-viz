import math

import numpy as np
import numpy.typing as npt
import pandas as pd
import pytest

from easy_viz.stats.smoothing import rolling_mean

nan = math.nan


def pandas_rolling_mean(values: list[float], window: int) -> npt.NDArray[np.float64]:
    """The reference: pandas' trailing mean with min_periods=1."""
    series = pd.Series(values, dtype="float64")
    return series.rolling(window, min_periods=1).mean().to_numpy(dtype=np.float64)


@pytest.mark.parametrize(
    ("values", "window"),
    [
        # Gaps inside the window: the mean is over the values present, and the
        # window still counts the gap's positions.
        ([1.0, nan, 3.0, nan, nan, 6.0, 2.0, nan, 8.0], 3),
        # A run of NaNs longer than the window: NaN once the window is all gap,
        # then the first value after it stands alone.
        ([4.0, 5.0, nan, nan, nan, nan, 7.0, 9.0], 2),
        # Leading NaNs: nothing to average yet.
        ([nan, nan, 2.0, 4.0], 3),
        ([3.0, nan, 5.0], 1),
        # A window longer than the series is the expanding mean.
        ([2.0, 4.0, nan, 9.0], 10),
        ([7.5], 4),
        ([0.25] * 6, 3),
    ],
    ids=[
        "gaps in window",
        "gap longer than window",
        "leading NaNs",
        "window 1",
        "window longer than series",
        "one value",
        "zero variance",
    ],
)
def test_matches_pandas(values: list[float], window: int) -> None:
    result = rolling_mean(np.array(values), window)
    expected = pandas_rolling_mean(values, window)
    np.testing.assert_allclose(result, expected, rtol=1e-12, equal_nan=True)


def test_matches_pandas_on_a_long_noisy_series_with_gaps() -> None:
    # Cumulative sums drift on long series; pandas uses compensated sums.
    rng = np.random.default_rng(5)
    values = rng.lognormal(6, 1.2, 2000)
    values[rng.random(2000) < 0.15] = nan
    values[700:740] = nan
    for window in (7, 28, 365):
        expected = pandas_rolling_mean(values.tolist(), window)
        np.testing.assert_allclose(
            rolling_mean(values, window), expected, rtol=1e-9, equal_nan=True
        )


def test_infinities_count_as_missing() -> None:
    # Hand-computed: pandas 3 does the same, older pandas returns inf or NaN.
    values = np.array([math.inf, 1.0, 2.0, -math.inf, 4.0])
    expected = [nan, 1.0, 1.5, 2.0, 4.0]
    np.testing.assert_allclose(rolling_mean(values, 2), expected, equal_nan=True)


def test_empty_series_gives_an_empty_result() -> None:
    result = rolling_mean(np.array([], dtype=np.float64), 3)
    assert result.shape == (0,)
    assert result.dtype == np.float64


def test_input_is_left_unchanged() -> None:
    values = np.array([1.0, nan, 3.0])
    rolling_mean(values, 2)
    np.testing.assert_array_equal(values, [1.0, nan, 3.0])


@pytest.mark.parametrize("window", [0, -2, 2.5, True])
def test_window_must_be_a_whole_number_of_one_or_more(window: object) -> None:
    with pytest.raises(ValueError, match=r"^rolling_mean: window=.* is not valid"):
        rolling_mean(np.array([1.0, 2.0]), window)  # type: ignore[arg-type]
