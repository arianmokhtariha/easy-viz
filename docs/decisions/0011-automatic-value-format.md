# 0011: Values are formatted automatically unless a format is given

**Status:** accepted · **Date:** 2026-10-15

## Context
Plots write values on bars, in hover text and on reference lines. The legacy module
formatted them with `".3g"` by default, and the conventions fix `value_format` as a
Python format spec (never d3-format, which analysts don't know).

The first visual review of `bar_plot` showed what `".3g"` does to business numbers:
revenue of 862,289 becomes `8.62e+05`. Python format specs have no thousands
suffixes (d3's `s` has no Python equivalent), so no single spec reads well for both
`862,289` and `0.42`.

## Decision
Proposed during the visual review of `bar_plot`; approved by the product manager on
2026-10-15, as the default for every plot.
- **`value_format=None` is the default** and means automatic: three significant
  digits, with k, M, B or T for thousands, millions, billions and trillions
  (`862k`, `1.08M`, `-2.5k`, `0.42`). Implemented once, in
  `_layout.format_value`, for every plot.
- **A given `value_format` is a Python format spec**, as before, applied to labels,
  hover and reference lines. When it means the same in d3-format (a sign, thousands
  separators, a precision, and an `f`, `%` or `e` type), it also formats the value
  axis and the colour bar, so the axis reads like the labels.

## Alternatives
- **Keep `".3g"`:** scientific notation on every business-sized number.
- **Default to `",.0f"`:** right for money totals, wrong for rates (`0`) and means
  (`80`, losing the decimals that matter).
- **Accept d3-format strings:** gives `~s` for free, but the conventions chose Python
  specs on purpose, and mixing the two makes `.3g`-style specs ambiguous.

## Consequences
- **Easier:** the bare call reads well for totals, rates and means alike.
- **Harder:**
  - a third behaviour to explain beside the two format languages
  - the automatic format writes `B` for billions; d3's own axis ticks write `G`.
    Axes keep Plotly's tick format unless the user's spec is a shared one
  - changes the legacy default; listed in the changelog
