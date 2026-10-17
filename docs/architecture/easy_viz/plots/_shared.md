# Shared plot helpers (`plots/_shared`)

Covers: src/easy_viz/plots/_shared.py

## Responsibilities
Everything two plot functions do the same way, kept once, because the library guide
forbids copied logic between modules. Internal: nothing here is public. Today
`bar_plot` ([comparison.md](comparison.md)) and `line_plot`
([timeseries.md](timeseries.md)) use it.

## How it works
- **Interval options.** `CI_LEVEL`, `N_BOOT`, `RANDOM_STATE` are the defaults of
  `ci_level`, `n_boot` and `random_state` in every signature, and the values the
  no-effect warnings compare against. `check_interval_options` checks `ci` (needs
  `agg="mean"` or `"median"`; `"sem"` refuses the median), the level, the resamples
  and the seed, and warns for settings that have no effect without `ci` or the
  bootstrap.
- **Query-result shape.** `check_shape` applies conventions rules 2 and 3: `y` is
  needed unless `agg="count"`, `color` can't be `x` (the fix text is per function),
  a list `y` and `color` can't be combined.
- **Labels and text.** `names` (one name or a list, as a list), `text` (a data value
  as plain text, dates without a midnight time), `value_label` (`"Mean order_value"`,
  from `AGG_WORDS`), `plotly_list` (NaN as `None`, so Plotly draws no mark),
  `check_value_format`, `warn_hover_with_agg` (the warning names the mark: "a combined
  bar" or "a combined point"), `conflict` (the standard two-option message).
- **Colours.** `check_color_map` (several series needed; every value readable by
  `theme._color.is_color`), `check_series_colours` (`color_map` must cover every
  series drawn in colour, or the theme's `colorway` must be long enough; the fix text
  is per function).
- **Reference lines.** `add_reference_lines(fig, lines, theme, on=...)` draws each
  `ReferenceLine` (group, value, label, colour, dash) as a `lines+text` scatter trace
  with role `reference`:
  - `on="y"`: a horizontal line at a value, drawn on a hidden `xaxis2` overlaid on
    `x` with range 0 to 1, label at the right end (`"top left"`).
  - `on="x"`: a vertical line at an x value (a number, date or category), drawn on a
    hidden `yaxis2` overlaid on `y`, label above the plot (`"top center"`).

  A trace on the other data axis would end at the outer data points, and a layout
  shape (`add_hline`) would span the plot but carry no role a user can select.

## Invariants
- Messages are built with `_validate.message`, so they keep the conventions format;
  per-function wording (fix texts, the mark's name) is passed in, never branched on
  the function name.
- Moving code here never changes a figure: `bar_plot`'s output was compared trace by
  trace and layout key by layout key before and after the move.

## Pitfalls
- **The overlay is the other axis letter.** Vertical lines span a `yaxis2` overlaid on
  `y`; horizontal ones an `xaxis2` overlaid on `x`. A chart with both (a `line_plot`
  with `avg_line` and `events`) has both overlays, which Plotly allows.
- **`fixedrange` on the overlay** keeps zooming from moving the 0-to-1 span, so a line
  still crosses the whole plot after a zoom.
