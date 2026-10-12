# 0005: Python version policy

**Status:** accepted · **Date:** 2026-10-11

## Context
Python 3.15 was released on 2026-10-09:
- lazy imports (PEP 810)
- `frozendict` (PEP 814)
- comprehension unpacking
- a faster Windows interpreter
- an upgraded JIT
- the Tachyon sampling profiler

A library runs on the user's own Python, so `requires-python` sets the oldest version
a user may have. numpy 2.5 and scipy 1.18 already require 3.12 or newer. SPEC 0 (the
support schedule the scientific Python ecosystem follows) drops 3.12 in Q4 2026.

## Decision
- **Support Python ≥ 3.13.** Develop on 3.15.
- **Test** on 3.13, 3.14 and 3.15.
- **No 3.14+-only syntax or built-ins** in the source. mypy checks against 3.13.
- **Heavy imports use `__lazy_modules__`:** lazy on 3.15, a normal import on older
  versions.

## Alternatives
- **≥ 3.15:**
  - would allow the new syntax everywhere
  - but locks out nearly every current user, including the owner's own 3.13
    analytics environment
- **≥ 3.12:** about to fall outside the ecosystem's support window, with nothing
  gained.

## Consequences
- **Easier:**
  - users on 3.15 get its speed and lazy imports automatically
  - development uses the newest profiler and runtime
- **Harder:** `frozendict`, the `lazy` keyword and other new features wait until 3.15
  becomes the minimum. Revisit following SPEC 0.
