---
name: release
description: >-
  Release everything merged since the last release as a new easy-viz version on
  PyPI. Reads the changes from git, works out the version number, writes the
  changelog entry that becomes the GitHub release text, and ships it through a
  release pull request.
disable-model-invocation: true
argument-hint: "[patch | minor | major | X.Y.Z] (optional: overrides the computed version)"
---

# Release easy-viz

The product manager invoked this skill. That is the explicit approval the root
guide requires to change `version`, publish to PyPI, and merge the release pull
request once CI is green, for this one release only.

The release workflow does the publishing ([decision 0013](../../../docs/decisions/0013-automated-releases.md)).
This skill prepares what it publishes: the version number and the changelog entry.
The entry is the GitHub release text, so it must be accurate, complete, and read as
if a person wrote it.

**Read first:** decision 0013 (process, version rules, changelog format), the
`Release` section of `docs/architecture/ci/index.md`,
`docs/architecture/scripts/release_notes.md`, and `CHANGELOG.md` (the previous
entry is the model for tone and bullet style). A release changes no library code,
so the rest of the root guide's orientation is not needed.

## 1. Preconditions
Stop and report to the product manager if any of these fails:
- the working tree is clean; `git switch main && git pull && git fetch --tags`
- the latest `CI` and `Release` runs on `main` are green
  (`gh run list --branch main --limit 4`)
- no release pull request is open: this prints nothing
  (`--head` matches whole branch names only, so filter by prefix):
  `gh pr list --json number,headRefName --jq '.[] | select(.headRefName | startswith("release/"))'`
- the last release is the newest tag `v<X.Y.Z>`
  (`git describe --tags --abbrev=0 --match "v[0-9]*"`). `uv version --short`
  prints either that same version, or a `.dev` version of a later one
  (`0.3.0.dev0` after `0.2.0`), which decision 0013 also allows on `main`. With
  no tag at all, this is the first release and the range below is the whole
  history.

## 2. Collect every change since the last release
Commit titles and PR descriptions are claims. The diff is the evidence.
- `git log v<last>..HEAD --reverse --format="%h %s"`: one squash-merged pull
  request per commit, titled as a Conventional Commit, `type(scope)!: summary (#N)`.
- For each `#N`: `gh pr view N --json title,body,files`. Its *Outcome* and *Product
  impact* sections say what changed for users.
- `git diff --stat v<last>..HEAD`, then the diff of everything public:
  `src/easy_viz/__init__.py` (`__all__`), the signatures and docstrings of public
  functions, `Theme` and `Config` fields, `pyproject.toml` (dependencies and
  `requires-python`).
- The `## Unreleased` notes in `CHANGELOG.md`, which each pull request added.

## 3. Sort each change into a section
| Change | Section |
|---|---|
| a new function, parameter, option value, theme field (`feat`) | Added |
| different behaviour, default, look or name of something that exists | Changed |
| still works but will go | Deprecated |
| gone | Removed |
| a bug fix (`fix`) | Fixed |
| a vulnerability fix | Security |
| CI, tests, docs, gallery, tooling, refactors (`ci`, `test`, `docs`, `build`, `chore`, `refactor`) | Internal |

A change is **breaking** when existing user code can stop working or give a
different result: a removed or renamed public name or parameter, a changed
default, a changed return value, a raised `requires-python` or dependency lower
bound. Check for this in the diff even when the commit title has no `!`. A breaking
bullet starts with `Breaking:`, says what to change in user code, and the summary
mentions it.

## 4. Work out the version
From the last release `X.Y.Z`, by decision 0013:

| What the release holds | While `X` is 0 | From 1.0.0 |
|---|---|---|
| a breaking change | `X.(Y+1).0` | `(X+1).0.0` |
| anything in Added, Changed or Deprecated | `X.(Y+1).0` | `X.(Y+1).0` |
| only Fixed or Security | `X.Y.(Z+1)` | `X.Y.(Z+1)` |
| only Internal | no release | no release |

- **Only Internal:** stop. Tell the product manager there is nothing new for users
  to install and list what is waiting. Decision 0013 rules such a release out;
  changing that needs a new decision record first, not a release.
- **`main` is on a `.dev` version** (step 1): release that version without the
  `.dev` part (`0.3.0.dev0` becomes `0.3.0`), unless the table asks for a higher
  one. Never go below it.
- **An argument was given** (`patch`, `minor`, `major` or an exact version): use it
  if it is higher than the last release and not lower than the table requires.
  Otherwise ask before going on: a patch that hides a breaking change misleads
  every user who upgrades.
- Going to 1.0.0 is always the product manager's call. Never compute it.

## 5. Write the entry
In `CHANGELOG.md`, insert `## <version> - <today, YYYY-MM-DD>` directly under
`## Unreleased`, which stays as an empty heading, and move the notes under it.
- **Complete and true:** every user-visible change from step 2 has a bullet, every
  bullet matches the diff, no change appears twice, and each section heading
  appears once.
