# 0013: Releases publish automatically from a version bump on `main`

**Status:** accepted · **Date:** 2026-10-18

## Context
easy-viz 0.1.0 is its first release on PyPI. Every later release must be as safe
as the first, without a person running upload commands by hand:
- a PyPI version can never be uploaded twice, even after it is deleted, so a broken
  upload costs a version number
- a stored upload token is a secret that can leak, and it works from any machine
- users read the GitHub release text, so it should say what changed, with the same
  structure every time

The project already works through pull requests, and a version change needs the
product manager's approval (root guide), so the merge of that change is the natural
moment to publish.

## Decision
- **A final version merged to `main` is released, once its tests pass.** The
  `Release` workflow runs after the `CI` workflow succeeds on a commit pushed to
  `main`, and builds that exact commit, so a merge that breaks the tests never
  reaches PyPI. It publishes only a final version
  (`0.2.0`, never `0.2.0.dev0` or `0.2.0rc1`) whose tag `v<version>` does not exist
  yet. Development happens on a `.dev` version or on the last released one, so an
  ordinary merge never publishes.
- **The package is checked before it can be published**, on every pull request too:
  it builds, `twine check` confirms the PyPI page renders, and the wheel is
  installed in a clean environment and imported.
- **Trusted publishing.** PyPI accepts uploads from this repository's `release.yml`
  in the `pypi` environment, proven by a short-lived token GitHub issues per run.
  There is no stored secret. The upload carries attestations: signed records of
  which workflow built each file.
- **The GitHub release follows the upload**, so it never announces a version
  users can't install. Creating it creates the tag. Its text is the version's
  `CHANGELOG.md` entry plus a fixed footer (install command, link to every commit
  since the previous release), written by `scripts/release_notes.py`.
- **The changelog has a fixed format**, checked on every pull request:
  `## X.Y.Z - YYYY-MM-DD`, a one-paragraph summary, then only the sections Added,
  Changed, Deprecated, Removed, Fixed, Security and Internal, in that order. Internal
  is our addition to Keep a Changelog: work that doesn't change what users install
  or call (CI, tests, docs), kept short.
- **Version numbers follow Semantic Versioning.** While the major version is 0, a
  breaking change or a new feature raises the minor version (0.1.0 → 0.2.0) and
  fixes alone raise the patch (0.1.0 → 0.1.1). From 1.0.0, a breaking change
  raises the major version. Internal-only changes are not released: users would
  install the same library under a new number.

## Alternatives
- **Uploading by hand with an API token (`uv publish`):** a long-lived secret on a
  laptop, no record of what was built from which commit, and steps that can be
  skipped.
- **Publishing on a pushed tag:** a tag can be pushed from any branch without a
  pull request or green CI, and the version in `pyproject.toml` can disagree with it.
- **Publishing on the push to `main`, beside CI:** simpler, but nothing waits for
  the tests of the merged commit, which can fail when two pull requests merge close
  together.
- **Release bots (release-please, semantic-release):** they compute versions and
  notes from commit messages alone. Our squash-merged commits are titled well, but
  the notes deserve a human-quality summary, and a bot adds a dependency and its
  own pull request flow.
- **A dry run on TestPyPI first:** catches upload problems without spending a
  version; rejected by the product manager (2026-10-18), because the build job
  already checks the package before any upload.

## Consequences
- **Easier:** a release is one reviewed pull request; no secret to manage; every
  release has notes with the same structure; a failed release is re-run from the
  Actions tab ("Re-run all jobs"): an upload that already happened is skipped, and
  the GitHub release follows.
- **Harder:**
  - the changelog must keep its format; a pull request that breaks it fails
  - a mistake that reaches PyPI can only be fixed by a new version (yanking hides
    a version from new installs but never frees its number)
  - the PyPI trusted publisher names the workflow file and environment: renaming
    either breaks publishing until the PyPI settings are updated
