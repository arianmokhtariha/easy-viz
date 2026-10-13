# Theme dataclass

Covers: src/easy_viz/theme/theme.py

## Responsibilities
- Define `Theme`, the public, frozen dataclass that names every colour, font and size
  easy-viz draws with, by the role it plays (never by the colour it happens to be).
- Reject a theme no figure could draw, at construction time.
- Convert a theme into a Plotly template with `build_template()`.

## How it works
**Fields, by group** (the class docstring documents each one):
- Surfaces and text: `background`, `plot_background`, `grid`, `axis_line`, `text`,
  `muted_text`, `overlay_background` / `overlay_border` (legend boxes and call-outs
  drawn over the data).
- Data marks: `colorway` (series colours in order), `other` (the "Other" bucket of
  `top_n`), `dimmed` (what `highlight` pushes back), `neutral` (marks with no series
  identity: outliers, connectors, an "overall" line), `mark_outline`, `reference` and
  `reference_secondary` (e.g. mean and median lines), `positive` / `negative`.
- Scales: `cell_text`, `diverging_scale` and `sequential_scale` (safe under
  `cell_text`), `marker_diverging_scale` (markers carry no text), `severity_scale`.
- Fonts: `font_family`, `font_size`, `title_font_size`, `subtitle_font_size`,
  `label_font_size`.
- Layout in px: `title_top_px`, `title_gap_px` (the title block), `row_gap_px`,
  `col_gap_px`, `row_plot_px` (subplot grids, read by
  [`grid_geometry`](../_layout.md)).

The legacy module's second qualitative palette (`_CATEGORICAL_COLORS`) has no field:
one `colorway` serves every series, so a category gets the same colour in every
chart. `color_map` and a longer `colorway` cover the rest.

**Type aliases drive validation.** Fields are declared as `Color`, `ColorScale`
(`tuple[tuple[float, Color], ...]`), `tuple[Color, ...]`, `Px` (int) or `str`.
`__post_init__` walks `dataclasses.fields()` and checks each value by its declared
type, so a new field is validated as soon as it is declared:
- colours must parse (see [the package page](index.md))
- the colorway must be non-empty
- a scale needs at least two stops, starts at position 0, ends at 1, and its
  positions strictly rise
- px values are positive `int` (`bool` rejected)
- `font_family` is a non-empty string

Lists given for the colorway or a scale are stored as tuples (`object.__setattr__`
inside the frozen class), so users can write natural lists and the theme stays
hashable.

**`build_template(theme)`** is cached with `functools.cache` (a theme is immutable
and hashable). The template is built from scratch, not layered on `plotly_dark` or
`plotly_white`, so every value comes from a `Theme` field. It sets:
- colorway, both backgrounds, the base font
- title font, subtitle font and title placement: centred, top-anchored at
  `title_top_px` from the figure's top edge (`yref="container"`), so the title never
  moves with the figure height
- cartesian and polar axes (grid, zero line, axis line, muted tick labels), colour
  bars, the default sequential/diverging scales
- annotation text colour, and `reference` as the default line colour of shapes, so
  `add_hline` / `add_vline` draw reference lines in the theme's colour
- heatmap defaults: `sequential_scale` and cell labels in `cell_text`

Margins and figure size are not in the template: they depend on the figure, and are
set by [`apply_base_layout`](../_layout.md).

## Invariants
- A `Theme` that exists is valid: there is no way to build one that fails later in a
  plot.
- A `Theme` is immutable and hashable; customising means
  `dataclasses.replace(theme, ...)`, which re-runs validation.
- Every field has a declared type with a validation rule; a field of any other type
  raises `TypeError` the moment a built-in is constructed, i.e. on import.
- Assigning a template to a figure copies it, so the cached template is never changed
  through a figure.

## Pitfalls
- **Plotly base defaults apply where the template is silent.** Because the template
  does not inherit `plotly_dark`, parts it doesn't set (3-D scenes, ternary, geo
  maps) fall back to Plotly's white-background defaults. A plot that starts using one
  of them adds its styling to `build_template` first.
- **`make_subplots` writes `font.size=16` on every subplot title**, which beats the
  template. Their colour still comes from the template.
- **A new field needs a value in both built-ins** (there are no defaults), and if it
  is a text colour or a label-carrying scale, a line in the contrast tests.
- **Validation compares declared types by identity** (`field.type is Color`). Annotate
  new fields with the aliases, not with `str`, or a colour field is validated as a
  font name.
