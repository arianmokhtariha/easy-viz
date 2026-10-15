# Showcase dataset

Covers: nothing directly; the only module here, generate.py, has its own doc.

## Responsibilities
`gallery/data/` holds the data every gallery notebook queries: the fictional retailer
Fernway, as seven CSV tables with ten planted patterns. The product manager chose an
online retailer with a membership (2026-10-12): it can hold every planted pattern
naturally, and it differs from food delivery, which the owner's Delivr portfolio
project already covers.

| File | Role |
|---|---|
| `generate.py` | builds every table from one seed: [generate.md](generate.md) |
| `*.csv` | the generated tables, committed so notebooks and CI need no build step |
| `INSIGHTS.md` | the answer key: the business, the tables, and every pattern with its measured strength ([open](../../../../gallery/data/INSIGHTS.md)) |

## How it works
```
generate.py ──► *.csv ──► gallery notebooks (SQL over the CSV files)
                  │
INSIGHTS.md ──────┴──► tests/test_showcase_data.py
```
The test reads the summary table of `INSIGHTS.md` (one row per metric: ID, pattern,
table, metric, documented value), measures each ID on the committed CSV files with
the function registered for it, and fails when a value drifts beyond its tolerance or
when a documented ID has no measurement (or the reverse). It also checks that the
tables agree with each other, and that the files equal a fresh `build_tables()` run.

## Invariants
- The CSV files are only ever written by `generate.py`.
- Every planted pattern has at least one row in the summary table of `INSIGHTS.md`,
  and every row is measured by the test. A story can't disappear silently.
- Documented values are the values measured on the committed files, rounded to 2
  decimals.

## Pitfalls
- **Changing the generator changes the answer key.** Re-run the script, run
  `pytest tests/test_showcase_data.py`, and update every documented value (and the
  numbers quoted in the prose of `INSIGHTS.md`) that moved.
- **Notebooks read the CSV files as they are.** A column rename here breaks every
  notebook query that uses it.
