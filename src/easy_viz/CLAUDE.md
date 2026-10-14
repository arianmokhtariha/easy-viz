# Guide: library code (`src/easy_viz/`)

Covers all library code. Subdirectories add their own guides; this one applies to all
of them.

@../../docs/conventions.md

## Structure
- **Layering:** `plots/` may import `stats/`, `theme/` and the `_`-prefixed internal
  modules. `stats/` never imports `plotly` or `plots/`. `theme/` never imports
  `plots/`. *(enforced by an import test)*
- **The public API is exactly `easy_viz.__all__`.** `__init__.py` holds only
  re-exports and `__all__`. Underscore-prefixed modules are internal and can change
  freely.
- **No copied logic between modules.** Behaviour two places need lives in one
  internal module.
- **No new abstraction** (base class, registry, plugin layer, decorator framework)
  unless at least two existing call sites need it now.
- **All dataframe input goes through `_data`.** No other module converts, checks or
  normalises user tables.
- **User-facing warnings use `EasyVizWarning`** (from `_warnings`), so users can
  filter them.

## API evolution
- **New behaviour is additive:** a new keyword option whose default reproduces the
  old behaviour.
- **These are breaking changes:** changing an existing default, renaming or removing
  a public name or parameter. After 1.0 they need a `DeprecationWarning` for one
  minor version first.
- **An option is never silently ignored.** If it conflicts with another or has no
  effect in the current mode, raise (conflict) or warn (no effect).

## Compatibility
- Code runs on Python 3.13 (mypy checks against 3.13). No 3.14+-only syntax or
  built-ins: e.g. `frozendict`, the `lazy` import keyword, `*` unpacking in
  comprehensions, `t""` strings.
- Heavy imports (scipy) go in `__lazy_modules__`: lazy on 3.15, a normal import on
  older versions.

## Verification
Changes that can alter how a figure looks go through the visual review loop in the
root guide.
