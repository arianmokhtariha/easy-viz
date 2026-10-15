# Guide: gallery (`gallery/`)

The gallery is the complete, visual guide to every public plotting function, and the
source of every image in the README. It must always match the current code: a plot
change isn't done until its notebook shows the new behaviour.

## Structure
```
gallery/
  README.md                index: one row per function → notebook, and what it reveals
  meet_the_data.ipynb      introduces the business and its tables (no plot function)
  _template.ipynb          the notebook template: copy it to start a notebook
  <family>/<function>.ipynb   one notebook per public plot function; families mirror plots/
  data/
    generate.py            builds the showcase dataset; fixed seed, so it's deterministic
    *.csv                  generated tables (committed; never edited by hand)
    INSIGHTS.md            the answer key: every planted pattern, and how to reveal it
```

## Notebook template
`_template.ipynb` holds these sections with authoring notes; copy it into the family
folder, fill it, and delete the notes. Sections in this order:
1. **The question:** what this plot answers, and which planted pattern it will
   uncover.
2. **Bare call:** the one-line default.
3. **Parameter tour:** every keyword option, grouped by purpose (data and
   aggregation, ordering, labels, colour, reference lines, layout, theme). For each
   one: what it does, what changes visibly, and a figure. Defaults and accepted values
   are quoted from the docstring, never restated differently.
4. **Combinations:** realistic scenarios using several options together.
5. **Limits:** every conflicting option pair shown with its real error message, plus
   the edge cases the docstring promises (empty data, a single category, ...).
6. **Insight story:** step by step from the default chart to the chart that exposes
   the planted pattern. This is the product value made visible.
7. **Escape hatch:** one edit on the returned figure, using a trace role.

## Rules
- **One notebook per public plot function.** Adding a function adds its notebook and
  its row in `gallery/README.md`.
- **Every keyword parameter appears in its notebook.** *(enforced by a test)*
- **Changing a plot function** (a new option, a changed default, new behaviour)
  updates its notebook in the same PR and re-executes it.
- **Notebooks are committed executed**, with outputs that display on GitHub as static
  images, and run top to bottom without errors. *(executed in CI)*
- **Data comes only from `gallery/data/`, through SQL**
  ([decision 0009](../docs/decisions/0009-gallery-sql-duckdb.md)): the template's
  setup cell makes every CSV a DuckDB view, and each chart starts from a query whose
  result goes straight into the plot. Vary what is passed across notebooks (the
  query result itself, `.pl()`, `.df()`, `.to_arrow_table()`), never reshape
  between query and plot.
- **Only the public API:** `import easy_viz as ev`, never internal modules.
- **Every planted pattern is documented in `INSIGHTS.md`** and asserted by a test.
  Changing the generator must not silently remove a story.
- **README images are generated** by the gallery build script from cells tagged
  `readme:<name>` (one figure per tagged cell; the image is
  `docs/images/readme/<name>.png`). They are never made or edited by hand.
- **Edit notebooks with the NotebookEdit tool**, cell by cell, never by rewriting the
  `.ipynb` JSON by hand. NotebookEdit can't set cell metadata, so add a tag with
  `nbformat` (read the notebook, append to the cell's `metadata.tags`, write it).
- **Execute notebooks only with the build script** (root guide, "Commands"): it is
  the only path that writes their outputs, with the static PNG GitHub needs, and it
  extracts every image to `.review/` for the visual review loop. CI only checks that
  every notebook still runs (`pytest --nbmake`), it writes nothing.
- **Narrative style:** written for a data analyst, not a developer. Each section opens
  with one or two sentences on what to look at and why it matters.
