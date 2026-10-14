# Guide: statistics layer (`src/easy_viz/stats/`)

Pure computation behind the plots: confidence intervals, regression, seriation,
distributions, classification curves.

## Rules
- **Pure functions:**
  - in: numpy arrays or narwhals frames
  - out: numpy arrays, narwhals frames or small frozen dataclasses
  - never figures, never Plotly
- **No dataframe-library-specific code** (pandas or polars methods). Use the narwhals
  API, or numpy on extracted columns (decision 0004).
- **Randomness is reproducible:**
  - any function that samples (bootstrap, subsampling) takes
    `random_state: int | np.random.Generator | None` and draws only from
    `np.random.default_rng(random_state)`
  - plot functions that use it expose the same parameter
- **Edge cases are defined, not accidental:** document and test the behaviour for
  empty input, a single value, zero variance and NaNs. Decide per function whether
  each one raises, returns empty, or skips with a warning.
- **Internal by default.** Stats functions are not exported in `easy_viz.__all__`
  unless the product manager decides to make one public.
- **Every function has a reference test** (see `tests/CLAUDE.md`).
