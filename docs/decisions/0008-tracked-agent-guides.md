# 0008: Agent guides are tracked in git and kept out of the library

**Status:** accepted · **Date:** 2026-10-14

## Context
easy-viz is built by AI coding agents working for a product manager. The agents'
working rules live in `CLAUDE.md` guides, one per directory that has rules of its own,
and in agent definitions under `.claude/agents/` (such as the independent code
reviewer). Until now these files were gitignored: they existed on one machine only.
That had costs:
- rule changes left no history and showed in no pull request, so they could not be
  reviewed, reverted, or seen by anyone reading the project
- a fresh clone, or CI, had no guides, so the checks that keep the guides consistent
  could only run locally
- tracked documents could not link to a guide, because the link would break

The working method is part of what this portfolio project shows, so it belongs in the
repository. The library users install must still contain only the library.

## Decision
- **The guides (`CLAUDE.md`) and `.claude/agents/` are tracked** and change through
  branches and pull requests like code.
- **Personal overrides stay gitignored:** `CLAUDE.local.md` and
  `.claude/settings.local.json` hold one person's local settings, not project rules.
- **The build excludes every agent file.** `pyproject.toml` lists them in the build
  backend's `source-exclude`, which applies to both the source distribution and the
  wheel. A test builds both and fails if any agent file is inside.

## Alternatives
- **Keep the guides local-only:** private, but no history or review, no CI checks,
  and the working method stays invisible.
- **A separate repository for the guides:** history without the noise, but rule
  changes and the code they govern could no longer change together in one pull
  request.
- **Exclude guides only through `.gitignore`:** that was the old protection against
  shipping them; once they are tracked it no longer applies, so the build needs its
  own explicit exclusion.

## Consequences
- **Easier:**
  - every rule change has a history, a diff and a pull request
  - CI checks that the guide table matches the guides on disk and that links
    inside guides resolve
  - documents may link to a guide
- **Harder:**
  - the guides are public: they must never contain personal details or anything
    secret
  - pull requests that change rules are longer
