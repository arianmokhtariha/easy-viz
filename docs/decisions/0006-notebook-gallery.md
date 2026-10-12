# 0006: Executed notebooks as the gallery and showcase

**Status:** accepted · **Date:** 2026-10-12

## Context
The product promise ("simple to advanced by changing arguments") has to be visible:
- every function, every parameter, realistic combinations and limits
- on a fictional dataset with hidden patterns that the features uncover

The README also needs images that show this value. Examples that aren't executed
drift away from the code.

## Decision
- **Format:** one Jupyter notebook per public plot function in `gallery/<family>/`,
  following a fixed template. All notebooks use one fictional, deterministic dataset
  with documented planted patterns.
- **Execution:** notebooks are committed executed, run in CI, and rendered by the docs
  site (myst-nb).
- **README images** are exported from tagged notebook cells by a build script.

## Alternatives
- **sphinx-gallery scripts:** they execute too, but GitHub doesn't display them as
  notebooks, and they'd duplicate any notebook-based guide.
- **A single large notebook:** unmanageable at 25+ functions, and too slow to open and
  run.
- **Examples inside the README:** too long for 25+ functions, and not executed.

## Consequences
- **Easier:**
  - one source for the visual guide, the docs pages and the README images
  - stale examples fail CI
  - a test enforces that every parameter is demonstrated
- **Harder:**
  - committed outputs make notebooks large in git and need re-executing after every
    plot change
  - the dataset generator must keep every planted pattern intact
