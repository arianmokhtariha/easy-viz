# Plot functions (`plots/`)

Covers: src/easy_viz/plots/__init__.py

## Responsibilities
The public plotting functions, one module per chart family (`comparison`,
`distribution`, `relationship`, `timeseries`, `business`, `ml`; see the
[plots guide](../../../../src/easy_viz/plots/CLAUDE.md)). Each function turns a
query result into a finished `go.Figure` and does nothing else: tables go through
[`_data`](../_data.md), numbers come from [`stats/`](../stats/index.md), colours and
sizes from the [theme](../theme/index.md), the title block from
[`_layout`](../_layout.md).

| Module | Doc | Functions |
|---|---|---|
| `comparison.py` | [comparison.md](comparison.md) | `bar_plot` |

## How it works
Every function follows the same stages, in this order, so a reader who knows one
knows them all:
1. **Option checks** that need no data (choices, conflicts, ranges), before any
   table work. Messages come from `_validate.message`.
2. **Table intake** through `_data`: `load`, `require_numeric`, `parse_time`,
   `drop_nulls`, `aggregate`.
3. **Shaping**: whatever the chart needs from the data (ordering, cuts, statistics
   from `stats/`).
4. **Drawing**: traces tagged with their role (`_meta.tag`), coloured from theme
   roles, then `_layout.apply_base_layout`.

## Invariants
- No styling literals: no hex colours, font names or pixel sizes (tested by
  `tests/test_styling_literals.py`). Ratios and fractions that aren't styling (an
  aspect ratio, a hatch density) are named module constants with their reason.
- Every public function is in `easy_viz.__all__`, registered in the contract test,
  and has a gallery notebook.

## Pitfalls
- **The package `__init__` stays empty.** Functions are exported from
  `easy_viz/__init__.py`, the only public surface.
