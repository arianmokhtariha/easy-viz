# Architecture

Covers: nothing directly; every file is covered by one of the docs linked below.

How easy-viz is built today. Every doc here describes only what is on `main`, and
mirrors a directory of the repository.

## Responsibilities
This overview is the entry point: it names the parts of the repository and links to
the doc that owns each one.

## How it works
| Part | Directory | Doc |
|---|---|---|
| Continuous integration | `.github/` | [ci/index.md](ci/index.md) |

The library package `src/easy_viz/` is a placeholder with no public functions yet. Its
architecture docs are created together with its first modules.

## Invariants
- Every architecture doc is linked from this page or from an `index.md` below it.

## Pitfalls
- None yet.
