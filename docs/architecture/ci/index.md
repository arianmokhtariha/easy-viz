# Continuous integration

Covers: .github/workflows/ci.yml, .github/workflows/release.yml

## Responsibilities
Run the project's checks (lint, formatting, strict type check, tests) automatically,
so no change reaches `main` without proving it works on every Python version
[decision 0005](../../decisions/0005-python-version-policy.md) supports, and publish
each new version to PyPI ([decision 0013](../../decisions/0013-automated-releases.md)).
The workflow files are the single list of the exact commands and versions.

## How it works
Two GitHub Actions workflows: `CI` (`ci.yml`) checks the code; `Release`
(`release.yml`) checks the package and publishes it.

### `CI`
Two jobs, `checks` and `lowest`.

**`checks`** runs on the newest locked versions:
- **Triggers:** every pull request, and every push to `main` (which includes merges).
- **Matrix:** the job runs once per supported Python version, as parallel jobs named
  `Python <version>`. `fail-fast: false` lets every version finish, so one failure
  doesn't hide another.
- **Setup:** `astral-sh/setup-uv` installs uv and the matrix's Python, and caches
  downloaded packages between runs. `uv sync --all-extras` then installs the exact
  versions in `uv.lock`: the library, its optional extras and the default `dev` group.
- **Checks:** one step per command, so the log shows which check failed.
- **Gallery:** a last step executes every gallery notebook (`pytest --nbmake
  gallery/`), so a notebook that no longer runs with the code fails the build. It
  only checks; committed outputs come from the gallery build script. The step is
  skipped on Python 3.15, because the notebooks need DuckDB, which has no 3.15 wheel
  yet ([decision 0009](../../decisions/0009-gallery-sql-duckdb.md)).
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

### `Release`
Runs on every pull request, and after every `CI` run on `main` (a `workflow_run`
trigger). Only a successful `CI` run of a push to this repository's `main` goes on:
a failed run, or a pull request from a branch that happens to be named `main`, is
skipped. That run checks out the commit `CI` tested, not `main`'s latest commit.
Three jobs, each with only the permissions it needs:
- **`build`** (`Build and check the package`), on every run:
  - reads the version (`uv version --short`) and decides whether this run releases:
    only a final version (digits and dots), only after `CI` on `main`, and only
    when the tag `v<version>` doesn't exist yet. The log prints the
    decision and its reason.
  - for a final version, writes the release text with
    [`scripts/release_notes.py`](../scripts/release_notes.md), which fails on a
    missing or malformed changelog entry. This runs on pull requests too, so a
    release pull request without notes fails before it is merged.
  - builds the wheel and the source distribution (`uv build`), checks their
    metadata and that the README renders on PyPI (`twine check --strict`), then
    installs the wheel alone in a fresh environment, imports `easy_viz` and compares
    the installed version with `pyproject.toml`.
  - uploads `dist/` (and the notes, when releasing) as artifacts for the next jobs.
- **`publish`** (`Publish to PyPI`), only when `build` decided to release: uploads
  `dist/` with `pypa/gh-action-pypi-publish` through trusted publishing. It runs in
  the GitHub environment `pypi` with `id-token: write`, the permission to request
  the short-lived token PyPI checks. The upload includes attestations of where each
  file was built. `skip-existing` makes a repeated upload a no-op, so a run that
  uploaded but failed before tagging recovers with "Re-run all jobs".
- **`github-release`** (`Create the GitHub release`), after a successful publish:
  `gh release create v<version>` at the built commit, with the release text and the
  two files attached. This creates the tag, which marks the version as released
  for every later run.

Runs on `main` are never cancelled, so a publish is never interrupted.

The release pull request itself (version number, changelog entry) is prepared by
the `/release` skill, `.claude/skills/release/SKILL.md`, which only the product
manager invokes. It reads the changes since the last tag, picks the version by the
rules of decision 0013, writes the entry, and follows the run above to PyPI.

## Invariants
- The matrix lists exactly the versions decision 0005 supports. Changing that policy
  changes the matrix in the same PR.
- Every runtime lower bound installs from a ready-built package (wheel) on the
  oldest supported Python (3.13) and passes the tests there; the `lowest` job
  enforces both. Newer Pythons are not checked at the bounds: an old release often
  has no wheel for them, and their resolvers pick newer releases anyway.
- A version is uploaded to PyPI at most once: the tag check skips released
  versions, and `skip-existing` skips files PyPI already has.
- Nothing reaches PyPI that `CI` didn't test and `build` didn't check, on the same
  commit.
- CI runs the same commands as local development. A check added to the project's
  definition of done is added to the workflow in the same PR.

## Pitfalls
- **A `workflow_run` trigger only works from `main`.** GitHub reads `release.yml`
  from the default branch for it, so a pull request can test the build job but
  not the release path; the first run after merging is the real test.
- **PyPI's trusted publisher names `release.yml` and the environment `pypi`.**
  Renaming either makes the upload fail with an "invalid publisher" error until the
  publisher is updated in the PyPI project's settings.
- **Release notes stay outside `dist/`.** The publish action uploads every file in
  `dist/`, and PyPI rejects anything that isn't a distribution.
- **A tag pushed by hand as `v<version>` blocks that version's release**: the
  workflow reads the tag as "already released". Tags are created only by the
  workflow.
- **`uv.lock` records the project's own version.** A version change must update
  the lock too (`uv version <new>` does both), or every `UV_LOCKED` job fails.
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
- **The gallery step's 3.15 skip is temporary.** When DuckDB ships a 3.15 wheel,
  remove the step's `if:` together with the dependency marker (decision 0009).
- **The `docs` dependency group is not installed.** A future docs-build step must add
  `--group docs` to the install step.
