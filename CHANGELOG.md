# Changelog

Changes to easy-viz, newest first. Format: [Keep a Changelog](https://keepachangelog.com/);
versions follow [Semantic Versioning](https://semver.org/).

Each release's entry is also its GitHub release text, so the format is fixed and
checked by `scripts/release_notes.py` ([decision 0013](docs/decisions/0013-automated-releases.md)):
`## X.Y.Z - YYYY-MM-DD`, a one-paragraph summary, then only these sections, in this
order: Added, Changed, Deprecated, Removed, Fixed, Security, Internal. Internal
lists work that doesn't change what users install or call (CI, tests, docs).

## Unreleased

### Added
- `bar_plot`: bars per category from any query-result shape (one row per category,
  raw rows with `agg`, series in a column with `color`, or in several columns with a
  list `y`). Sorting, top N with an optional "Other" bar, side-by-side, stacked
  (with totals) or 100 % bars, horizontal layout, value labels, `highlight`,
  `color_map`, colouring by value (sequential, diverging or by sign), average and
  target lines. With raw rows, bootstrap or standard-error confidence intervals and
  a flag on bars built from too few rows. It replaces the original module's
  `bar_plot` and `grouped_bar_plot`.
- `line_plot`: lines over an ordered axis, usually time, from any query-result
  shape (one row per period as-is, raw rows with `agg`, series in a column with
  `color`, or in several columns with a list `y`). A time axis is always
  continuous: the calendar grain is read from the data (or set with
  `time_grain`), raw dates are bucketed into it, and a period without rows shows
  as a gap (or a zero, or bridged, with `missing_periods`) instead of being
  silently skipped. Rolling means over calendar periods, confidence bands with raw
  rows, `highlight`, `color_map`, an overall line across series, average, target
  and event lines, value labels on every point or only the last, both ends or the
  extremes, markers, step and spline lines, area fill, log axes and a range
  slider. It replaces the original module's `line_plot` and `time_series_plot`;
  line width and marker size moved to the theme.
- `Theme.line_width` and `Theme.marker_size`: the width of data lines and the size
  of their markers. Custom themes built field by field need values for them.
- `Theme.marker_sequential_scale`: the low-to-high scale for marks coloured by
  value, visible at its lowest colour. Custom themes built field by field need a
  value for it.
- Themes: `Theme`, `set_theme()` and `get_theme()`, with two built-in themes, `dark`
  (the original house style) and `light`. Both are also registered as the Plotly
  templates `easy_viz_dark` and `easy_viz_light` for your own figures; easy-viz never
  changes Plotly's default template.
- Global output defaults: `get_config()` and `set_config()` for the default figure
  width (1400 px) and export resolution (2x).
- Static export: `save()` for one figure and `save_many()` for a batch in a single
  Chrome session. PNG, JPEG and WebP use the configured resolution; SVG and PDF are
  written at the figure's true size. Needs `pip install "easy-viz[export]"` and
  Chrome.
- `EasyVizWarning`: every easy-viz warning uses it, and it points at the line of your
  own call, so `warnings.filterwarnings("ignore", category=ev.EasyVizWarning)`
  silences easy-viz without silencing other libraries.
- Type information for type checkers (`py.typed`).
