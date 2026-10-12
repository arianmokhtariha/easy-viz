# 0002: Parameter-rich functions

**Status:** accepted · **Date:** 2026-10-11

## Context
The product promise is that a plot goes from simple to advanced by changing arguments,
not by writing code. Every option that isn't a parameter becomes 10–20 lines of Plotly
in the user's notebook.

## Decision
Functions expose every useful option of their chart as a typed, documented parameter.
20–40 parameters per function is expected.

Complexity is controlled by four things, not by limiting the count:
- **Defaults:** the bare call works and looks finished.
- **Keyword-only options:** they can grow without breaking callers.
- **Conflict validation:** incompatible options raise; no option is silently ignored.
- **The glossary:** one name per concept across all functions.

## Alternatives
- **Few parameters plus `**kwargs` passed through to Plotly:** undocumented, untyped,
  and pushes users back into Plotly's own vocabulary.
- **Builder or method chaining (`ev.bar(df).sort().top(10)`):** more ways to do the
  same thing and harder to document. Rejected in favour of one call.

## Consequences
- **Easier:** discoverable through autocomplete and docstrings, and one call per chart.
- **Harder:**
  - every new option needs conflict checks and tests
  - docstrings are long
  - the number of option combinations grows, so testing must target conflicts
    deliberately
- Removing a parameter for being "one too many" is not a valid reason. Merging two
  parameters that duplicate each other is.
