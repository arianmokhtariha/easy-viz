# 0009: The gallery queries its data with SQL through DuckDB

**Status:** accepted · **Date:** 2026-10-15

## Context
The first product principle is "SQL result in, chart out". The gallery
([decision 0006](0006-notebook-gallery.md)) is where that promise is shown, so its
examples should start where an analyst starts: a SQL query whose result goes straight
into an easy-viz call, with no reshaping in between.

The showcase dataset is a set of CSV files in `gallery/data/`. The notebooks need an
engine that runs real SQL on them. In 2026-10 DuckDB, the natural choice, had no
wheel (ready-built package) for Python 3.15, released days earlier. Installing it on
3.15 means compiling it from C++ source, which is far too slow for local development
and CI.

## Decision
- **Gallery notebooks query the showcase data with DuckDB.** A shared setup cell
  registers each CSV as a view named after its table, so queries read like warehouse
  SQL (`FROM orders JOIN customers USING (customer_id)`). Results are passed on as
  polars, pandas or Arrow tables, varied across notebooks.
- **DuckDB is a dev dependency only**, limited to Python < 3.15 by an environment
  marker. Users of easy-viz never install it.
- **The gallery builds and runs on Python 3.14** until DuckDB publishes a 3.15 wheel:
  - locally through an isolated environment
    (`uv run --isolated --python 3.14 python scripts/build_gallery.py`), which leaves
    the project's 3.15 environment untouched
  - in CI, the notebook execution step is skipped on 3.15

  The library itself is still tested on 3.13, 3.14 and 3.15
  ([decision 0005](0005-python-version-policy.md)); only the gallery, which never
  ships, uses the older Python.

## Alternatives
- **SQLite (built into Python):** works everywhere with no dependency, but the
  notebooks would first load each CSV into a database, and its dialect lacks common
  analyst functions such as `date_trunc`.
- **polars SQL:** no new dependency, but a limited dialect (no `date_trunc`, partial
  function coverage) that few analysts know.
- **pandas or polars code instead of SQL:** hides the SQL-first story the product is
  built around.
- **Compiling DuckDB on 3.15:** keeps one Python everywhere, at the cost of very long
  installs locally and in every CI run.

## Consequences
- **Easier:**
  - every example shows a real query result going straight into a plot
  - DuckDB reads the CSVs directly, so the notebooks need no loading code beyond the
    setup cell
- **Harder:**
  - while the exception lasts, gallery notebooks are not executed on Python 3.15 in CI
  - the gallery build needs a different command from the rest of the project
- **When DuckDB ships a 3.15 wheel:** drop the environment marker, the CI skip and the
  `--isolated --python 3.14` part of the command in one PR, and mark this record as
  superseded by a short one that records the change.
