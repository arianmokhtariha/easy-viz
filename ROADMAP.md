# Roadmap

Where easy-viz stands. Updated in the PR that changes it.

## Now
- Nothing in progress.

## Next
- Release 0.1.0 (`bar_plot` and `line_plot`).

## Later
- Small multiples (`facet_col`, `facet_row`) for every plot function, in one plan
  (decided with plan 0003)
- A second y axis for measures on different scales (orders and conversion rate
  on one chart); the product manager will shape it (2026-10-16)
- Found while porting `line_plot`:
  - stacked areas, indexing series to 100 for growth comparisons, shaded periods
    (a range of x, such as a campaign), and the low-n flag (`min_n`) on points
  - linear trendlines with r² and p belong with the relationship plots
  - value labels that never cross another line: today a label moves away from
    nearby points but can still sit on another line's segment, and three lines
    within one label height can't all be separated
  - reference, event and overall lines are drawn above the data (overlay-axis
    traces, shared with `bar_plot`); drawing them underneath needs a technique
    that keeps their trace roles
  - the range slider repeats value labels (no Plotly option to leave them out)
  - a repeated-x message after bucketing shows the date with its midnight time
    (`2024-01-01 00:00:00`)
- Theme sample sheet: the series panel's legend sits beside the highlight panel,
  and the polar panel's radial ticks sit on its fills
- Found while porting `bar_plot`:
  - `highlight` for several series and on a time axis (today one series, no dates)
  - reference-line labels that avoid value labels at the same height
  - visual polish found in review: error-bar whiskers that cross labels at the
    bar's base, a small gap between tick labels and horizontal bars, outside
    labels near the plot's right edge, and fewer decimals on axis ticks than on
    labels (`value_format=",.2f"` writes "120.00" on the axis)
  - a bar corner radius in the theme, as the original report charts used
  - a more accurate automatic value format (`_layout.format_value`, decision 0011):
    no scientific notation for very small values, a sensible result beyond
    trillions, one unit per chart instead of per label (no "950" next to "1.2k"),
    full precision in the hover, and possibly using the column's
    meaning (rates as percentages)
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

## Done
- Automated releases ([decision 0013](docs/decisions/0013-automated-releases.md)):
  a final version merged to `main` is built and checked in CI, published to PyPI
  through trusted publishing and given a GitHub release whose text is its
  changelog entry; the changelog's format is checked on every pull request
- `line_plot` (plan 0004): one line function for every query shape, merging the
  original `line_plot` and `time_series_plot`
  ([decision 0012](docs/decisions/0012-one-line-plot-continuous-time.md)); a time
  axis that is always continuous, with the calendar grain read from the data and
  empty periods shown; rolling means over calendar periods, confidence bands, an
  overall line that uses every row; line width and marker size in the theme; its
  gallery notebook, with the price-rise story as the first README image
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
