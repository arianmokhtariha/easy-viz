# Theme sample sheets

Covers: scripts/render_theme_samples.py

## Responsibilities
Render one sample sheet per built-in theme to `.review/theme/<name>.png`
(gitignored), so any theme or layout change can be judged by looking at it.

## How it works
`uv run python scripts/render_theme_samples.py` builds a grid of ten panels per
built-in theme with raw Plotly and the shared layout helpers
([`grid_geometry`, `apply_base_layout`](../easy_viz/_layout.md)), the same ones plots
use. Each panel exercises theme roles:
- the full colorway, the "Other" bucket and a reference line with a call-out box
- series drawn at `line_width` with `marker_size` markers, a legend, a `neutral`
  overall line and a `reference_secondary` line
- `highlight`: one series in colour and one px wider than `line_width` (the original
  module's emphasis), the rest `dimmed`
- heatmaps with cell labels on `diverging_scale` and on `sequential_scale`
- markers on `marker_diverging_scale` with its colour bar
- bars coloured by value on `marker_sequential_scale`, the smallest one included
- bars on `severity_scale`; `positive` / `negative` bars with call-outs
- a polar panel with translucent fills (`with_alpha`)

The title and subtitle contain `$` signs, to show the escaping works. All sheets go
out in one `pio.write_images` call, because each export starts Chrome.

## Invariants
- The sheet shows every theme role. A new `Theme` field that is visible in a figure
  gets a mark on the sheet in the same change.
- Every colour and font size on the sheet comes from the theme, and the layout from
  the shared helpers, so the sheet shows what the theme does, not what the script
  chose.

## Pitfalls
- **`pio.write_images` ignores each figure's own `layout.width` and `height`** in
  Plotly 7.1 (`write_image` and `to_image` honour them) and falls back to 700 × 500.
  The script passes the sizes explicitly.
- **Needs Chrome** for kaleido's static export (`plotly_get_chrome` installs it).
- **Sample data is deterministic** (sines, fixed lists), so sheets only change when
  the theme or layout changes.
