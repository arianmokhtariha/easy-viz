# Architecture

Covers: nothing directly; this page is the overview that links to every doc.

How easy-viz is built today. Every doc here describes only what is on `main`, and
mirrors a directory of the repository.

## Responsibilities
This overview is the entry point: it names the parts of the repository and links to
the doc that owns each one.

## How it works
| Part | Directory | Doc |
|---|---|---|
| Continuous integration | `.github/` | [ci/index.md](ci/index.md) |
| Library package | `src/easy_viz/` | none yet |
| Tests | `tests/` | none yet |

The library package is a placeholder that exports nothing, and `tests/` holds a single
import test. Neither has an architecture doc yet.

## Invariants
- Every architecture doc is linked from this page or from an `index.md` below it.

## Pitfalls
- None yet.
