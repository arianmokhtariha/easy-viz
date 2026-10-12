# Conventions

Binding rules and vocabulary for all easy-viz code. Changing anything here is a
public-API decision: propose it to the product manager first.

## Parameter glossary
One name per concept, in every function.

| Name | Meaning |
|---|---|
| `df` | input table: pandas, polars, pyarrow or anything else narwhals accepts |
| `x` | category or independent column (BI: Axis); `orientation` only changes where it is drawn |
| `y` | measure column (BI: Values). `str`, or a list of columns: one series per column |
| `color` | column that splits the data into coloured series (BI: Legend) |
| `facet_col`, `facet_row` | columns that split the data into a grid of panels (BI: Small multiples) |
| `hover` | extra columns shown on hover (BI: Tooltips) |
| `size`, `label` | bubble-size column; text-label column |
| `cols`, `exclude` | column selection for multi-column functions |
| `agg` | `None` = plot values as-is; otherwise `Literal["sum", "mean", "median", "count", ...]` |
| `sort_by`, `ascending`, `top_n` | ordering and truncation of categories |
| `orientation` | `Literal["vertical", "horizontal"]` |
| `log_x`, `log_y` | log axes |
| `value_format` | Python format spec (`".3g"`, `",.0f"`), never d3 format |
| `color_map` | `dict[str, str]`: fixed colour per category, identical across charts |
| `highlight` | category or categories to emphasise; the rest use the theme's dimmed colour |
| `title`, `subtitle` | `subtitle` carries the method note or the measure |
| `width`, `height` | px; `height=None` means auto-size |
| `theme` | per-call theme override; `None` = the global theme |

Names retired from `custom_plots.py` (never reintroduce):
- `color_by`, `group_col` (when it meant a series split), `split_col` → `color`
- `ignore_cols` → `exclude`

A new concept is added to this table in the same PR that introduces it.

## Query-result shapes
How every function treats the shapes SQL queries return (product principle 1). These
rules are the same in every function that has the slot.

1. **Pre-aggregated is the default.** With `agg=None`, values are plotted as-is.
   - If a combination of `x`, `color` and facets repeats, raise `ValueError`. The
     message names `agg` and says how many keys repeat.
   - Never sum silently.
2. **Raw rows need `agg`.**
   - `agg="sum"`, `"mean"`, `"median"`, `"min"`, `"max"` aggregate `y` within each
     `x` / `color` / facet group before plotting.
   - `agg="count"` counts rows and needs no `y`.
3. **Long format uses `color`. Wide format uses a list `y`.**
   - `color="region"` draws one series per value of that column.
   - `y=["revenue", "cost"]` draws one series per column, named after the column.
   - Both together raise `ValueError`: pick one shape.
4. **Row order is meaningful.** When `sort_by=None` (the default), categories keep
   their first-appearance order, so the query's `ORDER BY` controls the chart.
   Datetime axes are always chronological.
5. **Time columns are recognised.** Date, datetime and ISO-date string columns used as
   `x` are treated as time.
6. **SQL types are normalised** in one place (`_data`): decimals → float, dates →
   datetime, nullable and Arrow types → standard ones.
7. **NULLs are dropped, announced.** Rows with nulls in a used column are dropped with
   an `EasyVizWarning` that states how many rows were dropped and in which columns.

## Public function contract
Every public plotting function:
1. Takes `df` and its required columns positionally. Every option comes after `*`
   (keyword-only), so options can be added or reordered without breaking callers.
2. Is fully typed: `Literal[...]` for string options, no `Any` in the public
   signature.
3. Returns `go.Figure`. It never calls `.show()`, never prints, never mutates `df`.
4. Validates before computing anything:
   - missing columns and wrong dtypes raise `TypeError`/`ValueError`
   - every conflicting option pair raises `ValueError`
5. Reports non-fatal issues with `warnings.warn(..., EasyVizWarning)`: nulls dropped,
   categories folded into "Other", an option with no effect in this mode.
6. Tags every trace with a role (see below).
7. Gets its numbers from `stats/` functions.
8. Has a numpy-style docstring with:
   - a one-line summary of the question the plot answers
   - every parameter, with its default and any conflicts
   - a `Trace roles` section
   - an `Examples` section

## Error and warning messages
Format: `"<function>: <what is wrong>. <how to fix it>."` Name the offending
parameter(s) and the value received. Example:
`"bar_plot: color_by_value=True cannot be combined with color='region'. Remove one of them."`

## Trace roles
Set via `_meta.tag()` as `meta={"role": ..., "group": ...}`. Users target pieces
after the fact like this:
`fig.update_traces(line_color="red", selector=lambda t: (t.meta or {}).get("role") == "trendline")`

| Role | Used for |
|---|---|
| `data` | the main marks |
| `trendline` | fitted lines |
| `ci` | confidence intervals and bands |
| `reference` | average/target lines and other reference lines |
| `marginal` | marginal distributions |
| `density` | KDE and 2-D density |
| `cumulative` | cumulative curves (e.g. Pareto) |
| `highlight` | emphasised subsets |

A new role is added here in the same PR that introduces it.

## Plotly constraints (still open in Plotly 7.1)
- **plotly.js (JavaScript) draws the chart** in the notebook's web view; Python only
  describes it. Hover and zoom live there, very large point counts get slow there,
  and static export needs Chrome.
- **Two `$` in a string switch on LaTeX mode.** Every user-supplied string goes
  through `_layout.escape_text()`.
- **`make_subplots` spacing is a fraction of the whole figure.** Use
  `_layout.grid_geometry()` (pixel budgets), never literal fractions.
- **Heatmap `textfont.color` is one colour for all cells.** Colour scales that carry
  labels keep WCAG 4.5:1 contrast against that one colour.
- **Each kaleido export starts Chrome.** Batch exports with `pio.write_images()`.
- **Plotly ships no type information.** Keep untyped values inside the wrapper;
  public signatures stay concrete.
