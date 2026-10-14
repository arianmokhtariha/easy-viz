# Theme package

Covers: src/easy_viz/theme/__init__.py

## Responsibilities
- Be the only place in the package where colour, font and size values live. A plot
  never writes a colour, a font or a pixel size itself: it reads a role from a
  `Theme` (`theme.reference`, `theme.label_font_size`, ...).
- Turn a theme into a Plotly template, so figures pick up the look without each plot
  styling axes, fonts and backgrounds.
- Provide the two built-in themes (`dark`, `light`), the global theme every plot uses
  by default, and the per-call `theme=` override.
- Hold the colour maths (parsing, WCAG contrast) that theme validation and the
  contrast tests share.

## How it works
| Module | Doc | Role |
|---|---|---|
| `theme.py` | [theme.md](theme.md) | the `Theme` dataclass, its validation, and `build_template()` |
| `registry.py` | [registry.md](registry.md) | `DARK`, `LIGHT`, the active theme, `get_theme` / `set_theme` / `resolve_theme`, Plotly template registration |
| `_color.py` | [_color.md](_color.md) | colour parsing and WCAG contrast maths |
| `__init__.py` | this page | re-exports `Theme`, `get_theme`, `set_theme` |

How a figure gets its theme:
1. A plot function calls `resolve_theme(theme, caller="<its name>")`: a `Theme` or a
   built-in name passed to the call wins, `None` means the global theme.
2. It colours its traces from that theme's role fields.
3. `easy_viz._layout.apply_base_layout` sets `fig.layout.template` to
   `build_template(theme)`, plus the title block and size (see
   [_layout.md](../_layout.md)).

Dependencies point one way: `theme/` imports the standard library, `plotly`,
`easy_viz.theme` itself and `easy_viz._validate` (for its number checks and message
format). It never imports `plots/`, so any module may import it.

## Invariants
Tested on every built-in theme (`tests/theme/test_theme.py`):
- `text` and `muted_text` reach 4.5:1 on both `background` and `plot_background`.
- `reference`, `reference_secondary`, `positive` and `negative` reach 4.5:1 on
  `plot_background`, because plots also use them for call-out text. `text` reaches
  4.5:1 inside an `overlay_background` box on the plot area.
- Every stop of `diverging_scale` and `sequential_scale` reaches 4.5:1 under
  `cell_text`, and the heatmap template draws cell labels in `cell_text`.
- Every `colorway` colour reaches 3:1 on `plot_background` (WCAG's level for
  graphical objects).
- Parity: every field is set in both built-ins (the dataclass has no defaults, so a
  missing value fails at import), the colorways have the same length, and each scale
  has the same stop positions in both.
- `plotly.io.templates.default` is never changed: easy-viz restyles only its own
  figures.

## Pitfalls
- **CSS colour names (`"white"`) are rejected on purpose.** Contrast maths needs the
  channels, and a 148-name table would be a second source of truth. Hex says the
  same thing.
- **Plotly draws all heatmap cell labels in one colour** (`textfont.color` is a
  scalar). That is why the label-carrying scales are built around `cell_text` instead
  of Plotly's stock scales: classic RdBu peaks near white at 0, which gives white
  labels a 1.1:1 contrast.
- **The light theme is not the dark one inverted.** Its label-carrying scales stay
  light (dark text on them), its marker scale has a grey midpoint (RdBu's near-white
  middle vanishes on white), and its colorway is darkened hue by hue so series *n*
  has the same hue family in both themes.
