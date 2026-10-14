# Global configuration

Covers: src/easy_viz/config.py

## Responsibilities
Hold the few output defaults that every plot and every export shares, so a user
changes them once instead of passing them to each call:
- `width`: figure width in px for plots called with `width=None` (default 1400)
- `export_scale`: resolution multiplier for [`save` and `save_many`](export.md)
  to raster formats (default 2.0); `svg` and `pdf` are written at true size

The legacy module repeated `width=1400` in every function and `scale=2` in its save
helper; this replaces both.

## How it works
- `Config` is a frozen dataclass. `__post_init__` validates every field, so an invalid
  `Config` cannot exist.
- One module-level `Config` holds the active defaults. `get_config()` returns it;
  `set_config(*, width=None, export_scale=None)` builds a new `Config` from the old
  values plus the given ones, and only then replaces the active one. `None` means
  "keep the current value".
- Consumers call `get_config()` at call time, never at import time or as a default
  argument value, so a later `set_config()` takes effect.

## Invariants
- The active `Config` is always valid. `set_config` constructs and validates the new
  object before swapping it in, so a rejected call (for example a valid width with a
  negative scale) changes nothing, not even the valid half.
- `Config` is immutable: the only way to change a default is `set_config`.
- `width` is a positive `int`; `export_scale` is a positive, finite `int` or `float`.
  `bool` is rejected for both. The checks are `_validate.check_positive_int` and
  `check_range`, so every invalid value raises `ValueError` in the standard format.
- Messages follow the conventions format and name the parameter and the value.

## Pitfalls
- **`bool` is a subclass of `int` in Python**, so `width=True` would pass an
  `isinstance(..., int)` check and mean 1 px. The checks reject it explicitly.
- **`None` in `set_config` means "keep", so a default cannot be reset by passing
  `None`.** Pass the value (`set_config(width=1400)`); the defaults are the dataclass
  field defaults, `Config().width`.
- **The state is process-wide.** Tests that call `set_config` restore it afterwards
  (a fixture in each test module), or they leak into other tests.
- **Why the export scale lives here and not in the theme:** it is a property of the
  output (how many pixels a file gets), not of the look. A theme switch should not
  change file resolution, and a report author sets the resolution once for the whole
  project next to the width.
