# The `easy_viz` package

Covers: src/easy_viz/__init__.py, src/easy_viz/_meta.py, src/easy_viz/_typing.py

## Responsibilities
The library itself: the plot functions ([plots/](plots/index.md)), the statistics
behind them ([stats/](stats/index.md)), and the foundation every plot is built on.

The foundation's job: when a plot is ported, its function only holds plot logic.
Accepting any table, validating options, normalising SQL types, laying out the title
and subplots, theming, tagging traces and exporting are already solved here, the same
way for every function (product principle 7, "Consistency is a feature").

## How it works
**Public API.** `__init__.py` only re-exports names and lists them in `__all__`, which
is exactly the public API: `bar_plot`, `EasyVizWarning`, `Theme`, `get_theme`,
`set_theme`, `get_config`, `set_config`, `save`, `save_many`. Modules whose names start with `_`
are internal and can change freely. `py.typed` marks the package as typed, so type
checkers in users' projects read its annotations.

**Modules.** Small ones are described on this page; the others have their own doc.

| Module | Doc | Role |
|---|---|---|
| `_data.py` | [_data.md](_data.md) | the only module that touches user tables: intake, column and dtype checks, SQL type normalisation, ISO-date parsing, null dropping, aggregation, exit to numpy |
| `_validate.py` | [_validate.md](_validate.md) | runtime option checks, and the one formatter for every error and warning message |
| `_layout.py` | [_layout.md](_layout.md) | `escape_text` (the `$` fix), `grid_geometry` (pixel-budget subplot spacing), `apply_base_layout` (template, title block, size), `auto_height`, value formatting (`format_value`, `d3_format`), `text_px` |
| `_warnings.py` | [_warnings.md](_warnings.md) | `EasyVizWarning`, and `warn()`, which points the warning at the user's call |
| `_meta.py` | this page | trace roles and `tag()` |
| `_typing.py` | this page | type aliases shared by the package |
| `config.py` | [config.md](config.md) | global output defaults: figure width, export scale |
| `export.py` | [export.md](export.md) | `save` and `save_many`: static image export through kaleido and Chrome |
| `theme/` | [theme/index.md](theme/index.md) | the `Theme` dataclass, the built-in `dark` and `light` themes, global and per-call theme, Plotly templates |
| `plots/` | [plots/index.md](plots/index.md) | the public plot functions, one module per family |
| `stats/` | [stats/index.md](stats/index.md) | statistics behind the plots (confidence intervals) |

**How a plot function uses them**, in order:
1. Check its options with `_validate` (choices, conflicts, ranges).
2. Turn `df` into a validated, normalised narwhals frame with `_data` (`load`,
   `require_numeric`, `parse_time`, `drop_nulls`, `aggregate`).
3. Pick its theme with `theme.registry.resolve_theme`.
4. Get its numbers from `stats/`, build traces coloured from theme roles, and tag each
   with `_meta.tag`.
5. Finish with `_layout.apply_base_layout` and return the plain `go.Figure`
   ([decision 0003](../../decisions/0003-return-plain-figure.md)).

**`_meta.py`: trace roles.** `Role` is a `Literal` of the roles listed in
[conventions](../../conventions.md#trace-roles), and `ROLES` is the same set at
runtime. `tag(trace, role, group=None)` sets
`trace.meta = {"role": role, "group": group}` and returns the trace, so it can wrap a
constructor. `group` names the series (e.g. the `color` category), so a user can
target one series' trendline. An unknown role raises: it can only be a bug in
easy-viz.

**`_typing.py`: shared aliases.** `FrameLike` (any table narwhals accepts, eager or
lazy), `Orientation` and `Agg`. They are plain assignments, not `type` statements, so
`typing.get_args` returns their allowed values at runtime: `_validate.check_choice`
reads valid options from the same alias the signature uses.

## Invariants
- `__all__` is exactly the set of public names in `__init__.py` (tested).
- Layering: `stats/` never imports `plotly` or `plots/`; `theme/` never imports
  `plots/` (tested).
- Every user table goes through `_data`. Every option check that more than one
  module needs (choices, conflicts, positive whole numbers, ranges) lives in
  `_validate`, and every message follows its format. Every warning is an
  `EasyVizWarning` issued through `_warnings.warn`.
- `ROLES` and the trace-role table in the conventions name the same roles (tested).
- Global state is limited to the active theme and the active config. Both are
  immutable values, replaced whole by `set_theme` / `set_config`
  ([decision 0007](../../decisions/0007-immutable-global-defaults.md)).

## Pitfalls
- **The `type` statement hides allowed values.** `typing.get_args` returns nothing
  for an alias made with `type X = Literal[...]`. Aliases used for runtime checks stay
  plain assignments.
- **Some `narwhals.typing` names are strings in old narwhals.** In narwhals 2.0,
  `IntoSeries` is the string `'NativeSeries'`, so `X | IntoSeries` raises
  `TypeError` when evaluated, at import for a plain assignment. Check a new alias
  that uses narwhals types against the lowest supported narwhals (the `lowest` CI
  job runs the tests there).
- **`tag` replaces `meta`.** It overwrites anything already in `trace.meta`; a plot
  that needs extra metadata adds it after tagging.
