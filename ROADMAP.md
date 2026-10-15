# Roadmap

Where easy-viz stands. Updated in the PR that changes it.

## Now
- Nothing in progress.

## Next
- Plan 0003: port `line_plot` and `bar_plot` with their gallery notebooks, then
  release 0.1.0. The first of these notebooks also proves the gallery template on a
  real plot function.

## Later
- Port the remaining functions by family: distribution, relationship, comparison,
  timeseries, business, ml. One function at a time, each port also a redesign
  against the product principles: overlapping functions merge into one where
  nothing is lost (e.g. `time_series_plot` into `line_plot`, `grouped_bar_plot`
  into `bar_plot`, if their ports confirm it); the improvements and features found
  along the way are built or listed here; and the showcase data grows the patterns
  that function's options reveal
- Report features: waterfall, cohort heatmap, `highlight`, `color_map`, takeaway titles
- Docs site rendering the gallery notebooks
- README showcase built from gallery images
- Automated releases: a version bump merged to `main` builds in CI, creates the
  GitHub release and publishes to PyPI through trusted publishing

## Done
- Showcase dataset and gallery (plan 0002): Fernway, a fictional retailer in seven
  related tables with ten planted patterns and a tested answer key; the notebook
  template and a "Meet the data" notebook, with every chart starting from a SQL query
  (DuckDB); a build script that executes the notebooks, stores every figure as a
  static image and as an interactive figure, and exports README images; checks that
  every plot function, parameter and README image stays covered. The product
  manager approved the dataset and its answer key as the starting set (2026-10-15).
  With their approval, proving the template on a real plot function
  moved to plan 0003, and rendering the notebooks on a docs site stays with the
  "Docs site" item; the notebook outputs are already docs-ready
- Foundation (plan 0001): table intake for pandas, polars and pyarrow with SQL type
  normalisation, option validation, layout helpers, the `dark` and `light` themes,
  trace roles, global config and static export, plus repository-wide checks for
  layering, styling literals, the plot contract and the knowledge base
- CI: lint, formatting, type checks and tests on Python 3.13–3.15 for every pull
  request and every push to `main`, plus a test run on the lowest dependency versions
  `pyproject.toml` allows
