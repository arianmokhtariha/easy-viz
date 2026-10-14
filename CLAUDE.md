# easy-viz: root guide for AI agents

## Product
**easy-viz is the Metabase / Power BI of Python, at the code level.**
- A SQL result goes straight into one function call, and a finished Plotly figure
  comes out.
- Simple charts take a few options. Professional charts take more options, never
  more code.
- Whatever the parameters don't cover or can't cover, the user finishes on the
  returned `go.Figure`.

The full vision, the problem, the product principles, the query-result shapes and the
non-goals are in `docs/product.md`. **That document is the yardstick for every
change:** a technically good change that weakens a product principle is a bad change. 

easy-viz grows out of the owner's earlier work, kept locally in `legacy/` (gitignored):
- `legacy/custom_plots.py`: the 25-function Plotly module that easy-viz generalises
- `legacy/conclusions.ipynb`: report charts that module couldn't produce, plus their
  report theme and `save()` helper

These files show the old approach. They are reference material to port, not code to
copy as-is. Porting rules are in `src/easy_viz/plots/CLAUDE.md`. When porting is
complete, the product manager deletes `legacy/`, and the porting rules are removed in
the same task.

## Orientation: before touching anything
Every task starts with reading. Edit nothing until it's done. Documents already read
in this session need re-reading only if they changed since.
1. `docs/product.md`, `README.md` and this guide: the vision, the principles, and the
   problem easy-viz solves.
2. `ROADMAP.md`: where the project stands.
3. `docs/decisions/`: every record at the start of a session (each is one page).
   These explain why the project has its shape.
4. `docs/conventions.md`.
5. For the area you'll work in:
   - the guides on its path
   - `docs/architecture/index.md`, then the docs at the area's mirrored paths
   - the plan being implemented, if any
6. The code you'll change, and its tests.

Then, before the first edit, state in 2–3 sentences:
- what the task is for, in product terms
- which product principles it serves, and any it could weaken
- which documents you read
- anything in them that conflicts with the request

A conflict goes to the product manager before any work starts.

## Working model
- **The owner is the product manager**, a data analyst/scientist, not a software
  engineer. They judge the library as a product: what it does, how consistent and
  pleasant it is. They don't review code line by line.
- **You are the engineering team.** Technical decisions are yours, within these
  guides. Because nobody re-checks your code, technical quality is your
  responsibility.
- **Escalate only these**, with a short plan (goal, approach, alternatives,
  trade-offs), and wait for approval:
  - a change to the public API (names, parameters, defaults, return types)
  - a new runtime dependency
  - a change that contradicts a decision record
  - a trade-off the user would see
  - a change to this file's Working model, Delivery or Reporting sections

  Everything else: decide, do it, report.
- **Rules serve the product.** If a rule blocks a clearly better solution, say so and
  propose an amendment (with a decision record). Don't quietly work around it, and
  don't follow it into a worse result.
- **It's a portfolio product.** Plans, decision records, PRs and commit history are
  part of what gets shown, so they must read well to an outsider.

## Guide system
Rules live in a tree of CLAUDE.md files. Each one covers its directory and everything
below it. A directory's guide loads automatically once you read a file in it. **Before
creating or editing anything in a directory, read its guide and every guide above it.**

**Guides are tracked in git** ([decision 0008](docs/decisions/0008-tracked-agent-guides.md)),
like the agent definitions in `.claude/agents/`, so:
- Guide changes go through branches and PRs like code, and show up in PR diffs.
- Guides and agent files are never part of the library: the build excludes them
  (`source-exclude` in `pyproject.toml`), and a test builds the package to prove it.
- Personal overrides stay local and gitignored: `CLAUDE.local.md` and
  `.claude/settings.local.json`.

| Guide | Covers |
|---|---|
| `CLAUDE.md` | the whole repo: product, working model, knowledge sync, delivery, reporting |
| `src/easy_viz/CLAUDE.md` | all library code: layering, public API, API evolution, compatibility |
| `src/easy_viz/plots/CLAUDE.md` | public plotting functions: styling, porting, adding a plot |
| `src/easy_viz/stats/CLAUDE.md` | the statistics layer |
| `src/easy_viz/theme/CLAUDE.md` | themes |
| `tests/CLAUDE.md` | tests |
| `docs/CLAUDE.md` | the knowledge base: kinds of documents, formats, lifecycle |
| `gallery/CLAUDE.md` | the notebook gallery, showcase dataset and README images |

