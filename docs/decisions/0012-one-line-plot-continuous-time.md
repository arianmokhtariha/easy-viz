# 0012: One line function, with a continuous time axis

**Status:** accepted · **Date:** 2026-10-16

## Context
The legacy module had two functions that draw lines:
- `line_plot`: draws the rows it gets, without aggregating, with groups, a rolling
  mean, an average line in two modes, a per-x "group average" line and min/max
  labels
- `time_series_plot`: buckets raw rows into a calendar frequency (`freq="MS"`),
  aggregates them, and leaves empty periods as gaps

Both draw one line per series over an ordered axis; the second only adds the step
that turns raw rows into one value per period. Product principle 8 ("one function
per chart concept") asks whether one function can do both with nothing lost, as
[decision 0010](0010-one-bar-plot.md) did for the bar charts.

A second problem showed while porting: a SQL `GROUP BY` returns no row for a period
without data, and a line silently bridges it, as if the measure went on. On the
showcase data, a weekly query of Gifts orders skips 10 of 105 weeks. Neither legacy
function caught this for data the query had already bucketed.

The product manager approved plan 0004 on 2026-10-16. The plan was graduated in the
pull request that added `line_plot`, whose description keeps its scope; this record
keeps the decisions.

## Decision
Product manager, 2026-10-16:
- **`time_series_plot` merges into `line_plot`, losing no option.** Bucketing becomes
  `time_grain` (`"hour"` to `"year"`, weeks from Monday as in SQL), aggregating is
  the `agg` every function has, `group_col` becomes `color`.
- **A time axis is always continuous** (the product manager's own requirement).
  Every period between the first and the last is on the chart:
  - `time_grain="auto"` (the default) reads the grain from the data: the calendar
    grain every date sits on, if the closest dates are one period apart. Dates on
    no regular grid raise and name `time_grain`; `time_grain=None` draws points as
    they are.
  - Empty periods are gaps by default, announced by a warning; `missing_periods`
    draws them as zero or bridges them.
  - The rolling mean runs over the calendar, so `rolling=7` on daily data is
    always 7 days.
- **`overall_line` replaces the legacy per-x group average.** With raw rows it is
  the same `agg` over every row at that x (a true overall mean or total); with
  pre-aggregated rows only the mean of the series can be computed, and it is named
  "Mean of series" so it is never read as the overall value.
- **Line width and marker size are theme fields**, not parameters; `opacity`,
  `max_groups`, `top_n_groups`, `sort_x`, `avg_line_mode` and `annotate_extremes`
  are dropped or absorbed (`show_values="extremes"`). Numeric and time axes are
  drawn sorted, text axes keep the query's order.
- **New options:** confidence bands (`ci`), `highlight`, `color_map`, `target`,
  `events`.
- **More series than the theme has colours raises**, suggesting a filter or
  `highlight`; series are never dropped silently.

## Alternatives
- **Port both functions:** two answers to "draw a line over time", with users left
  to learn which one aggregates.
- **Continuity only with an explicit `time_grain`:** leaves the most common case,
  data the query already bucketed, silently bridged.
- **Infer the grain from the most common gap, always:** irregular timestamps would
  be bucketed by a guess; principle 2 forbids guessing, so ambiguous dates raise.
- **Keep the legacy group average for raw rows:** a mean of means hides changes in
  the mix of series (a slow warehouse shipping more orders leaves it flat).

## Consequences
- **Easier:** one function for every line chart; a missing period can no longer
  pass unnoticed; the bare call on raw daily rows already gives a daily line.
- **Harder:**
  - a time axis with dates on no regular grid (random timestamps, every other day)
    needs `time_grain` or `time_grain=None` before it draws
  - behaviour that differs from the legacy functions: line width and marker size
    are set through the theme; text axes are no longer sorted alphabetically;
    `time_series_plot`'s default `agg="mean"` is now `agg=None` (pre-aggregated)
  - `bar_plot` and `line_plot` share their option checks and reference lines in
    `plots/_shared`, so a change there affects both
