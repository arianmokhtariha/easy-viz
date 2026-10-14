# 0007: Global defaults are immutable values, and Plotly's own defaults are untouched

**Status:** accepted · **Date:** 2026-10-14

## Context
Two things are set once for a whole notebook or report rather than on every call:
- the **theme** (every colour, font and size), with a per-call `theme=` override
- the **output defaults** (figure width, export resolution)

Users must be able to customise both: a brand palette, a narrower width. And easy-viz
lives inside the user's Python session next to their own Plotly figures, which it
must not change.

## Decision
- **A theme is a frozen `Theme` dataclass; the defaults are a frozen `Config`.**
  `set_theme()` and `set_config()` replace the active value whole; `get_theme()` and
  `get_config()` read it. Customising means copying a built-in with
  `dataclasses.replace(ev.get_theme("light"), colorway=(...))`.
- **Every value is validated when it is created**, so an invalid theme or config can
  never become active, and a rejected `set_*` call changes nothing.
- **Fields are named by role** (`reference`, `dimmed`, `other`, `cell_text`), never by
  colour, so a plot asks for what a mark means and each theme decides how it looks.
- **The built-in themes are registered as Plotly templates** (`easy_viz_dark`,
  `easy_viz_light`) for users' own figures, but easy-viz **never changes
  `pio.templates.default`**. Each easy-viz figure carries its template explicitly.
- **Styling lives in the theme, output defaults in the config.** The default width
  and export scale are properties of the output, not of the look: switching theme
  doesn't change file resolution.

## Alternatives
- **Mutable settings objects (`ev.options.width = 1100`, `theme.colorway.append(...)`):**
  an assignment can't be validated as a whole, and a half-applied change can leave an
  invalid state. Mutation also breaks caching the Plotly template per theme.
- **Plain Plotly templates as the theme format:** Plotly templates have no notion of
  roles such as "dimmed" or "reference", so plots would hard-code those colours, and
  contrast rules couldn't be checked.
- **Setting `pio.templates.default` in `set_theme`:** convenient, but it restyles
  every other Plotly figure in the user's session, which a library must not do.
- **Default width in the theme:** couples the look to the output size; rejected for
  the reason above.

## Consequences
- **Easier:**
  - a theme is hashable, so its Plotly template is built once and cached
  - built-in themes are checked by tests for WCAG contrast and for parity (every
    field set in both)
  - users' own figures and easy-viz figures never interfere
- **Harder:**
  - a new visual role means a new `Theme` field and a value in every built-in theme
  - `None` in `set_config` means "keep", so a default is reset by passing its value,
    not `None`
  - global state is process-wide: tests that change it must restore it
