# Statistics (`stats/`)

Covers: src/easy_viz/stats/__init__.py, src/easy_viz/stats/intervals.py

## Responsibilities
The numbers behind the plots, kept apart from drawing: a plot function validates,
prepares its data, then asks `stats/` for anything statistical. Pure functions only
(numpy in, numpy or small frozen dataclasses out), never Plotly, so the statistics
can be tested against scipy and reused by any plot ([the stats guide](../../../../src/easy_viz/stats/CLAUDE.md)).
Nothing here is public.

## How it works
**`intervals.py`: confidence interval of a group's mean or median**, ported from the
legacy `_agg_ci` with the same behaviour. Used by `bar_plot`'s error bars.
- `interval(values, *, statistic, method, level, n_boot, random_state) -> Interval`
  (`estimate`, `low`, `high`, `n`).
- `method="bootstrap"`: the *basic* bootstrap, `2 * estimate - quantile`, from
  `n_boot` resamples. Resample indices are drawn as scipy draws them
  (`rng.integers(0, n, (n_boot, n))` from `np.random.default_rng(random_state)`), so
  the result equals `scipy.stats.bootstrap(..., method="basic")` given the same
  generator; the test demands that exactly.
- `method="sem"`: mean ± z·SEM, with z from the standard library's `NormalDist`
  (no scipy import at all).
- Edge cases: NaN values are ignored; no values gives NaN everywhere and `n=0`; one
  value gives the estimate with NaN bounds (the legacy rule: an interval needs two
  values); identical values give a zero-width interval. `sem` with the median raises.

## Invariants
- No module imports `plotly` or `easy_viz.plots` (tested by `tests/test_layering.py`).
- Randomness comes only from `np.random.default_rng(random_state)`. An int seed makes
  each call independent of every other call, so adding a bar never moves another
  bar's interval.
- Every function is tested against a reference (scipy) plus its documented edge
  cases (`tests/stats/`).

## Pitfalls
- **Resamples are drawn in batches** below `_MAX_BATCH_VALUES` (one million floats),
  so a group of 10,000 rows doesn't need 160 MB at once. Consecutive draws from a
  numpy `Generator` give the same stream as one big draw, which is why batching keeps
  the scipy match; the reference test uses a group large enough to batch.
- **scipy renamed `random_state` to `rng` in 1.15**; the lowest supported scipy is
  1.14. `stats/` doesn't call scipy, so only the reference test has to pick the
  keyword (it inspects the signature).
- **The bootstrap of 2 or 3 values is itself unreliable**: its interval comes out
  narrow because few distinct resamples exist. That's why `bar_plot` flags small
  groups (`min_n`) as well as drawing intervals.
