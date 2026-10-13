# Plan 0001: Foundation

**Status:** approved

## Goal
Build the shared machinery every plot function depends on, before porting any plot.
When this is done, porting a function from `custom_plots.py` only means writing plot
logic: validation, data handling, layout, theming and tagging are already solved.

## Scope
| Module | Responsibility | Ported from `custom_plots.py` |
|---|---|---|
| `_data.py` | Accept any narwhals-supported frame (eager or lazy). Check that required columns exist and have the right type. Normalise types: decimals → float, dates → datetime, nullable/Arrow dtypes. | `_is_categorical_col`, the column checks repeated in each function |
| `_validate.py` | Raise for conflicting option pairs and invalid values, using the message format in `docs/conventions.md` | the inline `raise ValueError` checks |
| `_layout.py` | `grid_geometry()` (pixel-budget subplot spacing), `apply_base_layout()` (title, subtitle, sizing), `escape_text()` (the `$` fix) | `_grid_geometry`, `_apply_base_layout` |
| `_meta.py` | `tag(trace, role, group)` and the allowed roles | new |
| `_typing.py` | Shared aliases: `Orientation`, `Agg`, `ArrayLike`, ... | `ArrayLike` |
| `_warnings.py` | `EasyVizWarning` (so users can filter easy-viz warnings) | new |
| `theme/` | Frozen `Theme` dataclass → registered Plotly template. `set_theme()`, `get_theme()`, per-call override. Built-in `dark` (today's house style) and `light`. | `PALETTE`, `_DARK_BG` and the other colour constants, `_CORR_DIVERGING`, `SEQ_BLUE` |
| `config.py` | Global defaults (width, export scale) | the repeated `width=1400` |
| `export.py` | `save(fig, path)`, `save_many(figs, dir)` built on `pio.write_images` | the `save()` helper in `conclusions.ipynb` |

## Tests delivered with it
Repository-wide checks:
- **`test_contract.py`:** a registry of public functions, each with a minimal valid
  call, run on pandas, polars and pyarrow input. Empty until the first plot lands.
- **`test_layering.py`:**
  - `stats/` never imports `plotly` or `plots/`
  - `theme/` never imports `plots/`
- **`test_styling_literals.py`:** no hex colours, font names or pixel sizes in
  `plots/`.
- **`test_knowledge_base.py`:**
  - relative links in `docs/` resolve
  - `Covers:` paths in architecture docs exist
  - plans have a valid `Status`
  - no tracked file links to the local agent guides
  - when the local guides are present, they match their index (skipped in CI and in
    fresh clones, where they don't exist)

Plus unit tests for every module above.

## Acceptance criteria
- All checks pass.
- The architecture docs exist at their mirrored paths:
  - `docs/architecture/index.md` (system overview)
  - `docs/architecture/easy_viz/index.md` (the package and its small internal
    modules)
  - `docs/architecture/easy_viz/theme/index.md`
  - `docs/architecture/tests/index.md`
  - a `<module>.md` for any module over the size threshold

  Each one has a `Covers:` line and these sections: Responsibilities, How it works,
  Invariants, Pitfalls.
- This plan file is deleted in the same PR.
- The two built-in themes are rendered as PNG samples and approved by the product
  manager.

## Next plans
- 0002: showcase dataset and gallery.
- 0003: port `line_plot` and `bar_plot`, the two most-used functions. They prove the
  foundation on real plots and complete the first gallery notebooks.
