# Guide: public plotting functions (`src/easy_viz/plots/`)

The public function contract, glossary, trace roles and Plotly constraints are in
`docs/conventions.md` (loaded with `src/easy_viz/CLAUDE.md`). Every function here
follows them.

## Rules
- **No styling literals:** no hex colours, font names or pixel sizes. They come from
  the theme or `config`. *(enforced by a test that scans this directory)*
- **One module per family:** `distribution`, `relationship`, `comparison`,
  `timeseries`, `business`, `ml`. A function that fits none of them is a reason to
  propose a new family, not to stretch an existing one.
- **Numbers come from `stats/`.** A plot function validates, prepares data, calls
  stats, builds traces and applies layout. It doesn't compute statistics inline.
- **The best chart wins, native or custom.** Before designing or porting a plot,
  look up what current Plotly offers for its chart type through Context7 (root
  guide, "Library documentation"): trace types and attributes, layout, hover,
  annotations. Then pick whatever gives the most professional, best-looking and
  most readable chart:
  - a native Plotly feature, when it delivers that
  - a custom construction (own traces, shapes, annotations), when the native
    feature looks worse, is too limited, or makes the data harder to interpret

  The visual review loop judges the result. Name the choice and the reason in the
  report's *Why this way*.

## Porting from `custom_plots.py`
The original lives at `legacy/custom_plots.py` (local, gitignored). The report charts
it couldn't produce are in `legacy/conclusions.ipynb`.
- Read the original before porting. Its behaviour is the specification unless
  `docs/conventions.md` changes it (e.g. retired parameter names). Its Plotly code is
  not: it predates current Plotly, so check each technique against the current
  documentation.
- Keep its statistical behaviour exactly: CI methods, seriation, edge-case handling.
  Any intended difference is listed under *Product impact* in the report.

## Adding or porting a plot (definition of done for this directory)
1. Move or write its computation in `stats/`, with tests.
2. Write the function to the contract and glossary.
3. Export it in `easy_viz.__all__` and register it in the contract-test registry.
4. Add or update its gallery notebook and index row (see `gallery/CLAUDE.md`).
5. Run the visual review loop (root guide) on its notebook.
6. Run the knowledge sync loop (root guide).
