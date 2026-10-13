# Tests

Covers: tests/conftest.py, tests/test_import.py, tests/test_meta.py, tests/test_warnings.py, tests/test_config.py, tests/test_data.py, tests/test_validate.py, tests/test_layout.py, tests/test_export.py, tests/theme/test_theme.py, tests/test_contract.py, tests/test_layering.py, tests/test_styling_literals.py, tests/test_knowledge_base.py

## Responsibilities
Prove that the library is correct and that the repository stays consistent with
itself. There are two kinds of test:
- **Unit tests** (`test_data.py`, `test_validate.py`, `test_layout.py`,
  `theme/test_theme.py`, ...) mirror the module they test, one file per module.
- **Repository-wide checks** sit at the top level and test rules that no single module
  owns: the public-function contract, the layering between sub-packages, the absence of
  styling literals in the plot functions, and the agreement between documentation and
  code.

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
plot function, empty until the first plot is ported. Each case is run on all three
backends and must:
- return a `go.Figure`;
- leave the input table unchanged (compared through narwhals: schema and content, with
  NaN equal to NaN);
- give every trace a role from `ROLES` in `meta`;
- carry the active theme's template;
- show the `title` it was given.

A separate test lists the callables in `easy_viz.__all__` that are defined under
`easy_viz.plots` and fails for any that is not registered, so a plot cannot ship
unchecked. While the registry is empty, the per-function tests skip with that reason
instead of passing silently. The checks themselves are tested against small fake
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
it. A table of positive and negative snippets exercises the detector, because the real
directory is empty today.

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
- no tracked file links to or names the path of an agent guide;
- only when the root guide exists (never in CI): the guides on disk and the table in
  the root guide agree, and the links and imports inside the guides resolve.

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
- **The guide-reference check is stricter in prose than in configuration.** Excluding
  guides is legitimate in configuration (a `**/` glob in the build settings, a bare
  name in the ignore file), so only paths with a directory part and links fail there;
  in Markdown, any mention fails. The check never inspects its own test file.
- **Local-only checks skip in CI.** The guides are gitignored, so a failure in them
  appears only on a machine that has them; run the whole file before opening a pull
  request.
- **Public names are found through `obj.__module__`.** A function whose `__module__`
  was rewritten (to hide where it is defined) is not recognised as living in its
  file, and escapes the own-doc rule.
- **The styling scan cannot tell a colour name from a column name for a bare
  `color=`**: in the plot functions `color` is the column parameter. Colour names are
  caught everywhere else (`line_color`, `bgcolor`, inside `font`/`marker`/`line`).
- **Fixtures run on three backends.** A test using `make_frame` runs three times; keep
  such tests small.
