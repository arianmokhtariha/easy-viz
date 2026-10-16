# 0004: `line_plot`

**Status:** approved

Approved by the product manager on 2026-10-16: D1 to D10 as recommended, with D3
(a time axis is always continuous) added at their request and D8 confirmed as
option 1 (with raw rows the overall line uses every row; with pre-aggregated rows
it is the mean of the series, labelled so). The second y axis stays on the
roadmap.

## Goal
easy-viz gets its line chart: how a measure moves along an ordered axis, usually
time. A query result goes in as it comes out of SQL, whether one row per period,
raw rows to bucket into days, weeks or months, series stacked in one column, or
several measure columns. Out comes a finished chart that can show trends,
breaks and seasonality without extra code.

It is the second plot function, and the last one before release 0.1.0.

## What the legacy module had
Two functions draw lines (`legacy/custom_plots.py`):
- **`line_plot`**: draws the rows it gets, without aggregating. It has groups,
  markers, line shape, area fill, a rolling mean, an average line in two modes, a
  per-x "group average" line, min/max labels and log axes.
- **`time_series_plot`**: buckets raw rows into a calendar frequency (`freq="MS"`),
  aggregates them (`mean`, `median`, `sum`, `count`), leaves empty periods as gaps,
  and has a rolling mean, a cap on the number of groups and a range slider.

Both draw the same chart: one line per series over an ordered axis. The second one
only adds the step that turns raw rows into one value per period. The report
notebook (`legacy/conclusions.ipynb`) adds what neither function could do: labels
on the first and last point only, and series colours fixed across charts.

## Scope
1. **One function, `line_plot`**, in a new `timeseries` family module
   (`src/easy_viz/plots/timeseries.py`), absorbing `time_series_plot` (D1).
2. **The options**, following the glossary. A ✱ marks an option that is new or
   changed against the legacy functions; the D-numbers point to the decisions
   below.

   | Group | Options |
   |---|---|
   | Slots | `x`, `y` (one column or a list), `color`, `hover` |
   | Data and aggregation | `agg`, `time_grain` ✱ (D2), `missing_periods` ✱ (D3) |
   | Statistics | `ci`, `ci_level`, `n_boot`, `random_state` ✱ (D7), `rolling` |
   | Lines and markers | `show_markers` ✱ (auto by default, D6), `line_shape`, `fill_area` |
   | Labels | `show_values` ✱ (D4), `value_format` |
   | Colour | `highlight` ✱, `color_map` ✱ (D7) |
   | Reference lines | `avg_line`, `target` ✱, `events` ✱ (D7), `overall_line` (D8) |
   | Axes and layout | `log_x`, `log_y`, `rangeslider`, `x_title` ✱, `y_title` ✱ |
   | Figure | `title`, `subtitle` ✱, `width`, `height`, `theme` |

   About 33 options, within the 20–40 of
   [decision 0002](../decisions/0002-parameter-rich-api.md).
3. **Statistics in `stats/`:** the rolling mean, in a new module, tested against
   pandas. Confidence bands reuse `stats.intervals`, unchanged.
4. **Time bucketing in `_data`**, the only module that touches user tables: truncate
   a time column to a grain, and list the full run of periods between the first and
   the last, so empty ones can be shown.
5. **Theme:** two new fields, `line_width` and `marker_size`, if D5 is approved, set
   in both built-in themes and shown on the theme sample sheets.
6. **Gallery notebook** `gallery/timeseries/line_plot.ipynb`, every option with a
   story from the showcase data:
   - pattern 4, the main story: noisy daily orders, then a 7-day rolling mean
     (weekly cycle gone), then 28 days with an event line at 2025-04-01 (the price
     rise) showing orders and conversion step down while order value steps up
   - empty periods: Gifts has orders in 95 of the 105 weeks, so a weekly
     `GROUP BY` returns no row for 10 weeks, and a plain line bridges them as if
     sales went on. `time_grain="week"` shows the gaps
   - `highlight` on monthly revenue per category, confidence bands on the mean
     order value per month, warehouses with `overall_line`
   - any of these that needs measured numbers gets rows in the `INSIGHTS.md`
     answer key; no new planted pattern is expected
