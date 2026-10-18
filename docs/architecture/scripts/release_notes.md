# Release notes

Covers: scripts/release_notes.py

## Responsibilities
Check the format of `CHANGELOG.md` and turn one version's entry into the text of
its GitHub release ([decision 0013](../../decisions/0013-automated-releases.md)).

## How it works
The release workflow ([CI](../ci/index.md)) runs it for every final version, on
pull requests and before publishing:
`uv run --no-project python scripts/release_notes.py <version> --repo <owner/name>`.
It uses only the standard library, so CI runs it without installing the project.

- `parse_changelog` splits the file at `## ` headings, then each entry at `### `
  headings, and checks the whole file, not only the requested version:
  `## Unreleased` first (no summary, any sections); then releases as
  `## X.Y.Z - YYYY-MM-DD`, versions strictly decreasing and dates never increasing,
  each with a one-paragraph summary and at least one section. Section names come
  from `SECTIONS`, in its order, each a non-empty bullet list. Any break raises
  `ChangelogError`, whose message names the entry and the fix.
- `release_body` returns the summary and the sections as written, then a footer:
  the install command (with the package name read from `pyproject.toml`) and a link
  comparing the previous release's tag with this one, or listing this tag's commits
  for the first release. `unwrap` first joins the changelog's hard-wrapped lines
  into one line per paragraph and per bullet (nested bullets kept).
- `main` prints the body, or exits with the error message.

## Invariants
- The real `CHANGELOG.md` always parses: a test runs `parse_changelog` on it, so a
  pull request that breaks the format fails before a release would.
- Nothing is repository-specific in the code: the repository comes from `--repo`
  (`$GITHUB_REPOSITORY` in CI), the package name from `pyproject.toml`.

## Pitfalls
- **The body is the entry as written.** The script never rewrites prose, so the
  summary and bullets must already read well in the changelog.
- **GitHub shows every line break in a release body**, unlike Markdown files, so
  the 88-column wrapping of the changelog would cut sentences in half there; that
  is why `unwrap` exists. A line that must stay separate has to be its own bullet.
- **Release tags are `v<version>`.** The compare link assumes it, as does the
  workflow that creates them.
