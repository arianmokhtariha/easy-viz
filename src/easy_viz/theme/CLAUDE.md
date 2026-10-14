# Guide: themes (`src/easy_viz/theme/`)

## Rules
- **This is the only place in the package where colour, font and size literals
  live.** One exception: output defaults (default figure width, export scale) live in
  `easy_viz.config`, because they describe the output file, not the look
  (decision 0007).
- **A plot never needs a colour the theme doesn't define.** If a plot needs a new
  visual role (e.g. a "target line" colour), add a `Theme` field. Don't hard-code it
  in the plot.
- **Built-in themes stay in parity:**
  - a new field gets a value in every built-in theme in the same PR
  - nothing reads a field that any built-in theme leaves unset
- **Colour scales that carry text labels** meet the contrast rule in
  `docs/conventions.md` (Plotly constraints). How the original module achieved it:
  `_CORR_DIVERGING` and `SEQ_BLUE` in `custom_plots.py`.
- **Changes are reviewed visually:** render every built-in theme with
  `uv run python scripts/render_theme_samples.py` (writes `.review/theme/<name>.png`),
  run the visual review loop on the sheets, and give their paths in the report. A new
  `Theme` field gets a visible use on the sample sheet in the same change.
