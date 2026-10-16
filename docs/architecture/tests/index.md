# Tests

Covers: tests/conftest.py, tests/test_import.py, tests/test_meta.py, tests/test_warnings.py, tests/test_config.py, tests/test_data.py, tests/test_validate.py, tests/test_layout.py, tests/test_export.py, tests/theme/test_theme.py, tests/theme/test_registry.py, tests/theme/test_color.py, tests/test_contract.py, tests/test_layering.py, tests/test_styling_literals.py, tests/test_knowledge_base.py, tests/test_packaging.py, tests/test_gallery.py, tests/test_showcase_data.py, tests/scripts/test_build_gallery.py, tests/stats/test_intervals.py, tests/plots/test_comparison.py, tests/plots/test_timeseries.py

## Responsibilities
Prove that the library is correct and that the repository stays consistent with
itself. There are two kinds of test:
- **Unit tests** (`test_data.py`, `test_validate.py`, `test_layout.py`,
  `theme/test_registry.py`, ...) mirror the module they test, one file per module.
- **Repository-wide checks** sit at the top level and test rules that no single module
  owns: the public-function contract, the layering between sub-packages, the absence of
  styling literals in the plot functions, the agreement between documentation and
  code, and the contents of the built package.

Tests for a developer script live in `tests/scripts/`, mirroring `scripts/`. A script
is not importable as a package, so `load_script()` in `conftest.py` loads it by path;
the tests exercise its pure functions and small file helpers, writing only inside
pytest's `tmp_path`; kernels and Chrome stay out of them.

`conftest.py` holds the shared `make_frame` fixture. It builds the same small table as
pandas, polars and pyarrow, and runs each test that uses it once per backend, which is
how the library proves it accepts any dataframe library
([decision 0004](../../decisions/0004-narwhals-dataframe-agnostic.md)).

## How it works
Every repository-wide check is built the same way: a pure function that takes its
input (a source string, or the repository root) and returns a list of problems, plus a
test that runs it on the real repository, plus a few tests that run it on tiny
synthetic input to prove the rule fails when it should. The rule is therefore tested,
and an empty directory does not make the real check pass for the wrong reason. Every
failure message names the file, the rule and the fix.

### `test_contract.py`
Holds `REGISTRY`: one `ContractCase` (function, sample data, minimal call) per public
plot function (today `bar_plot` and `line_plot`). Each case is run on all three
backends and must:
- return a `go.Figure`;
- leave the input table unchanged (compared through narwhals: schema and content, with
  NaN equal to NaN);
- give every trace a role from `ROLES` in `meta`;
- carry the active theme's template;
- show the `title` it was given.

A separate test lists the callables in `easy_viz.__all__` that are defined under
`easy_viz.plots` and fails for any that is not registered, so a plot cannot ship
unchecked. Were the registry ever empty, the per-function tests would skip with that
reason instead of passing silently. The checks themselves are tested against small fake
functions that break each rule.

### `test_layering.py`
Parses every module of `stats/` and `theme/` with `ast` and collects all imports, in
every form: `import x`, `from x import y` (which may import the submodule `x.y`),
relative imports (resolved against the importing module), and imports inside functions
or `if TYPE_CHECKING:` blocks. `stats/` may not import `plotly` or `easy_viz.plots`;
`theme/` may not import `easy_viz.plots`. The reason is the dependency direction:
plots depend on stats and theme, never the reverse, so computation stays testable
without Plotly and themes stay usable without any plot.

### `test_styling_literals.py`
Scans `src/easy_viz/plots/` for literals that belong to the theme or to `config`, so
that restyling happens in one place:
- hex colours and `rgb(`/`rgba(`/`hsl(` functions in any string;
- colour names given to colour keywords, font families and font stacks;
- pixel sizes: numbers given to size keywords (`font_size`, `marker_size`, margins,
  `width`/`height` as integers above 1, `size` inside a font or marker spec, ...) and
  CSS lengths such as `12px`.

The exact definition, with what is deliberately not detected, is in the test module's
docstring. The scan reads the syntax tree, so comments and docstrings never trigger
it. A table of positive and negative snippets exercises the detector, so the rule is
proven to fail on each kind of literal, not only to pass on today's code.

### `test_knowledge_base.py`
Turns the placement rules for the documentation into checks. On the real repository:
- every relative link in `docs/` and the top-level Markdown files resolves;
- every architecture doc has a title, a `Covers:` line whose paths exist, and the
  four sections in order; only an `index.md` may cover nothing (the overview, or a
  directory whose modules all have their own docs);
