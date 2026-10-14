# Roadmap

Where easy-viz stands. Updated in the PR that changes it.

## Now
- [Plan 0002: Showcase dataset and gallery](docs/plans/0002-showcase-data-and-gallery.md) (proposed)

## Next
- Plan 0003: port `line_plot` and `bar_plot` with their gallery notebooks, then
  release 0.1.0

## Later
- Port the remaining functions by family: distribution, relationship, comparison,
  timeseries, business, ml
- Report features: waterfall, cohort heatmap, `highlight`, `color_map`, takeaway titles
- Docs site rendering the gallery notebooks
- README showcase built from gallery images
- Automated releases: a version bump merged to `main` builds in CI, creates the
  GitHub release and publishes to PyPI through trusted publishing

## Done
- Foundation (plan 0001): table intake for pandas, polars and pyarrow with SQL type
  normalisation, option validation, layout helpers, the `dark` and `light` themes,
  trace roles, global config and static export, plus repository-wide checks for
  layering, styling literals, the plot contract and the knowledge base
- CI: lint, formatting, type checks and tests on Python 3.13–3.15 for every pull
  request and every push to `main`