7. **Knowledge:** a new architecture doc `plots/timeseries.md`, a decision record for
   the merge, the glossary entries for the new option names, and the changelog and
   roadmap.

**Not in scope** (to `ROADMAP.md`): facets (one plan for every function, as decided
with plan 0003), a second y axis, stacked areas, indexing series to 100 for growth
comparisons, linear trendlines with r² (they belong with the relationship plots),
shaded periods (`add_vrect`), the low-n flag (`min_n`) on points.

## Decisions
Each one was proposed with a recommendation and approved (see Status).

- **D1. Merge `time_series_plot` into `line_plot`, losing no option.**
  *Recommended.* Bucketing becomes `time_grain`, aggregating is the `agg` every
  function already has, `group_col` becomes `color`, `top_n_groups` is replaced
  by D9. Two functions would leave users guessing which one aggregates (product
  principle 8), the same split that [decision 0010](../decisions/0010-one-bar-plot.md)
  removed from the bar charts.
- **D2. The bucketing option is `time_grain`**, with
  `"hour" | "day" | "week" | "month" | "quarter" | "year"`; weeks start on Monday,
  as in SQL's `date_trunc('week', ...)`. *Recommended* over the legacy `freq`,
  which takes pandas codes (`"MS"`, `"QS"`) that analysts must look up. It works
  on raw rows (with `agg`) and on rows the query already bucketed.
- **D3. A time axis is always continuous** (product manager's requirement,
  2026-10-16): every period between the first and the last is on the chart, even
  when the data has no row for it. A SQL `GROUP BY` returns no row for an empty
  period, and a line silently bridges it, the most common way a line chart
  misleads.
  - `time_grain="auto"` is the default for a time `x`: the grain is read from the
    data. It is the calendar grain every date sits on (midnight, Monday, first of
    the month, ...) whose step is the smallest gap between dates. Daily data is
    `"day"`, the output of `date_trunc('month', ...)` is `"month"`.
  - When the dates sit on no regular grid (timestamps at random times, or every
    other day), the grain is ambiguous: it raises and names `time_grain`
    (product principle 2). `time_grain=None` is the explicit way out: draw the
    points as they are, with no calendar.
  - Empty periods follow `missing_periods`: `"gap"` (default; a break in the
    line), `"zero"` (right for counts and sums: no orders is zero orders) or
    `"connect"` (bridge it, the legacy `connect_gaps=True`).
  - When empty periods are found and `missing_periods` was left at its default,
    a warning says how many and how they are drawn.
  - The rolling mean runs over this full grid, so `rolling=7` on daily data is
    always 7 days, never 7 rows that skip a missing day.
- **D4. `show_values` also takes `"last"`, `"ends"` or `"extremes"`** besides
  `True`/`False` (every point). Default `False`. This replaces
  `annotate_extremes` and adds the report notebook's first-and-last labels.
  *Recommended:* one option for "which values are written", and `True` means the
  same as in `bar_plot`. The alternative is three separate booleans that can
  contradict each other.
- **D5. Drop `line_width`, `marker_size` and `opacity` as parameters;** line
  width and marker size become `Theme` fields. *Recommended:* they are styling, no
  other function has size options, and one size across all charts is what a theme
  is for. One chart's size is one line on the returned figure
  (`fig.update_traces(line_width=4)`). Against it: decision 0002 says not to
  remove options, though moving them to the theme keeps them available.
- **D6. Ordering:** a numeric or time `x` is always drawn sorted; a text `x` keeps
  the query's order (`ORDER BY`), as every function does. `sort_x` is dropped.
  `show_markers=None` (the new default) shows markers when a series has 30 points
  or fewer, the report notebook's rule. *Recommended:* the legacy `sort_x=True`
  sorted text alphabetically, which scrambles `Mon, Tue, ...` or funnel steps.
  Unsorted numbers draw a zigzag nobody wants.