- every code file in `src/`, `scripts/` and `gallery/` is named in the `Covers:` line
  of exactly one architecture doc, located at the file's mirrored path, and every
  directory with code has an `index.md`;
- a module that defines an object of `easy_viz.__all__`, or has more than 150 lines,
  has its own `<module>.md`;
- every directory under `docs/architecture/` mirrors an existing source directory
  (`easy_viz` is `src/easy_viz`, `ci` is `.github`, other names are top-level
  directories);
- every architecture doc is linked from the `index.md` of its directory, hence
  reachable from the overview;
- every plan has a valid `Status`;
- the agent guides on disk and the table in the root guide agree, and the links and
  imports inside the guides resolve.

### `test_gallery.py`
Checks that the gallery matches the code ([gallery](../gallery/index.md)):
- every public plot function (found with `public_plot_functions()` in `conftest.py`,
  shared with the contract test) has `gallery/<family>/<name>.ipynb`, where family is
  the last part of its module, and a link to it in `gallery/README.md`;
- every keyword-only parameter is passed to the function itself in a code cell of
  its notebook (found by parsing the code, so prose, plain assignments and Plotly
  calls such as `fig.update_layout(title=...)` don't count);
- every gallery notebook is linked from `gallery/README.md`;
- every gallery notebook is committed executed: each code cell ran, none errored, and
  every Plotly figure output also carries a PNG (without it GitHub shows nothing);
- README images: every link into `docs/images/readme/` resolves, every `readme:<name>`
  tag has its image, every image has its tag, and tag names are unique.

It reuses the build script's notebook discovery and tag parsing (loaded with
`load_script`) and the link helpers of `test_knowledge_base.py`, so the build and the
checks can't disagree. While no plot function exists, the two per-function checks
skip with that reason.

### `test_showcase_data.py`
Keeps the showcase dataset honest ([showcase data](../gallery/data/index.md)):
- parses the summary table of `gallery/data/INSIGHTS.md` and measures every row's
  metric on the committed CSV files; a documented value that no longer matches, a
  documented metric without a measurement, or a measurement without a row fails;
- checks that the tables agree: daily totals equal the orders, customer aggregates
  equal their orders, keys resolve;
- rebuilds the tables with the generator and compares them with the committed files
  (floats within a small tolerance, because numpy's math can differ in the last bit
  between CPUs), which proves the CSVs were never edited by hand.

### `scripts/test_build_gallery.py`
Tests the gallery build script's pure functions on synthetic notebooks: notebook
selection, figure naming, `readme:` tag validation, PNG embedding and stale-image
detection. No kernel or Chrome is needed.

### `test_packaging.py`
Builds the source distribution and the wheel with `uv build` into a temporary
directory and lists their contents. Both must hold the package and no agent file
(`CLAUDE.md`, `CLAUDE.local.md`, anything under `.claude/`). The guides are tracked
and some sit inside `src/easy_viz/`, so only the build backend's `source-exclude`
keeps them out of the library
([decision 0008](../../decisions/0008-tracked-agent-guides.md)). A separate test
asserts that guides exist in the source tree, so the build checks cannot pass for
want of anything to exclude. Skips when `uv` is not on `PATH`.

## Invariants
- A check that depends on a directory that does not exist yet passes vacuously and
  starts enforcing as soon as files appear. The contract test is the exception: it
  skips with a reason while its registry is empty.
- Tests assert on figure data and on source text, never on pixels.
- Every failure message names the file, the broken rule and how to fix it, because
  the reader acting on it has no other context.
- A new public plot function is registered in `REGISTRY` in the same change that
  exports it.

## Pitfalls
- **Link anchors (`#section`) are not checked.** GitHub and Sphinx build heading
  anchors by different rules, so any check would reject links that work in one of
  them. Only the file part of a link is verified.
- **Link targets are compared with exact letter case.** Windows and macOS ignore case,
  the Linux CI runner does not; a link that opens locally can still fail in CI.
- **Coverage of code files excludes `tests/`.** Its doc needs valid `Covers:` paths but
  is not required to list every test file. When a test file is added, add it here too.
- **Public names are found through `obj.__module__`.** A function whose `__module__`
  was rewritten (to hide where it is defined) is not recognised as living in its
  file, and escapes the own-doc rule.
- **The styling scan cannot tell a colour name from a column name for a bare
  `color=`**: in the plot functions `color` is the column parameter. Colour names are
  caught everywhere else (`line_color`, `bgcolor`, inside `font`/`marker`/`line`).
- **Fixtures run on three backends.** A test using `make_frame` runs three times; keep
  such tests small.
