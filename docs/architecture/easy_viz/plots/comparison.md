# Comparison plots

Covers: src/easy_viz/plots/comparison.py

## Responsibilities
`bar_plot`: one value per category, from any query-result shape, with the statistics
needed to compare groups honestly. It is the legacy `bar_plot` and
`grouped_bar_plot` merged into one function
([decision 0010](../../../decisions/0010-one-bar-plot.md)); the public API is its
docstring, not restated here.

## How it works
The function is a short pipeline of private helpers; `_Options` (frozen) carries
every option between them.

1. **`_check_options`**: everything that needs no data. Choices, the query-shape
   rules (`y` needed unless `agg="count"`; a list `y` and `color` conflict), then one
   helper per option group (`_check_statistics`, `_check_ordering_and_layout`,
   `_check_labels`, `_check_colour`). Conflicts raise; options with no effect in the
   current mode warn (`_validate.warn_no_effect`). "Changed from its default" is read
   against the module constants (`CI_LEVEL`, `N_BOOT`, ...), which are also the
   signature's defaults.
2. **`_data` intake**: `load`, `require_numeric`, `parse_time`. A time `x` then
   refuses `sort_by`, `top_n` and `highlight` (`_check_time_axis`) before nulls are
   dropped.
3. **`_shape`** builds `_Bars`: a series × category grid of values (NaN = no bar),
   plus row counts `n` (whenever `agg` is set) and interval bounds (with `ci`).
   - `_data.aggregate` gives the bars, in first-appearance order.
   - `sort_by="value"` uses `_category_weights`: with `agg`, the category's own
     aggregate over all its rows, ignoring the `color` split (the legacy
     `grouped_bar_plot` rule, so a mean is ranked by a mean, not by a sum of means);
     with `agg=None`, the sum of its bars (the legacy `bar_plot` rule).
   - "Other" (`top_n` + `other=True`) is built from the cut rows with the key
     replaced by the label, then aggregated like any bar: with the same `agg` on raw
     rows (right for every aggregate), summed when `agg=None`. Its counts and
     interval come from the same rows. The label becomes "Other (N categories)" if a
     kept category is already called "Other".
   - Intervals: `_data.group_arrays` gives each bar's raw values,
     `stats.intervals.interval` the bounds.
4. **`_check_bars`**: checks that need the data: negative values with
   `barmode="percent"`, `highlight` naming a category not drawn, `color_map`
   coverage, more series than the theme has colours.
5. **`_draw`**: one `go.Bar` per series (role `data`, group = series name, `None`
   for a single series), then the reference traces, then the axes:
   - labels and hover text are built in Python (`_labels`), so `value_format` is a
     Python format spec; `_layout.format_value` gives the automatic k/M/B format,
     and `_layout.d3_format` passes a spec to the axis and colour bar when it means
     the same in d3-format
   - colours by mode (`_marker`): one theme colour for a single series (dimmed by
     `highlight`, `other` for the "Other" bar), `colorway` or `color_map` per
     series, or by value (`marker_sequential_scale`, `marker_diverging_scale` with
     `cmid`, or `positive`/`negative` around the midpoint)
   - small groups (`min_n`): a diagonal hatch overlaid on the bar plus "⚠" on the
     label, explained in the subtitle
   - error bars: asymmetric, from the interval bounds, in `theme.neutral`
6. `apply_base_layout` with the automatic title and subtitle, then
   `_layout.auto_height` when `height=None` (taller for horizontal bars).

**Custom constructions** (Plotly has no native option):
- *Stack totals*: a text-only scatter trace (role `reference`, group `total`) at the
  end of each stack. Negative segments stack downwards in `relative` mode, so the
  total sits beyond whichever end the net value points to.
- *Reference lines* (`avg_line`, `target`): line traces (role `reference`, groups
  `average` and `target`) on a hidden overlay axis that runs from 0 to 1 across the
  plot. A trace on the category axis would end at the outer bars' centres; a layout
  shape would span the plot but carry no trace role.

## Invariants
- The user's table is never modified; all table work is in `_data`.
- Every trace has a role; error bars belong to their `data` trace.
- Value labels appear on every side-by-side bar or on none (`_labels_fit`): Plotly
  hides each label that doesn't fit on its own, which leaves a chart with labels on
  some bars only.
- With `ci`, labels sit inside at the base of the bar (`insidetextanchor="start"`),
  clear of the whiskers; stacked labels sit inside, centred.
- Every message names the option(s) and value(s) in the conventions format.

## Pitfalls
- **The label-fit check is an estimate** (`_layout.text_px`: characters × font size
  × 0.6, against an estimated plot width). It errs towards hiding labels; the hover
  always has the value.
- **Plotly's default pattern fill makes the gaps between hatch stripes
  transparent**, so on a white page the bar turns half white and white labels in it
  disappear. The hatch uses `fillmode="overlay"`: thin stripes in the plot-area
  colour on top of the bar's own colour.
- **Reference lines cross the value labels of bars at the same height.** Plotly
  draws scatter traces above bar text, and moving labels per collision is not worth
  the complexity; the line's own label sits at its end, clear of the bars.
- **`barnorm="percent"` needs `barmode="stack"`, not `"relative"`**: that is why
  `"percent"` refuses negative values instead of stacking them downwards.
- **Numeric `x` is drawn as categories** (`type="category"` with an explicit
  `categoryarray`), so the query's order holds; only date columns get a date axis.
- **Python format specs and d3-format differ outside the shared forms** (`g`
  rounding, `s` exists only in d3). An unshared spec formats labels and hover but
  leaves Plotly's own tick format on the axis.
