# Gallery

Covers: nothing directly; the gallery's only code, the data generator, is documented in data/.

## Responsibilities
`gallery/` is the visual guide to easy-viz and the source of the README images
([decision 0006](../../decisions/0006-notebook-gallery.md)). It holds:
- `README.md`: the index, one row per plot function
- `meet_the_data.ipynb`: introduces the showcase business and its tables
- `_template.ipynb`: the notebook template (never executed by the build)
- `<family>/<function>.ipynb`: one notebook per public plot function, in a folder per
  plot family
- `data/`: the showcase dataset and its answer key ([data/index.md](data/index.md))

The rules for writing notebooks are in the [gallery guide](../../../gallery/CLAUDE.md).

## How it works
```
data/generate.py ──► data/*.csv ──► notebooks (SQL through DuckDB) ──► go.Figure outputs
                                                                          │
           scripts/build_gallery.py: execute, embed PNGs, export ◄────────┘
                    │                    │                     │
            notebooks (committed)   .review/<nb>/        docs/images/readme/
```
- **Data in:** every notebook starts with the same setup cell, which registers each
  CSV in `data/` as a DuckDB view named after its table. Each chart starts from a SQL
  query whose result (polars, pandas or Arrow) goes straight into an easy-viz call
  ([decision 0009](../../decisions/0009-gallery-sql-duckdb.md)).
- **Outputs:** the [build script](../scripts/build_gallery.md) executes the notebooks
  and stores every figure twice in its output: as Plotly JSON (interactive, for
  Jupyter and a future docs site) and as a PNG (what GitHub displays). Cells tagged
  `readme:<name>` also become `docs/images/readme/<name>.png`.
- **Checks:**
  - `tests/test_gallery.py` checks that every plot function has its notebook and
    index row, every keyword parameter appears in its notebook, notebooks are
    committed executed with PNGs, and README images match their tags
  - `tests/test_showcase_data.py` checks the planted patterns
  - CI executes every notebook (`pytest --nbmake gallery/`)

## Invariants
- A notebook's committed outputs come only from the build script.
- Notebook file names are unique across the gallery: the build's `--only` option and
  `.review/` name notebooks by file name.
- Notebooks use only the public API (`import easy_viz as ev`) and only the data in
  `data/`.

## Pitfalls
- **Notebooks run in their own folder.** The setup cell finds the data at `../data`
  from a family folder and at `data` from `gallery/` itself. A notebook moved to
  another depth needs that path changed.
- **DuckDB's `.arrow()` returns a stream in DuckDB 1.5** (a `RecordBatchReader`),
  which easy-viz does not accept. Use `.to_arrow_table()` for a pyarrow table.
- **DuckDB infers each CSV column's type** on every query: dates become `DATE`,
  empty fields `NULL`. A generator change that alters how a column is written (e.g. a
  date with a time part) changes what the notebooks receive.
- **Gallery notebooks need Python 3.14 for now** (no DuckDB wheel for 3.15); see the
  build command in the [build script doc](../scripts/build_gallery.md).
