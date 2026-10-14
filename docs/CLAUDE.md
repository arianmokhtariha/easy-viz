# Guide: knowledge base (`docs/`)

The documentation is the single source of truth for humans and agents. Code shows
*what*; these documents carry *how it fits together* and *why*.

## Kinds of documents
| Kind of truth | Lives in | Lifecycle |
|---|---|---|
| Vision, principles, non-goals | `docs/product.md` | Changed only by the product manager |
| Public rules and vocabulary | `docs/conventions.md` | Changes are public-API decisions: product manager approval first |
| How the code works now | `docs/architecture/` | Describes only what is merged to `main` |
| Why it's built this way | `docs/decisions/NNNN-*.md` | Never edited once accepted; a new record supersedes it |
| Work not built yet | `docs/plans/NNNN-*.md` | Has a `Status`; deleted when implemented |
| Public API reference | docstrings → generated pages | Never restated in prose docs |
| Usage guide and showcase | `gallery/` notebooks → docs site and README images | Executed in CI; updated with every plot change |
| Progress / user-visible changes | `ROADMAP.md`, `CHANGELOG.md` (repo root) | Updated in the PR that causes the change |

## Rules
1. **One fact, one place.** Other documents link to it instead of repeating it.
   Duplicated facts drift apart.
2. **Architecture docs are reality.** Never describe planned or partial behaviour in
   `docs/architecture/`.
3. **Graduation:** in the PR that completes a plan,
   - the plan's lasting content moves into architecture docs
   - its decisions become decision records
   - the plan file is deleted (git history and the PR keep it)
4. **Write for an agent with zero context.** Explain *why* wherever the code alone
   can't show it.
5. **Format:** Markdown (built by Sphinx through MyST). Relative links only.
6. **The Sphinx config excludes `CLAUDE.md`** (`exclude_patterns`). This guide sits
   inside `docs/` on disk but must never be published.

## Where documents go
Every location is fixed, so any agent can predict where a fact lives, and a test can
check it.

```
docs/
  product.md                 vision and principles (product manager only)
  conventions.md             binding public rules and vocabulary
  architecture/              how the code works now; mirrors the repository
    index.md                 system overview: layers, data flow, a link to every doc
    easy_viz/                mirrors src/easy_viz/, one directory per package
      index.md               the package itself, plus its small modules
      <module>.md            one module that needs its own doc (rule 2 below)
      plots/index.md         ...and so on for every subpackage
    gallery/index.md         repository directories outside src/ by name
    tests/index.md
    scripts/index.md
    ci/index.md              documents .github/ (the only renamed mirror)
  decisions/NNNN-*.md        why
  plans/NNNN-*.md            what's next
  images/readme/             generated README images (never edited by hand)
```
The API reference is generated from docstrings at docs build time and never written
by hand.

**Placement rules for architecture docs:**
1. **Mirror:** the docs for a source directory live at the same relative path under
   `docs/architecture/`. `src/easy_viz/stats/` maps to
   `docs/architecture/easy_viz/stats/`. Every source directory that holds code has an
   `index.md` there: what the package is for, how its modules connect, and its
   invariants.
2. **Own doc or index:** a module gets its own `<module>.md` when it exports public
   names (in `easy_viz.__all__`) or has more than 150 lines. Otherwise its package
   `index.md` covers it.
3. **Exactly one owner:** every code file is named in the `Covers:` line of exactly
   one architecture doc. There are no undocumented files and no double-documented
   ones.
4. **Docs follow code:** when a file or directory is created, moved, renamed, split or
   deleted, its doc is created, moved, renamed, split or deleted in the same PR. There
   are no orphan docs.
5. **Reachable:** every doc is linked from its parent `index.md`, up to
   `docs/architecture/index.md`.
6. **Growth:** when a module crosses the threshold in rule 2, its section moves out of
   `index.md` into its own doc, and `index.md` links to it.

## Formats
**Architecture doc** (`index.md` or `<module>.md`, placed by the rules above):
```
# <Package or module>
Covers: src/easy_viz/_data.py, src/easy_viz/_validate.py
## Responsibilities
## How it works        (data flow, main functions, how it connects to other modules)
## Invariants          (what must always stay true)
## Pitfalls            (non-obvious traps, with the reason)
```
An `index.md` uses the same sections at package level, and links to every doc in its
directory. Only an `index.md` may say `Covers: nothing directly; <why>`: the overview,
or a directory whose modules all have their own docs.

**Decision record** (`docs/decisions/NNNN-short-title.md`):
- Header: `Status` (accepted / superseded by NNNN) and `Date`.
- Sections: Context, Decision, Alternatives, Consequences.
- Numbered in order.

**Plan** (`docs/plans/NNNN-short-title.md`):
- Header: `Status`, one of: `proposed` (awaiting the product manager), `approved`,
  `in progress`.
- Sections: Goal, Scope, Tests delivered with it, Acceptance criteria.
- Implementation starts only once the status is `approved`.
