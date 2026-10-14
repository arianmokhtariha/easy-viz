# Continuous integration

Covers: .github/workflows/ci.yml

## Responsibilities
Run the project's checks (lint, formatting, strict type check, tests) automatically,
so no change reaches `main` without proving it works on every Python version
[decision 0005](../../decisions/0005-python-version-policy.md) supports. The workflow
file is the single list of the exact commands and versions.

## How it works
One GitHub Actions workflow, `CI`, with two jobs, `checks` and `lowest`.

**`checks`** runs on the newest locked versions:
- **Triggers:** every pull request, and every push to `main` (which includes merges).
- **Matrix:** the job runs once per supported Python version, as parallel jobs named
  `Python <version>`. `fail-fast: false` lets every version finish, so one failure
  doesn't hide another.
- **Setup:** `astral-sh/setup-uv` installs uv and the matrix's Python, and caches
  downloaded packages between runs. `uv sync --all-extras` then installs the exact
  versions in `uv.lock`: the library, its optional extras and the default `dev` group.
- **Checks:** one step per command, so the log shows which check failed.
- **Safety:**
  - the workflow's token is read-only (`contents: read`)
  - actions are pinned to commit SHAs, with the release tag in a comment
  - `UV_LOCKED=1` makes every uv command fail when `uv.lock` doesn't match
    `pyproject.toml`, instead of silently resolving new versions
- **Cancelling:** a newer push to a pull request cancels its older run. Runs on `main`
  are never cancelled, so every commit there gets a result.

**`lowest`** (`Lowest dependencies (Python 3.13)`) tests the promise the lower bounds
in `pyproject.toml` make: that easy-viz works with those versions.
- It installs the locked environment, then reinstalls every runtime dependency and
  extra at the lowest version its bound allows (`uv pip install -r pyproject.toml
  --all-extras --resolution lowest-direct --upgrade --only-binary :all:`). Dev tools
  stay locked: they never reach users.
- A step then compares each installed runtime dependency with its lower bound and
  fails on any difference, and prints the versions under test.
- The tests run with `uv run --no-sync`, which keeps the downgraded versions.
- It runs on Python 3.13, the oldest supported version, where old releases are
  likeliest to have packages.

## Invariants
- The matrix lists exactly the versions decision 0005 supports. Changing that policy
  changes the matrix in the same PR.
- Every runtime lower bound is a version that installs from a ready-built package
  (wheel) on every supported Python, and passes the tests. The `lowest` job enforces
  both.
- CI runs the same commands as local development. A check added to the project's
  definition of done is added to the workflow in the same PR.

## Pitfalls
- **`.python-version` pins the newest Python for local development.** The matrix
  overrides it through setup-uv's `python-version` input (it sets `UV_PYTHON`).
  Without that input, every job would silently run on the same version.
- **Raising `requires-python` without updating the matrix** fails the dropped
  version's job at install time (uv finds no valid environment). Lowering it without
  adding a job leaves the new minimum untested, silently.
- **mypy always checks against the minimum version** (`python_version` in
  `pyproject.toml`), whatever interpreter runs it. Running it in each job still
  catches third-party packages whose installed versions differ between Pythons.
- **Chrome is preinstalled on GitHub's Ubuntu runners**, so tests marked `export`
  find it and run in CI instead of skipping as they do on a machine without Chrome.
- **Pinned SHAs don't update themselves.** Bumping an action means replacing both the
  SHA and its version comment.
- **`uv pip install` keeps versions that already satisfy a bound.** Without
  `--upgrade`, the newer locked versions stay, and the job would test nothing new;
  the bound check exists so this can never pass silently.
- **A bound with no wheel for the oldest Python is not installable for users.** pip
  would try to compile it from source. With `--only-binary`, uv skips such a version
  and the bound check fails instead, naming the dependency. This is how the numpy and
  scipy bounds were found too low (their first Python 3.13 wheels are 2.1 and
  1.14.1).
- **The `docs` dependency group is not installed.** A future docs-build step must add
  `--group docs` to the install step.
