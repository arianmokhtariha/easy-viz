# Changelog

Changes to easy-viz, newest first. Format: [Keep a Changelog](https://keepachangelog.com/);
versions follow [Semantic Versioning](https://semver.org/).

Each release's entry is also its GitHub release text, so the format is fixed and
checked by `scripts/release_notes.py` ([decision 0013](docs/decisions/0013-automated-releases.md)):
`## X.Y.Z - YYYY-MM-DD`, a one-paragraph summary, then only these sections, in this
order: Added, Changed, Deprecated, Removed, Fixed, Security, Internal. Internal
lists work that doesn't change what users install or call (CI, tests, docs).

## Unreleased

### Internal
- A `/release` command for the maintainer: it reads every change since the last
  release, picks the version number and writes the changelog entry that becomes
  the release text.
- The code reviewer that checks every branch before its pull request now also
  reviews it against the product principles, and reports that verdict in its own
  section.

## 0.1.0 - 2026-10-18

This is the first release of easy-viz. You pass a query result to one function and
get back a finished Plotly figure in the easy-viz theme. It has two plot functions so
far, `bar_plot` and `line_plot`, along with themes, output defaults and image export.

### Added
- `bar_plot`: bars per category from any query-result shape: one row per category,
  raw rows with `agg`, series in a column with `color`, or several measure columns
  as a list `y`. It sorts, keeps the top N with an optional "Other" bar, and draws
  side-by-side, stacked (with totals) or 100 % bars, vertical or horizontal. It
  also has value labels, `highlight`, `color_map`, colouring by value (sequential,
  diverging or by sign), and average and target lines. With raw rows it adds
  bootstrap or standard-error confidence intervals and flags bars built from too
  few rows.
- `line_plot`: lines over an ordered axis, usually time, from the same query-result
  shapes. A time axis is always continuous: easy-viz reads the calendar grain from
  the data (or takes `time_grain`), buckets raw dates into it, and shows a period
  without rows as a gap, a zero or a bridged line (`missing_periods`) instead of
  skipping it silently. It also draws rolling means over calendar periods,
  confidence bands from raw rows, `highlight`, `color_map`, an overall line across
  series, and average, target and event lines. Value labels can go on every point,
  the last one, both ends or the extremes. Markers, step and spline lines, area
  fill, log axes and a range slider are options too.
- Themes: `Theme`, `set_theme()` and `get_theme()`, with two built-in themes, `dark`
  and `light`. A theme sets every colour, font and size, including line width,
  marker size and the colour scale for marks coloured by value. Both are also
  registered as the Plotly templates `easy_viz_dark` and `easy_viz_light` for your
  own figures; easy-viz never changes Plotly's default template.
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

### Internal
- CI runs lint, type checks and the tests on Python 3.13, 3.14 and 3.15, and once
  more with every dependency at the oldest version easy-viz allows.
- The gallery has one executed notebook per plot function. Every chart in it starts
  from a SQL query on a fictional retailer's data.
- GitHub Actions publishes each release to PyPI without a stored token and uses its
  changelog entry as the GitHub release text.
