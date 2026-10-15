# Guide: tests (`tests/`)

## Layout
- **Mirrors `src/easy_viz/`:** tests for `stats/regression.py` live in
  `tests/stats/test_regression.py`.
- **Developer scripts are tested in `tests/scripts/`**, loaded with `load_script()`
  from `conftest.py`. Test their pure functions; keep kernels, Chrome and file
  writes out of the tests.
- **Repository-wide checks** live at the top level:
  - `test_contract.py`
  - `test_layering.py`
  - `test_styling_literals.py`
  - `test_knowledge_base.py`
  - `test_packaging.py`
  - `test_gallery.py`
  - `test_showcase_data.py`

## Rules
- **A bug fix lands with a test that failed before the fix.**
- **Assert on figure data** (`fig.to_dict()`, trace properties), not on pixels. Pixel
  output differs between machines.
- **The contract test** (`test_contract.py`):
  - runs every registered public function with a minimal valid call on pandas,
    polars **and** pyarrow input
  - asserts that it returns `go.Figure`, leaves the input unchanged, gives every
    trace a role, applies the theme and uses `title`
- **Every conflicting option pair** has a test that expects the error and checks its
  message names both options.
- **Stats functions are tested against a reference:**
  - scipy or numpy where an equivalent exists
  - otherwise a small hand-computed case written in the test
  - plus the edge cases their docstring promises
- **Snapshot tests (syrupy)** for only a few key calls. They break on Plotly
  upgrades, so each one must earn its place.
- **Static-export tests** carry `@pytest.mark.export` and skip when Chrome is
  missing.
- **Backends come from the `make_frame` fixture** in `conftest.py` (one run each on
  pandas, polars, pyarrow). `tests/` is not a package: import its types with
  `from conftest import MakeFrame`, never `from tests.conftest ...`.
- **Global state is restored:** a test that calls `set_theme` or `set_config` uses a
  yield fixture that restores the previous value, so tests stay order-independent.

## Repository-wide checks (what they enforce)
- `test_layering.py`: the import rules in `src/easy_viz/CLAUDE.md`.
- `test_styling_literals.py`: no styling literals in `src/easy_viz/plots/`.
- `test_gallery.py`:
  - every public plot function has a notebook and a row in `gallery/README.md`
  - every keyword parameter appears in its notebook
  - every notebook is linked from the index and committed executed, with a PNG
    next to every interactive figure
  - README images match their `readme:` tags, and links to them resolve
- `test_showcase_data.py`: every pattern in `gallery/data/INSIGHTS.md` is present at
  its documented strength.
- **Notebook execution:** `pytest --nbmake gallery/` runs every notebook (in CI).
- `test_knowledge_base.py`:
  - every relative link in `docs/` resolves
  - every path in an architecture doc's `Covers:` line exists
  - every code file in `src/`, `scripts/` and `gallery/` is covered by exactly one
    architecture doc, located at its mirrored path
  - a module with public names or more than 150 lines has its own doc
  - every directory under `docs/architecture/` mirrors an existing source directory
    (no orphans)
  - every architecture doc is reachable from `docs/architecture/index.md`
  - every plan has a valid `Status`
  - every CLAUDE.md is listed in the root guide table, every listed one exists, and
    links inside the guides resolve
- `test_packaging.py`: the built wheel and source distribution contain the library
  and no agent file (CLAUDE.md, `.claude/`)
