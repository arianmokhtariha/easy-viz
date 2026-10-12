# 0004: Dataframe-agnostic internals through narwhals

**Status:** accepted · **Date:** 2026-10-11

## Context
Query results arrive as pandas, polars, pyarrow or other tables. The "no reshaping in
between" promise means easy-viz must accept them all directly. We considered moving
from pandas to polars for speed.

## Decision
Internals use the narwhals API (Polars-style syntax). It runs natively on whatever
table the user passes. Neither pandas nor polars is a runtime dependency. Where
narwhals stops, only the needed columns are converted to numpy, which statistics need
anyway.

## Alternatives
- **pandas internally:**
  - forces pandas on polars users
  - adds a conversion on every call
- **polars internally:**
  - forces polars on pandas users (most analysts)
  - adds a conversion on every call
  - speed gains are negligible, because chart data is usually small (aggregated query
    results); rendering is the bottleneck, not table operations

## Consequences
- **Easier:**
  - polars users get polars speed and pandas users get pandas, with no conversion
  - narwhals is already a Plotly dependency, so it costs nothing to install
  - narwhals' stable API shields us from pandas 3 and polars 2 breaking changes
- **Harder:**
  - narwhals covers a subset of operations, so gaps go through numpy
  - every function is tested on pandas, polars and pyarrow input
