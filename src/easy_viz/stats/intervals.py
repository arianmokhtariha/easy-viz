"""Confidence intervals of a group's mean or median.

Ported from ``_agg_ci`` of the original module, with the same behaviour: the
*basic* bootstrap (scipy's ``method="basic"``) or the normal approximation
mean ± z·SEM, and an interval only from two values up.
"""

import math
from dataclasses import dataclass
from statistics import NormalDist
from typing import Literal

import numpy as np
import numpy.typing as npt

from easy_viz._validate import message

# What a bar shows when its rows are aggregated, and how its interval is computed.
Statistic = Literal["mean", "median"]
CiMethod = Literal["bootstrap", "sem"]

# Anything np.random.default_rng accepts: a seed, a generator, or None (fresh).
RandomState = int | np.random.Generator | None

# Upper bound on resampled values held in memory at once (8 MB of float64).
# Resamples are drawn in batches below it; the random stream is the same as one
# big draw, so the result doesn't depend on the batch size.
_MAX_BATCH_VALUES = 1_000_000


@dataclass(frozen=True, slots=True)
class Interval:
    """A statistic with its confidence interval.

    ``low`` and ``high`` are NaN when no interval can be computed (fewer than
    two values); every field is NaN, and ``n`` 0, for an empty group.
    """

    estimate: float
    low: float
    high: float
    n: int


def interval(
    values: npt.ArrayLike,
    *,
    statistic: Statistic,
    method: CiMethod,
    level: float,
    n_boot: int,
    random_state: RandomState,
) -> Interval:
    """Return the ``statistic`` of ``values`` and its confidence interval.

    Parameters
    ----------
    values : array-like of float
        The group's values; NaN values are ignored.
    statistic : {"mean", "median"}
        What is estimated.
    method : {"bootstrap", "sem"}
        ``"bootstrap"``: the basic bootstrap with ``n_boot`` resamples,
        identical to ``scipy.stats.bootstrap(..., method="basic")`` given the
        same generator. ``"sem"``: mean ± z·SEM (normal approximation), mean
        only.
    level : float
        Confidence level, strictly between 0 and 1.
    n_boot : int
        Bootstrap resamples (bootstrap only).
    random_state : int, numpy Generator or None
        Seed of the resampling (bootstrap only). An int gives the same interval
        on every call, whatever else is computed around it.

    Returns
    -------
    Interval
        Edge cases: no values gives NaN everywhere and ``n=0``; one value gives
        the estimate with NaN bounds; values that are all equal give bounds
        equal to the estimate.

    Raises
    ------
    ValueError
        For ``method="sem"`` with ``statistic="median"``: the standard error
        describes a mean only.
    """
    if method == "sem" and statistic != "mean":
        raise ValueError(
            message(
                "interval",
                f"method='sem' is defined for the mean only, got {statistic=}",
                "Use method='bootstrap'",
            )
        )
    data = np.asarray(values, dtype=np.float64)
    data = data[~np.isnan(data)]
    n = len(data)
    if n == 0:
        return Interval(math.nan, math.nan, math.nan, 0)
    estimate = float(_reduce(data, statistic))
    if n < 2:
        return Interval(estimate, math.nan, math.nan, n)
    alpha = (1 - level) / 2
    if method == "sem":
        z = NormalDist().inv_cdf(1 - alpha)
        half = z * float(np.std(data, ddof=1)) / math.sqrt(n)
        return Interval(estimate, estimate - half, estimate + half, n)
    resampled = _bootstrap_distribution(data, statistic, n_boot, random_state)
    q_low, q_high = np.quantile(resampled, [alpha, 1 - alpha])
    # The basic interval reflects the percentiles around the estimate.
    return Interval(estimate, 2 * estimate - q_high, 2 * estimate - q_low, n)


def _reduce(
    data: npt.NDArray[np.float64], statistic: Statistic
) -> npt.NDArray[np.float64]:
    """Compute the statistic along the last axis (0-d for one sample)."""
    if statistic == "mean":
        return np.asarray(np.mean(data, axis=-1), dtype=np.float64)
    return np.asarray(np.median(data, axis=-1), dtype=np.float64)


def _bootstrap_distribution(
    data: npt.NDArray[np.float64],
    statistic: Statistic,
    n_boot: int,
    random_state: RandomState,
) -> npt.NDArray[np.float64]:
    """Compute the statistic of ``n_boot`` resamples, drawn as scipy does."""
    rng = np.random.default_rng(random_state)
    n = len(data)
    batch = max(1, _MAX_BATCH_VALUES // n)
    parts = []
    for start in range(0, n_boot, batch):
        size = min(batch, n_boot - start)
        indices = rng.integers(0, n, (size, n))
        parts.append(_reduce(data[indices], statistic))
    return np.concatenate(parts)
