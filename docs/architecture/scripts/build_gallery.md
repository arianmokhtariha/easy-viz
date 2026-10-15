# Gallery build

Covers: scripts/build_gallery.py

## Responsibilities
Turn the gallery's notebooks into their committed, executed form in one command:
regenerate the showcase data, execute every notebook, give every figure both a static
and an interactive form, export the README images, and save every figure to
`.review/` for the visual review loop. It is the only thing that writes notebook
outputs or README images ([gallery guide](../../../gallery/CLAUDE.md)).

## How it works
```
uv run --isolated --python 3.14 python scripts/build_gallery.py [--only NAME ...]
```
The gallery runs on Python 3.14 because DuckDB, which the notebooks query the data
with, has no 3.15 wheel yet ([decision 0009](../../decisions/0009-gallery-sql-duckdb.md)).
`--isolated` builds a throwaway 3.14 environment and leaves the project's `.venv`
alone. On an environment without DuckDB, the script stops at once with that command.

Steps, in order:
1. **Select:** every `gallery/**/*.ipynb` except files starting with `_` (the
   template) and checkpoint copies; `--only` keeps the named stems. Notebook stems
   must be unique, because `--only` and `.review/` name notebooks by stem.
2. **Regenerate the data:** runs `gallery/data/generate.py` in a subprocess
   ([generator](../gallery/data/generate.md)).
3. **Execute:** each notebook runs top to bottom with nbclient in a fresh kernel of
   the script's own interpreter, with the notebook's folder as working directory.
   `PLOTLY_RENDERER=plotly_mimetype` is set in the environment the kernel inherits,
   so every figure output carries the figure as Plotly JSON
   (`application/vnd.plotly.v1+json`): the interactive form.
4. **Check tags:** a cell tagged `readme:<name>` must hold exactly one figure, and
   names must be valid (`^[a-z0-9][a-z0-9_-]*$`) and unique. Any misuse stops the run
   before anything is written.
5. **Render:** every figure of every executed notebook goes through one
   `easy_viz.save_many` batch at scale 1 (Chrome starts once). Each PNG is embedded
   as `image/png` in the same output, next to the JSON: GitHub shows the PNG, Jupyter
   and a docs site the interactive figure. Each is also saved as
   `.review/<notebook>/cell-NN.png` (`cell-NN-K` for several figures in one cell; NN
   is the cell's index, markdown cells included). A notebook's review folder is
   emptied first.
6. **README images:** a second `save_many` batch writes the tagged figures to
   `docs/images/readme/<name>.png` at the configured export scale. A full run (no
   `--only`, no failed notebook) deletes PNGs there that no tag produced.
7. **Write:** each executed notebook is written back as nbformat v4 with LF line
   endings, without timing metadata or the kernel's exact Python version.

A notebook whose cell fails (or times out, or kills the kernel) is reported and not
written; the others still are, and the script exits with an error.

The logic sits in pure functions (`select_notebooks`, `figure_outputs`,
`readme_exports`, `embed_png`, `stale_readme_images`, `drop_volatile_metadata`)
tested without a kernel or Chrome in `tests/scripts/test_build_gallery.py`; `main`
does the I/O. `tests/test_gallery.py` reuses the tag parsing and notebook discovery,
so the build and the checks can't disagree on what a gallery notebook or a tag is.

## Invariants
- Rebuilding unchanged notebooks on the same machine produces byte-identical files.
- Every figure output of a committed notebook carries both the Plotly JSON and a PNG
  (checked by `tests/test_gallery.py`).
- `docs/images/readme/` holds exactly the images the tags produce, after a full run.

## Pitfalls
- **Never execute notebooks another way before committing.** Jupyter or nbmake
  output has no PNG, so GitHub would show the figure as nothing.
- **Plotly reads `PLOTLY_RENDERER` once, at import.** It must be set before the
  kernel starts, which is why the script sets it in its own environment.
- **The kernel is always the running interpreter's own**, never a `python3`
  kernelspec found on the machine, which could point at a Python without DuckDB.
- **README images are re-rendered from the figure JSON**, not copied from the
  embedded PNG, so they get the export scale (2× by default) while notebooks stay
  small.
- **`.review/` is gitignored** and only reflects the last build of each notebook.
