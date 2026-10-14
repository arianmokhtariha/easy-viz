# Option validation (`_validate`)

Covers: src/easy_viz/_validate.py

## Responsibilities
Check plot options at runtime (users don't run a type checker) and build every error
and warning text in the one format of
[the conventions](../../conventions.md#error-and-warning-messages):
`"<function>: <what is wrong>. <how to fix it>."`. Table checks live in
[`_data`](_data.md), which uses the same formatter. It replaces the inline
`raise ValueError(...)` checks of the legacy module, whose wording varied by function.

## How it works
- `message(func, problem, fix)` is the formatter; everything else calls it. It adds
  the final period unless `fix` already ends in `.`, `?` or `!`.
- `setting(param, value)` renders an option as the user wrote it, `param=repr(value)`,
  so strings show their quotes (`orientation='sideways'`).
- `is_set(value)` defines when an option counts as set: anything except `None`,
  `False` and empty values (`""`, `[]`, `()`). `0` counts as set, because it is a
  value the user chose; range checks reject it where it isn't allowed.
- Checks (each raises `ValueError`):
  - `check_choice(func, param, value, choices)`: `value` must be one of the values of
    a `Literal` alias from `_typing` (read with `typing.get_args`, so the allowed
    values are written once, in the type).
  - `check_conflict(func, /, **options)`: at most one of the keyword options may be
    set; the message names the first two that are, with their values.
  - `check_requires(func, param, value, *, needs, needs_value)`: a set option whose
    companion option is unset.
  - `check_positive_int(func, param, value)`: counts such as `top_n`.
  - `check_range(func, param, value, *, low, high, include_low, include_high)`:
    numbers within bounds, e.g. a CI level strictly between 0 and 1. The message
    spells the bounds in words ("greater than 0 and less than 1").
- `warn_no_effect(func, param, value, when, fix="Remove it")` issues an
  `EasyVizWarning` (through `_warnings.warn`) for an option ignored in the current
  mode. The caller decides when the option differs from its default.

## Invariants
- Every error and warning text in the package is built by `message`.
- Values in messages use `repr`; arbitrary values are typed `object`, never `Any`.
- The checks have no side effects besides raising (or, for `warn_no_effect`,
  warning), so they can run first, before any table work.

## Pitfalls
- **`bool` is an `int`** (and an `Integral` and a `Real`) in Python, so `top_n=True`
  would pass a naive number check. Number checks reject `bool` first.
- **NaN fails every comparison**, so a check written as "raise if `value <= 0`"
  would accept it, and infinity passes it. `check_range` converts to `float` and
  rejects every non-finite value. That's why `config`, `export` and `theme` use
  these helpers instead of their own checks.
- **`check_choice` needs the alias, not a value list.** Passing a non-`Literal` type
  raises `TypeError` (a programming error), because `get_args` would return nothing
  and every value would be rejected.
- **`check_conflict` takes keywords**, so a check can't mix up which name goes with
  which value; `func` is positional-only so no option name can clash with it.
