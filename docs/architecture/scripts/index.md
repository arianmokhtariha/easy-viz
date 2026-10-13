# Scripts

Covers: nothing directly; every script here is long enough to have its own doc.

## Responsibilities
Developer tools run by hand from the repository root with `uv run python scripts/...`.
They are never imported by the library or the tests.

## How it works
| Script | Doc | What it does |
|---|---|---|
| `render_theme_samples.py` | [render_theme_samples.md](render_theme_samples.md) | renders a sample sheet per built-in theme for visual review |

## Invariants
- Scripts import from `easy_viz` (including internal modules); nothing imports from
  `scripts/`.
- Output for review goes to `.review/` (gitignored), never into tracked paths.

## Pitfalls
- **Run from the project environment** (`uv run`), so the scripts use the same
  easy-viz and Plotly versions as the tests.
