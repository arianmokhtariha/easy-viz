# Roadmap

Where easy-viz stands. Updated in the PR that changes it.

## Now
- Nothing in progress.

## Next
- Port `line_plot` with its gallery notebook (its own plan), then release 0.1.0.

## Later
- Small multiples (`facet_col`, `facet_row`) for every plot function, in one plan
  (decided with plan 0003)
- Found while porting `bar_plot`:
  - `highlight` for several series and on a time axis (today one series, no dates)
  - reference-line labels that avoid value labels at the same height
  - a bar corner radius in the theme, as the original report charts used
- Port the remaining functions by family: distribution, relationship, comparison,
  timeseries, business, ml. One function at a time, each port also a redesign
  against the product principles: overlapping functions merge into one where
  nothing is lost; the improvements and features found along the way are built or
  listed here; and the showcase data grows the patterns that function's options
  reveal
- Report features: waterfall, cohort heatmap, takeaway titles; `highlight` and
  `color_map` in every function where they fit (built in `bar_plot`)
- Docs site rendering the gallery notebooks
- README showcase built from gallery images
- Automated releases: a version bump merged to `main` builds in CI, creates the
  GitHub release and publishes to PyPI through trusted publishing

## Done
- `bar_plot` (plan 0003): the first plot function, merging the original
  `bar_plot` and `grouped_bar_plot`
  ([decision 0010](docs/decisions/0010-one-bar-plot.md)); the first statistics
  module (bootstrap and standard-error intervals, matching scipy exactly); automatic
  value formatting ([decision 0011](docs/decisions/0011-automatic-value-format.md));
  its gallery notebook, the first on a real plot function, with a new pattern in the
  answer key (small groups at the top of a ranking)
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