- **D7. New options, built in this plan:**
  - `ci` (`"bootstrap"`, `"sem"`) with `agg="mean"` or `"median"`: a shaded
    confidence band, from the same statistics as `bar_plot` (product principle 5)
  - `highlight` (one or several series stand out, the rest dimmed; this also
    makes charts with many series readable) and `color_map`
  - `target`: a dotted line at a target value, as in `bar_plot`
  - `events`: labelled vertical lines at given x values, e.g.
    `events={"2025-04-01": "Price +12 %"}`, the tool of the pattern 4 story

  *Recommended, all four.* Each one is a standard of professional line charts that
  needs 10+ lines of Plotly today.
- **D8. Reference lines with several series.**
  - `avg_line` is one line at the mean of every point drawn, the same rule as in
    `bar_plot`. `avg_line_mode` is dropped: its two modes differ only when series
    have different lengths.
  - The legacy `avg_group_line` becomes `overall_line`: one line, in the theme's
    neutral colour, with the value of all series together at each x. With `agg`
    it is the same aggregate over all rows (a true total or mean); with
    pre-aggregated rows the raw rows aren't there to recompute it, so it is the
    mean of the series, as in the legacy code, named "Mean of series" in the
    legend and hover so it is never read as the overall value.

  *Recommended:* the legacy per-x line averaged the series' values even when they
  came from raw rows, so a mean of means was shown as the overall mean.
- **D9. Too many series:** more series than the theme has colours raises, and the
  message suggests filtering in the query or using `highlight` (dimmed series
  don't need their own colour). This replaces `max_groups` (raise above 8) and
  `top_n_groups` (keep the 8 most frequent). *Recommended:* the theme decides how
  many colours are distinguishable, and silently dropping series is what principle
  2 forbids.
- **D10. New names for the glossary:** `time_grain`, `missing_periods`, `rolling`,
  `events`, `overall_line`, `show_markers`, `line_shape`, `fill_area`,
  `rangeslider`. Final names are approved with this plan, as in plan 0003.

## Tests delivered with it
- **Contract:** `line_plot` registered in the contract test, so it runs on pandas,
  polars and pyarrow and returns a tagged, themed figure that leaves the input
  unchanged.
- **Statistics:** the rolling mean against pandas `rolling(min_periods=1).mean()`,
  including gaps (NaN) inside the window.
- **Bucketing:** each `time_grain` against hand-written dates, including weeks
  that cross a year end and a leap day; the period list with empty periods inside
  and at no edge.
- **Grain inference (`"auto"`):** daily, weekly (Mondays), monthly and quarterly
  dates each give their grain, also with periods missing; timestamps at random
  times and every-other-day dates raise and name `time_grain`.
- **Behaviour that could quietly go wrong:**
  - pre-aggregated rows with a repeated `x` raise and name `agg`
  - an empty period becomes a gap, a zero or a bridge, as asked
  - a numeric `x` given out of order is drawn sorted; a text `x` keeps its order
  - `overall_line` with `agg="mean"` is the mean of all rows, not the mean of
    series means (a case where the two differ)
  - confidence bands match `stats.intervals` for the same rows and seed
- **Every conflicting option pair** raises, and the message names both options.
- **Showcase data:** any new answer-key rows are measured by
  `test_showcase_data.py`.

## Acceptance criteria
- `ev.line_plot` is public, follows the contract, and its docstring documents every
  option, conflict and trace role.
- The legacy `line_plot` and `time_series_plot` have no option left without an
  equivalent, except those removed by an approved decision.
- The gallery notebook covers every option, is executed by the build script, and
  rebuilds byte-identically.
- The visual review loop finds no open defect in the notebook's figures, in both
  themes.
- `ruff check`, `ruff format --check`, `mypy src`, `pytest` and the notebook run
  pass; the knowledge sync loop is complete; the independent review has run once
  and its findings are resolved.
