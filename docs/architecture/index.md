# Architecture

Covers: nothing directly; this page is the overview that links to every doc.

How easy-viz is built today. Every doc here describes only what is on `main`, and
mirrors a directory of the repository.

## Responsibilities
This overview is the entry point: it names the parts of the repository, shows how
they depend on each other, and links to the doc that owns each one.

## How it works
| Part | Directory | Doc |
|---|---|---|
| Library package | `src/easy_viz/` | [easy_viz/index.md](easy_viz/index.md) |
| Themes | `src/easy_viz/theme/` | [easy_viz/theme/index.md](easy_viz/theme/index.md) |
| Tests and repository-wide checks | `tests/` | [tests/index.md](tests/index.md) |
| Developer scripts | `scripts/` | [scripts/index.md](scripts/index.md) |
| Gallery and showcase data | `gallery/` | [gallery/index.md](gallery/index.md) |
| Continuous integration | `.github/` | [ci/index.md](ci/index.md) |

**Layers of the library.** The package currently holds the foundation; plot functions
(`plots/`) and their statistics (`stats/`) arrive with the first ported plots.

```
user table ──► _data ──► (stats/) ──► traces ──► _layout ──► go.Figure
                 ▲                      ▲           ▲
             _validate               _meta        theme/, config
```
- `_data` turns any table into a validated narwhals frame (decision
  [0004](../decisions/0004-narwhals-dataframe-agnostic.md)).
- `theme/` and `config` hold every styling value and output default; nothing else
  in the package writes a colour, a font or a size.
- `_layout` finishes the figure; `export` writes it to image files.
- Import rules between layers are enforced by `tests/test_layering.py`.

## Invariants
- Every architecture doc is linked from this page or from an `index.md` below it.
- Every code file in `src/`, `scripts/` and `gallery/` is owned by exactly one doc at
  its mirrored path (tested by `tests/test_knowledge_base.py`).

## Pitfalls
- **Docs describe `main`, not plans.** Work not built yet lives in
  [`docs/plans/`](../plans/), never here.
