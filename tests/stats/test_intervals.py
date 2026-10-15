import inspect
import math

import numpy as np
import pytest
from scipy import stats

from easy_viz.stats.intervals import Statistic, interval

LEVEL = 0.95
N_BOOT = 2000


def scipy_basic_bootstrap(
    values: np.ndarray, statistic: Statistic, seed: int
) -> tuple[float, float]:
    """scipy's basic bootstrap with the generator easy-viz would build from seed."""
    function = np.mean if statistic == "mean" else np.median
    # scipy 1.15 renamed random_state to rng; the lowest supported scipy is 1.14.
    params = inspect.signature(stats.bootstrap).parameters
    key = "rng" if "rng" in params else "random_state"
    result = stats.bootstrap(
        (values,),
        function,
        confidence_level=LEVEL,
        n_resamples=N_BOOT,
        method="basic",
        **{key: np.random.default_rng(seed)},
    )
    return result.confidence_interval.low, result.confidence_interval.high


# 1,500 values make the resampling run in batches (memory bound), which must not
# change the random stream: scipy draws every resample in one call.
@pytest.mark.parametrize("n", [40, 1500])
@pytest.mark.parametrize("statistic", ["mean", "median"])
def test_bootstrap_matches_scipy_exactly(n: int, statistic: Statistic) -> None:
    values = np.random.default_rng(7).lognormal(3, 0.8, n)
    result = interval(
        values,
        statistic=statistic,
        method="bootstrap",
        level=LEVEL,
        n_boot=N_BOOT,
        random_state=11,
    )
    low, high = scipy_basic_bootstrap(values, statistic, seed=11)
    assert result.low == pytest.approx(low, rel=1e-12)
    assert result.high == pytest.approx(high, rel=1e-12)
    expected = np.mean(values) if statistic == "mean" else np.median(values)
    assert result.estimate == pytest.approx(expected)
    assert result.n == n


def test_sem_matches_the_normal_interval() -> None:
    values = np.random.default_rng(3).normal(50, 12, 80)
    result = interval(
        values,
        statistic="mean",
        method="sem",
        level=0.9,
        n_boot=N_BOOT,
        random_state=None,
    )
    low, high = stats.norm.interval(0.9, loc=values.mean(), scale=stats.sem(values))
    assert (result.low, result.high) == pytest.approx((low, high))


def test_an_int_seed_gives_the_same_interval_every_call() -> None:
    values = np.arange(30.0) ** 1.5
    first, second = (
        interval(
            values,
            statistic="median",
            method="bootstrap",
            level=LEVEL,
            n_boot=500,
            random_state=0,
        )
        for _ in range(2)
    )
    assert first == second


@pytest.mark.parametrize(
    ("values", "estimate", "n"),
    [
        ([], math.nan, 0),
        ([4.0], 4.0, 1),
        ([math.nan, 4.0, math.nan], 4.0, 1),
    ],
    ids=["empty", "one value", "NaN ignored"],
)
@pytest.mark.parametrize("method", ["bootstrap", "sem"])
def test_fewer_than_two_values_give_no_interval(
    values: list[float], estimate: float, n: int, method: str
) -> None:
    result = interval(
        values,
        statistic="mean",
        method=method,  # type: ignore[arg-type]
        level=LEVEL,
        n_boot=N_BOOT,
        random_state=0,
    )
    assert result.n == n
    assert result.estimate == pytest.approx(estimate, nan_ok=True)
    assert math.isnan(result.low) and math.isnan(result.high)


@pytest.mark.parametrize("method", ["bootstrap", "sem"])
def test_zero_variance_gives_a_zero_width_interval(method: str) -> None:
    result = interval(
        [2.5] * 10,
        statistic="mean",
        method=method,  # type: ignore[arg-type]
        level=LEVEL,
        n_boot=N_BOOT,
        random_state=0,
    )
    assert (result.estimate, result.low, result.high) == (2.5, 2.5, 2.5)


def test_sem_of_a_median_raises() -> None:
    with pytest.raises(ValueError, match="mean only"):
        interval(
            [1.0, 2.0],
            statistic="median",
            method="sem",
            level=LEVEL,
            n_boot=N_BOOT,
            random_state=0,
        )
