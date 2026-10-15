# Guide: public plotting functions (`src/easy_viz/plots/`)

The public function contract, glossary, trace roles and Plotly constraints are in
`docs/conventions.md` (loaded with `src/easy_viz/CLAUDE.md`). Every function here
follows them.

## Rules
- **No styling literals:** no hex colours, font names or pixel sizes. They come from
  the theme or `config`. *(enforced by a test that scans this directory)*
- **One function per chart concept** (product principle 8). Before adding or
  porting a function, check the existing functions and the rest of
  `legacy/custom_plots.py` for any that draw the same kind of chart. Where one
  function can do both jobs with nothing lost, propose merging them, with the
  options that carry the difference. A merged-away function is not ported
  separately.
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
- **Porting is also redesign, one function at a time.** Judge the original against
  `docs/product.md` while porting it. List the improvements and missing features
  found, each with a recommendation, in the plan or under *Decisions needed*,
  including which overlapping legacy functions it should absorb. The
  product manager approves which ones the port builds (they shape the public API).
  The rest go to `ROADMAP.md`, so nothing found is lost.

## Adding or porting a plot (definition of done for this directory)
1. Move or write its computation in `stats/`, with tests.
2. Write the function to the contract and glossary.
3. Export it in `easy_viz.__all__` and register it in the contract-test registry.
4. Add or update its gallery notebook and index row (see `gallery/CLAUDE.md`).
   Every scenario its options serve needs a story in the showcase data. Where no
   pattern in `gallery/data/INSIGHTS.md` shows one, add the pattern to the generator
   with its `INSIGHTS.md` section and summary rows in the same PR. The existing
   patterns must still measure at their documented values.
5. Run the visual review loop (root guide) on its notebook.
6. Run the knowledge sync loop (root guide).
