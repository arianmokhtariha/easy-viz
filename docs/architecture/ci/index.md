# Continuous integration

Covers: .github/workflows/ci.yml

## Responsibilities
Run the project's checks automatically, so no change reaches `main` without proving
it works on every supported Python version:
- `ruff check .`: lint
- `ruff format --check .`: formatting
- `mypy src`: strict type check
- `pytest`: tests

## How it works
One GitHub Actions workflow, `CI`, with one job (`checks`):
- **Triggers:** every pull request, and every push to `main` (which includes merges).
- **Matrix:** the job runs once per Python version, 3.13, 3.14 and 3.15, as separate
  parallel jobs named `Python 3.13` and so on. These are the versions
  [decision 0005](../../decisions/0005-python-version-policy.md) promises.
  `fail-fast: false` lets every version finish, so one failure doesn't hide another.
- **Setup:** `astral-sh/setup-uv` installs uv and the matrix's Python, and caches
  downloaded packages between runs. `uv sync --locked --all-extras --group dev` then
  installs the exact versions in `uv.lock`, plus the `export` extra and the dev tools.
- **Checks:** the four commands above, each as its own step so the log shows which one
  failed.
- **Safety:** the workflow's token is read-only (`contents: read`), and a newer push to
  the same branch cancels the older run (`concurrency`).

## Invariants
- The matrix lists exactly the versions decision 0005 supports, from
  `requires-python` in `pyproject.toml` up to the newest. Changing that policy changes
  the matrix in the same PR.
- CI runs the same commands as local development. A check added to the project's
  definition of done is added here in the same PR.
- Dependencies come from `uv.lock` (`--locked`): a `pyproject.toml` change without a
  matching `uv lock` fails CI instead of silently resolving new versions.

## Pitfalls
- **`.python-version` pins 3.15 for local development.** The matrix overrides it
  through setup-uv's `python-version` input (it sets `UV_PYTHON`). Without that input,
  all three jobs would silently run on 3.15.
- **mypy always checks against 3.13** (`python_version` in `pyproject.toml`), whatever
  interpreter runs it. Running it in each job still catches third-party packages whose
  installed versions differ between Pythons, and costs seconds.
- **The `docs` dependency group is not installed.** A future docs-build step must add
  `--group docs` to the install step.
- **A cancelled run is not a failure.** When `concurrency` cancels an outdated run,
  GitHub shows it as cancelled; only the latest run's result counts.
