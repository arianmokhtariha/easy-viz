# Colour maths

Covers: src/easy_viz/theme/_color.py

## Responsibilities
Read the colour strings a `Theme` accepts and compute WCAG contrast, so theme
validation and the contrast tests share one implementation. Internal: nothing here is
public.

## How it works
- `parse_color(text) -> RGBA` reads the three accepted forms: hex (`#1a2b3c`, `#abc`),
  `rgb(r, g, b)` and `rgba(r, g, b, a)`. Every part must be a plain decimal
  (`26`, `0.6`, `.6`), with only spaces around it; one bad part rejects the whole
  colour. Anything else raises `ValueError`. `is_color(text)` is the boolean form used
  by validation.
- `contrast_ratio(foreground, background)` is the WCAG 2.x ratio (1 to 21) from
  relative luminance. A translucent foreground is first blended onto the background,
  because the blend is what the reader sees; a translucent background raises, because
  the result would depend on what lies behind it.
- `with_alpha(color, alpha)` returns the colour as `rgba(...)` with a new opacity,
  for translucent fills (confidence bands, radar areas) derived from a series colour.
  `alpha` is checked with `_validate.check_range` (0 to 1, no `bool`, no NaN).

## Invariants
- Every colour `parse_color` accepts is one Plotly accepts too, so a `Theme` that
  passes validation never fails later when its template is built.
- Messages use the `_validate.message` format.

## Pitfalls
- **`float()` is more permissive than Plotly.** It reads `1e2`, `-0` and `+5`, which
  Plotly's colour validator rejects. Channels are matched against a plain-decimal
  pattern before conversion, mirroring Plotly's own `[\d.]+`.
- **CSS colour names (`"white"`) are rejected on purpose.** Contrast maths needs the
  channels, and a 148-name table would be a second source of truth.
