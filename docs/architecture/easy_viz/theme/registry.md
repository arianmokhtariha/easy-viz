# Theme registry

Covers: src/easy_viz/theme/registry.py

## Responsibilities
- Define the built-in themes `DARK` and `LIGHT`.
- Hold the active global theme, and decide which theme a call draws with.
- Register each built-in as a Plotly template, so users can style their own figures
  with `template="easy_viz_dark"` or `"easy_viz_light"`.

## How it works
- `ThemeName = Literal["dark", "light"]` is the public type of a built-in name.
  `BUILTIN_THEMES` maps each name to its theme; a test keeps the two in sync.
- **`DARK`** is the house style of the original module: page `#0e1117` around a
  `#1a1a1a` plot area, Plotly's ten-colour qualitative palette, gold reference lines,
  and the module's label-safe scales (`_CORR_DIVERGING`, `SEQ_BLUE`), marker scale
  (`_RDBU`) and severity ramp, unchanged.
- **`LIGHT`** is its equal for white-page reports: the same roles and hue order,
  darkened where white needs it (yellow becomes mustard, gold becomes a dark amber),
  and its own light-surface scales whose cell labels use dark text. Both scales were
  interpolated in OKLab (a colour space where equal steps look equal) from a near-white
  midpoint to soft poles, so salience grows with |value|.
- A module-level `_active` holds the global theme (`DARK` at import).
  - `get_theme(None)` returns it; `get_theme("light")` returns that built-in,
    whatever is active, so users customise with
    `dataclasses.replace(ev.get_theme("light"), ...)`.
  - `set_theme(name_or_theme)` replaces it.
  - `resolve_theme(theme, *, caller)` is the per-call rule plot functions use: a
    `Theme` is used as given, a name is looked up, `None` means the active theme.
- An unknown name (or any other value) raises `ValueError` in the conventions format,
  naming the public function through `caller`:
  `"bar_plot: theme='blue' is not a built-in theme. Use 'dark' or 'light', or pass an
  ev.Theme."`
- On import, each built-in's template (from `build_template`, see
  [theme.md](theme.md)) is copied into `plotly.io.templates` as
  `easy_viz_<name>`. The copy keeps a user's edit of `pio.templates[...]` from
  reaching the cached template easy-viz itself applies.

## Invariants
- `plotly.io.templates.default` is never read or written. Setting the easy-viz theme
  must not restyle the user's other Plotly figures. (Tested.)
- A per-call theme beats the global one; the built-ins by name never change.
- `ThemeName` and `BUILTIN_THEMES` list the same names.

## Pitfalls
- **The active theme is process-wide state.** Tests that call `set_theme` restore it
  with a fixture (`restore_theme` in `tests/theme/test_registry.py`), or later tests
  run under the wrong theme.
- **`resolve_theme` needs `caller`.** Error messages name the user's function, not an
  internal one, so every plot passes its own name.
- **Changing a built-in value changes every user's charts.** Re-render the sample
  sheets (see [the sample-sheet script](../../scripts/render_theme_samples.md))
  and review them before merging.
