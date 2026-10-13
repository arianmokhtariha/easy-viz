# Layout helpers

Covers: src/easy_viz/_layout.py

## Responsibilities
The figure-level layout every plot shares, so no plot re-solves it:
- `escape_text()`: make user text safe from Plotly's LaTeX trigger
- `grid_geometry()`: subplot spacing and figure height from pixel budgets
- `apply_base_layout()`: theme template, title block and figure size

## How it works
- **`escape_text(text)`** replaces every `$` with the HTML entity `&#36;`. Two `$`
  anywhere in a string switch Plotly into LaTeX mode ("Revenue from $1M to $3M"
  renders as garbled maths). The entity renders as a plain `$`. Other HTML is left
  alone, so users can pass `<b>` or `<br>` on purpose.
- **`grid_geometry(n_plots, n_cols, *, width, height, theme) -> GridGeometry`**
  (`n_rows, n_cols, h_spacing, v_spacing, height`), ported from the original
  `_grid_geometry`:
  - `make_subplots` takes spacing as a fraction of the grid, so a fixed fraction
    starves large grids (at `0.12`, nine rows leave ~11 px per row). Gaps are
    instead pixel budgets from the theme (`row_gap_px`, `col_gap_px`), converted
    against the figure height and width.
  - With `height=None`, the height is `n_rows * (row_plot_px + row_gap_px)`, as in
    the original module (but see Pitfalls on small grids).
  - Each spacing is capped at `0.5 / (count - 1)`: gaps never take more than half
    the axis, even under a small forced `height`, and `make_subplots` never rejects
    the value.
  - Fewer plots than columns use one column per plot (`n_cols` is clamped), so a
    lone panel fills the width. The original kept empty columns; callers read
    `n_cols` from the result.
  - `width=None` uses `easy_viz.config`'s width, as `apply_base_layout` does.
- **`apply_base_layout(fig, *, title, subtitle, width, height, theme)`**:
  - sets `template` to `build_template(theme)` (see
    [theme/theme.md](theme/theme.md))
  - title: bold, escaped, centred (placement comes from the template)
  - subtitle: Plotly's native `title.subtitle` (smaller, `muted_text`), escaped. It
    is a real layout property rather than HTML inside the title, so users can
    restyle it with `fig.update_layout(title_subtitle_font_size=...)`.
  - top margin: `title_top_px` + 1.5 × each shown line's font size + `title_gap_px`,
    so a two-line title never overlaps the plot or the subplot titles below it
  - `width=None` uses `get_config().width`; `height=None` leaves the height unset, so
    Plotly auto-sizes
  - `None` or `""` for the title or subtitle shows no line and reserves no space

## Invariants
- Every user-supplied string that reaches a figure through these helpers is escaped.
- Spacing fractions are never literals; they come from theme budgets.
- `apply_base_layout` sets only theme, title, top margin and size. Plot-specific
  choices (legend visibility, hover mode, axis types) stay in the plot.
- The config width is read at call time, so `set_config` affects later calls.

## Pitfalls
- **The auto height leaves out the fixed margins** (the title block, up to about
  120 px, and Plotly's bottom margin). That overhead is shared by all rows, so a
  one-row grid gets noticeably less than `row_plot_px` of drawing height while a
  five-row grid gets close to it. This keeps the original module's behaviour; revisit
  it in the visual review of the first ported grid plot, by adding the margins to the
  auto height.
- **The gaps are converted against the full figure size, margins included**, as in
  the original module, while Plotly applies the fraction to the plot area inside the
  margins. Drawn gaps come out about 80% of their nominal px. The budgets were tuned
  under this conversion, so don't "fix" one without the other.
- **`row_gap_px` budgets a subplot title plus the upper row's tick labels, not an x
  axis title.** A grid that titles the x axis of every row needs a larger budget (or
  titles only the bottom row), or the axis title collides with the next row's
  subplot title.
- **The 1.5 line-height factor** in the top margin is a typographic ratio for
  Plotly's line spacing, not a style value; title sizes stay in the theme.
