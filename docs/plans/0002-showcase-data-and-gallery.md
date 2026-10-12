# Plan 0002: Showcase dataset and gallery

**Status:** proposed

## Goal
Build the infrastructure that shows easy-viz's value:
- a fictional dataset with hidden patterns
- the notebook gallery that walks through every function and parameter
- the pipeline that turns tagged notebook cells into README images

Each plot port after this one only adds its notebook.

## Scope
**Showcase dataset** (`gallery/data/`):
- one coherent fictional business, generated with a fixed seed
- several related tables: transactions, customers, products, daily metrics,
  predictions from a churn model

Planted patterns, each chosen because a specific feature reveals it:

| Pattern | Revealed by |
|---|---|
| Simpson's paradox: price vs conversion is negative overall, positive within each region | `scatter_plot` with `color` and per-group trendlines |
| Profit concentration: ~20% of customers bring ~75% of profit | `pareto_plot` with a cutoff |
| Hidden bimodality: delivery times come from two warehouses | KDE, and `color` in distribution plots |
| Seasonality plus a structural break after a price change | `time_series_plot` with rolling averages |
| Long-tail product categories | `bar_plot` with `top_n` and "Other" |
| Correlated variable blocks | `correlation_heatmap` with cluster ordering |
| Missing-not-at-random: income missing mostly in one segment | `missing_values_plot` |
| Data-entry outliers (prices ×100) | `box_plot`, log axes |
| An overconfident churn model | `calibration_plot`, `threshold_sweep_plot` |
| Differences that look real but aren't | `grouped_bar_plot` bootstrap CIs |

`INSIGHTS.md` documents each pattern: where it is planted, how strong it is, and which
plot and parameters reveal it.

**Gallery infrastructure:**
- `gallery/README.md` as the index
- a notebook template following the gallery rules
- outputs that display both on GitHub (static image) and interactively on the docs
  site

**Build script** (`scripts/build_gallery.py`):
- regenerates the data
- executes every notebook
- exports the outputs of cells tagged `readme:<name>` to `docs/images/readme/<name>.png`
  in one batch
- saves every image output to `.review/<notebook>/<cell>.png` (gitignored), so
  agents can inspect each output visually
- can run a single notebook (e.g. `--only bar_plot`) for fast visual iteration

**Docs integration:** myst-nb renders the gallery notebooks in the docs site.

## Tests delivered with it
- `test_gallery.py`:
  - every public plot function has a notebook and an index row
  - every keyword parameter appears in its notebook
  - README image links resolve
- `test_showcase_data.py`: every pattern in `INSIGHTS.md` is present at its documented
  strength.
- CI executes all notebooks (`pytest --nbmake gallery/`).

## Acceptance criteria
- All checks pass.
- The dataset and `INSIGHTS.md` are approved by the product manager.
- At least one notebook (`line_plot` or `bar_plot`, from plan 0003) is complete, to
  prove the template.
- `docs/architecture/gallery/index.md` and `docs/architecture/scripts/index.md`
  describe the gallery pipeline. This plan file is deleted.

## Decided
- **The fictional business** is an online retailer with subscriptions (product
  manager, 2026-10-12). It deliberately differs from food delivery, which the Delivr
  portfolio project already covers, and it can hold every planted pattern above
  naturally.
