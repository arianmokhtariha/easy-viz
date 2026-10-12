# 0001: Plotly 7 as the only rendering core

**Status:** accepted · **Date:** 2026-10-11

## Context
easy-viz needs a rendering library that supports:
- interactive output in notebooks
- static PNG export for reports
- nearly every analytical chart type
- a figure object users can keep editing

In 2026-10 we evaluated Plotly, Bokeh, Altair, lets-plot, plotnine, seaborn,
Matplotlib, pyecharts, Highcharts, HoloViews/hvPlot and newer libraries (xy,
fastplotlib, pyobsplot), against 12 requirements taken from the original module.

## Decision
Plotly 7 is the single rendering core. There is no layer that abstracts over several
rendering libraries, and no custom renderer.

## Alternatives
- **Altair:**
  - *Strengths:* pixel-based spacing, per-cell text colour, Chrome-free export.
  - *Rejected because:* a 5,000-row default limit, no radar or beeswarm chart, only a
    workaround for a second y-axis, and statistics would need a separate pipeline.
- **Matplotlib:** best static output, but no native interactivity.
- **Multi-backend (the HoloViews/ArviZ approach):** costs multi-person years of work
  and limits every feature to what the weakest backend can do.
- **xy (reflex-dev):** promising for big data but 0.0.x (alpha). Revisit at 1.0.
- **Custom HTML/JS renderer:** would rebuild a decade of plotly.js work. The value of
  easy-viz is its API, not its renderer.

## Consequences
- **Easier:**
  - nearly all chart types are built in
  - Plotly templates provide the theme system
  - output works in Dash, Streamlit and Vizro
- **Harder:** we live with Plotly's open issues (fractional subplot spacing, the `$`
  LaTeX trigger, single-colour heatmap text, Chrome-based export), listed in
  `docs/conventions.md`.
- Keeping statistics in `stats/` (separate from drawing) keeps a second renderer
  possible later without a rewrite.