**Placement rules (where a rule goes):**
1. **One rule, one guide:** the guide of the narrowest directory whose whole subtree
   it applies to. If it applies to sibling directories, use their nearest common
   parent. Never copy a rule into a second guide; link to it.
2. **Guides hold instructions** (how to work here). **Knowledge** (what the code is,
   why it's built that way) belongs in `docs/`, per `docs/CLAUDE.md`.
3. **A new directory that needs rules of its own** gets its guide in the same task,
   plus a row in the table above. A directory without its own rules gets no guide.
4. **Moving, renaming or deleting a guide** updates the table in the same task.
   `tests/test_knowledge_base.py` fails if the table and the files disagree.
5. **How to write a rule:**
   - it must be pass/fail, specific to this project, and state its reason when that
     isn't obvious
   - no rules for what competent engineering already does
   - when a test can enforce it, add the test

## Knowledge sync loop
**A task isn't finished when the code works. It's finished when every guide and
document matches the code.** Stale knowledge is a bug: the next agent will trust it.

**Before** modifying a module, read the architecture doc that covers it. If the doc is
wrong, fix it in the same PR.

After the code is done and all checks pass, run this loop before reporting:
1. **List what changed:** `git diff --name-only main...HEAD`, plus uncommitted files.
2. **For each changed path, check and update whatever is now out of date:**
   - the architecture doc at its mirrored path: create, move, split or delete it as
     the placement rules in `docs/CLAUDE.md` require
   - every guide on its path (new or changed rules, new patterns worth following)
   - `docs/conventions.md` (new parameter names, trace roles, message patterns)
   - the plan being implemented (graduate and delete it when complete)
   - a decision record, for any significant choice
   - `CHANGELOG.md` and `ROADMAP.md`
   - the gallery notebook of every plot function added or changed (re-executed),
     `gallery/README.md`, and the README images if any are affected
   - the guide table above, if a guide was added, moved or removed

   Read `docs/CLAUDE.md` before editing any document.
3. **Repeat from step 1.** Sync edits can make other documents stale. Stop when a
   full pass changes nothing.
4. **Verify:** `uv run pytest tests/test_knowledge_base.py` passes.
5. **Report:** list every document and guide updated or created, and why, in the
   report's *Knowledge sync* section. For a guide, state the rule change itself.

If you notice any guide or document that contradicts the code, even outside your task,
fix it in the current PR and mention it in the report.

## Writing tests 
use tests to make correctness measurable(pass/fail) by codifying the correct logic. 
quality of tests matters more than the quantity of tests, for example writing multiple 
tests that catch no real edge-cases, bugs and anomalies is considered low-value, instead 
few tests that catch real problems, bugs, anomalies and edge-cases are a lot more worthy. 

## Visual review loop
Code that draws charts is judged by looking at the result. The checks only prove the
code runs. Any change that can alter what a figure looks like (plot functions, theme,
layout helpers, gallery notebooks) goes through this loop before it is reported done:

1. **Render:** run the gallery build script for the affected notebooks. It executes
   them and saves every image output to `.review/<notebook>/<cell>.png`. For figures
   outside the gallery, export to PNG with `fig.write_image()`.
2. **Look:** read every affected PNG (the Read tool shows images). Reading a notebook
   file directly omits its image outputs, so always read the extracted PNGs.
3. **Judge:** each image against this defect list:
   - text overlapping text, marks or reference lines
   - anything clipped: labels, titles, legends, annotations
   - text that's unreadable (size or contrast)
   - a legend or annotation covering data
   - crowded or badly rotated axis ticks
   - large empty areas, or squeezed plot areas
   - colours off-theme or inconsistent across related charts
   - the chart doesn't clearly show what its notebook section claims it shows
4. **Fix the cause:** if a default or behaviour of the library produces the defect,
   fix the plot function or theme, not the notebook cell. Every user would hit the
   same defect.
5. **Repeat** from step 1 until a full pass finds no defects. If a defect can't be
   fixed (e.g. a Plotly limitation), report it with the reason.
6. **Show:** for meaningful visual changes, keep before/after PNGs in `.review/`.
   - In the end-of-task message: give their paths, so the product manager can open
     them.
   - In the PR body: describe the visual change in words. Executed gallery
     notebooks show their images in the PR's file view.

## Settled decisions
Summaries only; the records are the source.
- [0001](docs/decisions/0001-plotly-single-core.md): Plotly 7 is the only rendering core.
- [0002](docs/decisions/0002-parameter-rich-api.md): parameter-rich functions (20–40 options) are the design.
- [0003](docs/decisions/0003-return-plain-figure.md): every plot returns a plain `go.Figure`.
- [0004](docs/decisions/0004-narwhals-dataframe-agnostic.md): narwhals internals; no pandas/polars runtime dependency.
- [0005](docs/decisions/0005-python-version-policy.md): support Python ≥ 3.13, develop on 3.15.
- [0006](docs/decisions/0006-notebook-gallery.md): executed notebooks are the gallery and the source of README images.
- [0007](docs/decisions/0007-immutable-global-defaults.md): theme and config are immutable values swapped by `set_*`; Plotly's default template is never touched.
- [0008](docs/decisions/0008-tracked-agent-guides.md): agent guides and agent definitions are tracked in git and excluded from the build.

## Dependencies
- `pyproject.toml` gives runtime dependencies lower bounds only, never upper caps, so
  easy-viz fits into users' existing environments.
- Dev and docs tools go in `[dependency-groups]`. Optional user features go in
  `[project.optional-dependencies]`.

## Delivery
- **Branch per change** (`feat/bar-plot`, `fix/heatmap-labels`). Never commit to
  `main` directly.
- **Open a PR with `gh pr create`.**
  - Title: a Conventional Commit (`feat: add pareto_plot`, `fix(bar_plot): ...`;
    `feat!:` for a breaking change).
  - Body: the report (below).
- **Before opening a PR:** once the work is complete and all checks pass, have the
  whole branch reviewed **once** by the `code-reviewer` subagent
  (`.claude/agents/code-reviewer.md`). It audits the branch with
  `/code-review` and reports its findings. Fix every real issue it reports; each fix
  gets a test that fails without it where the issue is testable, then re-run all
  checks. No second review round: later rounds cost a full review each and find
  mostly low-impact issues. Report a summary of the issues the review found and how
  each was resolved (fixed, or rejected with the reason).
  - **Keep it unbiased:** the prompt names only what to review (branch and base).
    Never pass your reasoning, approach, known issues or earlier findings. Reviewing
    from the main session (or a fork of it) is not independent and doesn't count.
  - The reviewer works alone and never spawns agents (it has no Agent tool). Nested
    agents take a long time and add no value.
- **After opening it:** wait for CI (`gh pr checks --watch`). Then give the product
  manager the report and the CI result in your end-of-task message, plus the PR
  link. They should never need to open GitHub to know the state of a PR.
- **Feedback:** the product manager gives change requests in chat, or as PR comments
  (read them with `gh pr view --comments`). Push fixes to the same branch; the PR
  updates itself. Each round ends with an updated report.
- **Merging is the product manager's decision.** They either click **Squash and
  merge** on GitHub, or tell you to merge. Only on an explicit instruction:
  ```
  gh pr merge --squash --delete-branch
  git switch main
  git pull
  ```
  Never merge on your own judgement, and never while CI is red.
- **Never without explicit approval:** force-push, rewrite pushed history, change
  `version` in `pyproject.toml`, publish to PyPI, change repo visibility or settings,
  touch secrets. A version change merged to `main` triggers a public release.

**Definition of done:**
- these pass: `ruff check`, `ruff format --check`, `mypy src`, `pytest`
- the definition-of-done items in the guides of every directory you changed
- the knowledge sync loop is complete
- the report is written

## Reporting
Every PR body and end-of-task message uses these sections, in plain language. Define a
technical term in a few words the first time it appears.
1. **Outcome**: what changed for the user, in 1–3 sentences.
2. **Why this way**: the reasoning, and the alternatives rejected.
3. **Product impact**: new capabilities and any public-API change.
4. **Verification**: the commands run and their actual results, including failures and
   anything skipped. For visual changes, the visual review result (see step 6 of the
   loop for where the images go).
5. **Knowledge sync**:
   - the documents read during orientation
   - each document updated or created, and why
   - each guide updated or created, with the rule change itself
6. **Decisions needed**: each with your recommendation.
7. **Next step**

## Commands
```
uv sync --all-extras --all-groups      # install everything
uv run pytest                          # tests (export tests auto-skip without Chrome)
uv run ruff check --fix .              # lint
uv run ruff format .                   # format
uv run mypy src                        # strict type check
uv run pytest --nbmake gallery/       # execute every gallery notebook
uv run python scripts/build_gallery.py   # regenerate data, notebooks, README images (plan 0002)
uv run python scripts/render_theme_samples.py   # theme sample sheets → .review/theme/
uv run sphinx-build docs docs/_build   # build the docs site (once docs are set up)
```
