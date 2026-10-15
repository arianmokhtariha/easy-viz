# Scripts

Covers: nothing directly; every script here is long enough to have its own doc.

## Responsibilities
Developer tools run by hand from the repository root with `uv run python scripts/...`.
They are never imported by the library or the tests.

## How it works
| Script | Doc | What it does |
|---|---|---|
| `build_gallery.py` | [build_gallery.md](build_gallery.md) | regenerates the showcase data, executes the gallery notebooks, renders their figures and the README images |
| `render_theme_samples.py` | [render_theme_samples.md](render_theme_samples.md) | renders a sample sheet per built-in theme for visual review |

## Invariants
- Scripts import from `easy_viz` (including internal modules). The library never
  imports from `scripts/`; tests load a script by path (`load_script` in
  `tests/conftest.py`) to test its pure functions.
- Output for review goes to `.review/` (gitignored). Only `build_gallery.py` writes
  tracked files: the gallery notebooks, the showcase data and
  `docs/images/readme/`, all generated, never edited by hand.

## Pitfalls
- **Run from the project environment** (`uv run`), so the scripts use the same
  easy-viz and Plotly versions as the tests. The exception is `build_gallery.py`,
  which runs in an isolated Python 3.14 environment built from the same lock file
  ([decision 0009](../../decisions/0009-gallery-sql-duckdb.md)).
