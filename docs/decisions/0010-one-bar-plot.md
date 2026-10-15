# 0010: One bar function, `bar_plot`

**Status:** accepted · **Date:** 2026-10-15

## Context
The legacy module had two functions that draw bars per category:
- `bar_plot`: plots pre-aggregated values as they are, with sorting, top N, labels
  and colour options
- `grouped_bar_plot`: aggregates raw rows to a mean or median, with bootstrap or
  standard-error intervals, a low-n flag and n labels

Both split bars into series by a second column. Product principle 8 ("one function
per chart concept") asks whether one function can do both jobs with nothing lost. A
third legacy function, `pareto_plot`, also draws bars per category, but adds a
cumulative line on a second axis and a cutoff.

Porting is also redesign (plots guide), so the product manager decided the shape of
the merged function when approving plan 0003. The plan was graduated in the pull
request that added `bar_plot`, whose description keeps its scope and decisions; this
record keeps the decisions.

## Decision
Product manager, 2026-10-15:
- **`grouped_bar_plot` merges into `bar_plot`, losing no option.** The difference
  becomes options: `agg` (raw rows), `ci`, `ci_level`, `n_boot`, `random_state`,
  `min_n` (the low-n flag) and `show_n` (the n labels). `split_col` and `group_col`
  become `color`.
- **`pareto_plot` stays a separate function**: the cumulative line, second axis and
  cutoff make it a different chart.
- **One colour per series by default.** The legacy default gave every bar its own
  colour, which suggests a meaning that isn't there. Deliberate colouring is
  `highlight`, `color_map`, and `color_by_value` in three modes (sequential,
  diverging around `color_midpoint`, sign), with any Plotly scale via `colorscale`.
  `single_color` is dropped.
- **"Other" is opt-in** (`other=True` with `top_n`). With raw rows it uses the same
  `agg`, so it is right for every aggregate; with pre-aggregated rows easy-viz can
  only add values up, which is wrong for averages and rates, and only the user knows
  which a column is.
- **Facets come later**, in one plan for every function.

## Alternatives
- **Port both functions:** two answers to "draw bars per category", with users left
  to learn which one computes and which one doesn't.
- **Fold `pareto_plot` in as `cumulative=True`:** its second axis, cutoff guide and
  cumulative trace would turn most bar options into conflicts.
- **"Other" by default with `top_n`:** silent sums of averages; principle 2 forbids
  guessing.
- **Keep `color_by_value` out:** colour by value repeats bar height, but diverging
  and sign colouring add information height doesn't show (above or below a
  midpoint), so it stays as an option, never a default.

## Consequences
- **Easier:** one function to learn for every bar chart of categories; the statistics
  of `grouped_bar_plot` work with every query shape.
- **Harder:**
  - many options, so many conflict pairs: each one raises, is tested, and is shown in
    the gallery's *Limits* section
  - behaviour that differs from the legacy functions: `ci="sem"` with a median raises
    (the legacy function silently switched to bootstrap), bars keep the query's order
    unless `sort_by` is set (the legacy `grouped_bar_plot` always ranked by value),
    nulls are dropped with a warning
  - bootstrap intervals use the same method and seed (0), but numpy's current
    generator (`default_rng`) instead of the legacy `RandomState`, so their exact
    ends differ slightly from the original module's
- Value colouring needed a scale whose lowest colour stays visible on the plot area,
  so `Theme` gained `marker_sequential_scale`.