- **Summary** (required, one paragraph, 1–3 sentences): what an analyst can do now
  that they couldn't before, or why they should upgrade. Name breaking changes.
- **Bullets:** start with the public name in backticks when there is one; say what
  the user can do or what changed for them; one change per bullet. User sections
  never mention PR numbers or internal module names. Internal bullets stay short,
  one line where possible.
- **Format:** only the sections Added, Changed, Deprecated, Removed, Fixed, Security,
  Internal, in that order, each a bullet list. Wrap at 88 columns with continuation
  lines indented two spaces (the release script joins them again).
- Never rewrite an earlier release's entry.

## 6. Make it read like a person wrote it
Run the `humanizer` skill on the summary and every bullet, then the `no-ai-slop`
skill on its result. Tell both: the audience is data analysts reading a changelog
and a GitHub release; keep the Markdown structure, headings, backtick names,
numbers and facts; the voice is plain and technical (no first person, no
opinions, no jokes). Apply the result to the entry.

If either skill is not installed, apply its core rules yourself: no em or en
dashes; no promotional words ("powerful", "seamless", "robust"); no trailing
"-ing" clauses that add fake depth; no padding lists of three; active voice;
concrete facts over claims.

Then compare the entry with the previous release's: the same tone, the same bullet
style, the same level of detail.

## 7. Bump, check, preview
- Create the branch `release/v<version>`.
- `uv version <version>`: updates `pyproject.toml` and `uv.lock` together.
- `ROADMAP.md`: add `Release <version> on PyPI (<the headline changes>), <date>` at
  the top of *Done*, as for every earlier release, and remove any *Next* item it
  completes. At 1.0.0, also update the README's status line.
- `uv run --no-project python scripts/release_notes.py <version> --repo "$(gh repo view --json nameWithOwner -q .nameWithOwner)"`
  prints the exact release text.
- The root guide's definition-of-done checks, all passing: `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run mypy src`, `uv run pytest`, plus
  `uv lock --check`.

## 8. Review
Commit (`chore(release): easy-viz <version>`), then have the branch reviewed as the
root guide's Delivery section requires, before any pull request exists. Fix every
real finding, run the checks of step 7 again, and keep the fixed release text for
step 9.

A release branch holds only the version, the lock file and the documents above.
Anything else needs its own pull request first.

## 9. Confirm once
PyPI never takes a version back, so ask exactly one question before anything leaves
the machine. Show the version with its one-line reason (e.g. "0.3.0: two new
features, nothing breaking") and the full release text. Then use AskUserQuestion:
**Publish** / **Change the notes** (they say what; apply it, then ask again) /
**Cancel**. If the text changes after this answer for any reason, ask again: only
text the product manager has seen gets published.

## 10. Ship
1. Push the branch and open the pull request with the commit's title. The body uses
   the root guide's report sections, short, with the release text under *Outcome*.
2. `gh pr checks --watch`. Once green: `gh pr merge --squash --delete-branch`, then
   `git switch main && git pull`, and note the merge commit: `sha=$(git rev-parse HEAD)`.
3. Follow that commit, not the newest run (the newest can still be the previous
   release's): `CI` first, then `Release`, which starts a few minutes after CI
   passes. Find each with `gh run list --workflow <ci.yml | release.yml> --commit "$sha"`
   (retry until it appears) and follow it with `gh run watch <id> --exit-status`.
4. Verify:
   - `gh release view v<version>` shows the release text and two files
   - `https://pypi.org/pypi/<package>/<version>/json` answers 200
   - `uv run --isolated --no-project --refresh --with <package>==<version> python -c "import easy_viz"`
     works (PyPI's index can take a minute to update; retry once)

## If something fails
- **CI fails on the release pull request:** fix the cause in its own pull request.
  Once that is merged, merge `main` into the release branch (`git merge main`, a
  new commit) and push. Never rebase a pushed branch: that needs a force-push, which
  needs the product manager's approval.
- **The publish job fails:** read its log, and never bump the version to retry.
  - "invalid-publisher", or any 400 that names the publisher: the PyPI trusted
    publisher doesn't match (project `easy-viz`, workflow `release.yml`,
    environment `pypi`). The product manager fixes it on PyPI.
  - a PyPI or network outage: wait.

  Then re-run with `gh run rerun <id>`.
- **Uploaded, but the GitHub release failed:** `gh run rerun <id>`. The upload is
  skipped (`skip-existing`), and the release is created.
- **A broken version reached PyPI:** never delete it. Fix forward with a patch
  release. Yanking (hiding it from new installs) needs the product manager's
  approval.

## Report
Use the root guide's Reporting sections, kept short:
- *Outcome*: the version, with links to the pull request, the GitHub release and the
  PyPI page
- *Why this way*: the version reasoning
- *Product impact*: what users get
- *Verification*: the CI run, the release run and the PyPI check, with real results
- *Knowledge sync*: CHANGELOG and anything else touched

Paste the release text at the end.
