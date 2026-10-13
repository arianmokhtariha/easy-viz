# Warnings

Covers: src/easy_viz/_warnings.py

## Responsibilities
Give every non-fatal issue easy-viz reports one warning class, `EasyVizWarning`
(public), so users can filter easy-viz warnings without silencing other libraries:
nulls dropped, ISO-date columns that can't become a time axis, an option with no
effect in the current mode, and, once plots exist, categories folded into "Other".

## How it works
- `EasyVizWarning` subclasses `UserWarning`, so warnings show by default.
- `warn(message)` issues it with `skip_file_prefixes` set to the package directory
  (Python 3.12+). Python skips every frame inside easy-viz when it picks the line the
  warning is reported at, so the warning names the line of the user's own call,
  however deep inside the package it was raised.
- Message text is built by `_validate.message`, in the conventions format
  `"<function>: <what happened>. <how to change it>."`.

## Invariants
- Every user-facing warning goes through `warn()` (never `warnings.warn` directly),
  so the class and the call-site line are always right.
- The reported file is the caller's (tested).

## Pitfalls
- **`stacklevel` is the wrong tool here.** It counts frames, so it breaks as soon as
  the warning is raised one helper deeper. `skip_file_prefixes` doesn't depend on
  depth.
- **Python shows each distinct warning once per call site by default.** Running the
  same cell twice in a notebook may show the warning only the first time; that is the
  `warnings` module's default filter, not a bug.
