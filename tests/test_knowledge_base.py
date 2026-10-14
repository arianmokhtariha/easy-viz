"""Repository-wide checks that the documentation matches the repository.

Documentation that drifts from the code misleads the next reader, so these rules turn
the placement rules of the knowledge base into pass/fail checks. Every rule is a pure
function that takes the repository root and returns a list of problems (empty when it
holds); each problem names the file, the broken rule and how to fix it. The tests at
the bottom run the rules on the real repository, and on small temporary trees that
prove the subtle rules do fail when they should.

Rules on the real repository
----------------------------
* Relative links in ``docs/`` and in the top-level Markdown files resolve to an
  existing path (exact letter case, because CI runs on case-sensitive Linux). Anchors
  (``#section``) are not checked: GitHub and Sphinx build them differently.
* Every architecture doc (``docs/architecture/**/*.md``) has a ``Covers:`` line whose
  paths exist, a ``# Title``, and the sections Responsibilities, How it works,
  Invariants, Pitfalls, in that order.
* Every ``*.py`` file in ``src/``, ``scripts/`` and ``gallery/`` (``__init__.py``
  included) is named in the ``Covers:`` line of exactly one architecture doc, which
  lives at the file's mirrored path: ``src/easy_viz/theme/x.py`` is documented in
  ``docs/architecture/easy_viz/theme/``; ``__init__.py`` by that directory's
  ``index.md``. Every directory with code has an ``index.md``.
* A module that exports public names (an object of ``easy_viz.__all__`` is defined in
  it) or has more than 150 lines has its own ``<module>.md`` that covers it.
* Every directory under ``docs/architecture/`` mirrors an existing source directory:
  ``easy_viz`` is ``src/easy_viz``, ``ci`` is ``.github``, any other name is the
  top-level directory of that name.
* Every architecture doc is linked from the ``index.md`` of its directory (or the
  nearest parent directory that has one), so all are reachable from
  ``docs/architecture/index.md``.
* Every plan in ``docs/plans/`` has ``**Status:**`` ``proposed``, ``approved`` or
  ``in progress``.
* No file tracked by git (or about to be) links to, or names the path of, an agent
  guide. Excluding them is legitimate: ``"**/<guide>"`` globs in ``pyproject.toml`` and
  bare names in ``.gitignore`` or a Sphinx config pass. In Markdown, any mention fails.
* Local only (skipped when the root guide is absent, as in CI and fresh clones, because
  guides are gitignored): every guide on disk is listed in the root guide's table,
  every listed guide exists, and the relative links and ``@imports`` inside guides
  resolve.
"""

import re
import subprocess
from collections import deque
from collections.abc import Callable, Iterator
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

import pytest

import easy_viz

ROOT = Path(__file__).resolve().parents[1]
SELF = PurePosixPath("tests/test_knowledge_base.py")

ARCH = PurePosixPath("docs/architecture")
ARCH_INDEX = ARCH / "index.md"
CODE_ROOTS = ("src", "scripts", "gallery")
SECTIONS = ("Responsibilities", "How it works", "Invariants", "Pitfalls")
PLAN_STATUSES = ("proposed", "approved", "in progress")
OWN_DOC_MIN_LINES = 150  # a module longer than this gets its own doc
ARCH_RENAMED = {"ci": ".github"}  # architecture directory -> repository directory

GUIDE_NAMES = ("CLAUDE.md", "CLAUDE.local.md")
SKIPPED_DIRS = frozenset({"legacy", "node_modules", "build", "dist", "_build"})
STRICT_SUFFIXES = (".md", ".rst", ".txt", ".ipynb")  # prose: no mention of a guide

FENCE = re.compile(r"^\s*(?:```|~~~)")
INLINE_CODE = re.compile(r"`[^`\n]*`")
LINK = re.compile(r"\]\(\s*<?([^)\s>]+)")
REFERENCE_LINK = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?([^\s>]+)")
EXTERNAL = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|//|#)")
IMPORT = re.compile(r"(?<![\w`@])@((?:\.{1,2}/|[\w-]+/)[^\s)`]*)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
COVERS = re.compile(r"^Covers:\s*(.*)$")
STATUS = re.compile(r"^\*\*Status:\*\*\s*(.*?)\s*$", re.MULTILINE)

_GUIDE = r"CLAUDE(?:\.local)?\.md"
GUIDE_LINK = re.compile(rf"\]\([^)]*{_GUIDE}")
# A path with a real directory part (``a/b/<guide>``, ``../<guide>``); a glob such as
# ``**/<guide>`` has no literal directory before the slash and does not match.
GUIDE_PATH = re.compile(rf"(?<![\w*])(?:[\w.~-]+/)+{_GUIDE}")
GUIDE_NAME = re.compile(rf"\b{_GUIDE}")


# --- Files -----------------------------------------------------------------------


def find_files(
    root: Path, start: str, wanted: Callable[[str], bool]
) -> list[PurePosixPath]:
    """List files under ``root/start`` whose name satisfies ``wanted``.

    Hidden directories (``.venv``, ``.git``, caches), ``__pycache__`` and build or
    vendored directories are not entered.
    """
    base = root / start
    found: list[PurePosixPath] = []
    if not base.is_dir():
        return found
    for directory, dirnames, filenames in base.walk():
        dirnames[:] = sorted(
            d
            for d in dirnames
            if not d.startswith(".") and d != "__pycache__" and d not in SKIPPED_DIRS
        )
        found.extend(
            PurePosixPath((directory / name).relative_to(root).as_posix())
            for name in sorted(filenames)
            if wanted(name)
        )
    return found


def exists_exact(root: Path, rel: PurePosixPath) -> bool:
    """True if ``rel`` exists under ``root`` with exactly this letter case.

    Windows and macOS file systems ignore case, Linux (CI) does not: a link that
    works on a laptop must not fail on the CI runner.
    """
    current = root
    for part in rel.parts:
        if not current.is_dir() or part not in {p.name for p in current.iterdir()}:
            return False
        current = current / part
    return True


def resolve_relative(source: PurePosixPath, target: str) -> PurePosixPath | None:
    """Join ``target`` to ``source``'s directory; None if it leaves the repository."""
    parts = list(source.parent.parts)
    for part in PurePosixPath(target).parts:
        if part == "..":
            if not parts:
                return None
            parts.pop()
        elif part != ".":
            parts.append(part)
    return PurePosixPath(*parts)


def markdown_files(root: Path) -> list[PurePosixPath]:
    """Markdown the repository publishes: ``docs/`` and the top-level files."""

    def published(name: str) -> bool:
        return name.endswith(".md") and name not in GUIDE_NAMES

    top = [p for p in find_files(root, ".", published) if len(p.parts) == 1]
    return top + find_files(root, "docs", published)


def architecture_docs(root: Path) -> list[PurePosixPath]:
    return find_files(root, ARCH.as_posix(), lambda name: name.endswith(".md"))


def code_files(root: Path) -> list[PurePosixPath]:
    """Every ``*.py`` file the architecture docs must account for."""
    files: list[PurePosixPath] = []
    for start in CODE_ROOTS:
        files.extend(find_files(root, start, lambda name: name.endswith(".py")))
    return files


def read(root: Path, rel: PurePosixPath) -> str:
    return (root / rel).read_text(encoding="utf-8")


# --- Markdown reading ------------------------------------------------------------


def lines_outside_fences(text: str) -> Iterator[tuple[int, str]]:
    """Yield ``(line number, line)`` for lines that are not in a fenced code block."""
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            yield number, line


def prose_lines(text: str) -> Iterator[tuple[int, str]]:
    """Like ``lines_outside_fences``, with inline `code` removed."""
    for number, line in lines_outside_fences(text):
        yield number, INLINE_CODE.sub("", line)


def links_in(text: str) -> list[tuple[int, str]]:
    """Every link target in ``text`` as ``(line number, target)``."""
    found: list[tuple[int, str]] = []
    for number, line in prose_lines(text):
        found.extend((number, m.group(1)) for m in LINK.finditer(line))
        reference = REFERENCE_LINK.match(line)
        if reference:
            found.append((number, reference.group(1)))
    return found


def link_problem(root: Path, source: PurePosixPath, target: str) -> str | None:
    """Why ``target`` (a link written in ``source``) is broken, or None if fine."""
    if EXTERNAL.match(target):
        return None  # web link, mailto: or same-page anchor
    path_part = unquote(re.split(r"[#?]", target, maxsplit=1)[0])
    if not path_part:
        return None
    if path_part.startswith("/"):
        return "is root-relative; write a path relative to this file"
    resolved = resolve_relative(source, path_part)
    if resolved is None:
        return "points outside the repository"
    if not exists_exact(root, resolved):
        return f"points to '{resolved}', which does not exist (check spelling/case)"
    return None


def parse_covers(text: str) -> list[str] | None:
    """Paths in the ``Covers:`` line; ``[]`` for "nothing ..."; None if no such line.

    The value runs to the end of the line and over following non-blank lines.
    """
    lines = text.splitlines()
    outside = dict(lines_outside_fences(text))
    for number, line in outside.items():
        match = COVERS.match(line)
        if not match:
            continue
        value = [match.group(1)]
        for follower in lines[number:]:
            if not follower.strip():
                break
            value.append(follower)
        joined = " ".join(part.strip() for part in value)
        if joined.lower().startswith("nothing"):
            return []
        return [p.strip().strip("`").strip() for p in joined.split(",") if p.strip()]
    return None


# --- Rules: links and format -----------------------------------------------------


def check_links(root: Path) -> list[str]:
    """Rule: every relative link in the published Markdown resolves."""
    problems = []
    for source in markdown_files(root):
        for number, target in links_in(read(root, source)):
            problem = link_problem(root, source, target)
            if problem:
                problems.append(
                    f"{source}:{number}: link '{target}' {problem}. Fix the path or "
                    f"remove the link (only relative links are allowed)."
                )
    return problems


def check_covers_exist(root: Path) -> list[str]:
    """Rule: every path in an architecture doc's Covers line exists."""
    problems = []
    for doc in architecture_docs(root):
        for path in parse_covers(read(root, doc)) or []:
            rel = PurePosixPath(path)
            if rel.is_absolute() or not exists_exact(root, rel):
                problems.append(
                    f"{doc}: Covers lists '{path}', which does not exist. List "
                    f"repository-relative paths of files that exist (no globs); "
                    f"remove or rename the entry if the file moved."
                )
    return problems


def check_doc_format(root: Path) -> list[str]:
    """Rule: title, Covers line and the four sections, in order."""
    problems = []
    for doc in architecture_docs(root):
        text = read(root, doc)
        first = next((line for line in text.splitlines() if line.strip()), "")
        if not first.startswith("# "):
            problems.append(f"{doc}: must start with a '# Title' line.")
        covers = parse_covers(text)
        if covers is None:
            problems.append(
                f"{doc}: has no 'Covers:' line. Add 'Covers: <path>, <path>' "
                f"under the title."
            )
        elif not covers and Path(doc).name != "index.md":
            # An index.md may own nothing: the overview, or a directory whose
            # modules all have their own docs. The coverage rule still makes
            # sure every code file has an owner.
            problems.append(
                f"{doc}: 'Covers: nothing ...' is only valid in an index.md. "
                f"List the files this doc is the owner of."
            )
        titles = [
            m.group(2)
            for _, line in lines_outside_fences(text)
            if (m := HEADING.match(line)) and len(m.group(1)) == 2
        ]
        missing = [s for s in SECTIONS if s not in titles]
        if missing:
            problems.append(
                f"{doc}: missing section(s) {missing}. Every architecture doc has "
                f"these '## ' sections, in this order: {list(SECTIONS)}."
            )
        elif [titles.index(s) for s in SECTIONS] != sorted(
            titles.index(s) for s in SECTIONS
        ):
            problems.append(f"{doc}: sections are out of order. Use: {list(SECTIONS)}.")
    return problems


# --- Rules: coverage and placement -----------------------------------------------


def mirror_dir(source_dir: PurePosixPath) -> PurePosixPath:
    """Architecture directory documenting a source directory."""
    parts = source_dir.parts
    if parts[:1] == ("src",):
        parts = parts[1:]
    elif parts[:1] == (".github",):
        parts = ("ci", *parts[1:])
    return ARCH.joinpath(*parts)


def source_dir_for(root: Path, doc_dir: PurePosixPath) -> PurePosixPath:
    """Source directory that an architecture directory must mirror."""
    first, *rest = doc_dir.relative_to(ARCH).parts
    if first in ARCH_RENAMED:
        base = PurePosixPath(ARCH_RENAMED[first])
    elif (root / "src" / first).is_dir():
        base = PurePosixPath("src", first)
    else:
        base = PurePosixPath(first)
    return base.joinpath(*rest)


def owners_of(root: Path) -> dict[PurePosixPath, list[PurePosixPath]]:
    """Map each path named in a Covers line to the docs that name it."""
    owners: dict[PurePosixPath, list[PurePosixPath]] = {}
    for doc in architecture_docs(root):
        for path in {PurePosixPath(p) for p in parse_covers(read(root, doc)) or []}:
            owners.setdefault(path, []).append(doc)
    return owners


def check_code_coverage(root: Path) -> list[str]:
    """Rule: every code file has exactly one owner doc, at its mirrored path."""
    problems = []
    owners = owners_of(root)
    files = code_files(root)
    for file in files:
        expected_dir = mirror_dir(file.parent)
        docs = owners.get(file, [])
        if not docs:
            hint = f"{expected_dir / 'index.md'}"
            if file.name != "__init__.py":
                hint += f" (or to {expected_dir / file.stem}.md if it has its own doc)"
            problems.append(
                f"{file}: not named in the Covers line of any architecture doc. "
                f"Add it to {hint}."
            )
        elif len(docs) > 1:
            problems.append(
                f"{file}: named in the Covers line of {len(docs)} docs "
                f"({', '.join(map(str, docs))}). Keep it in exactly one."
            )
        elif docs[0].parent != expected_dir:
            problems.append(
                f"{file}: covered by {docs[0]}, but its doc must live in "
                f"{expected_dir}/ (docs mirror the source tree). Move the entry."
            )
        elif file.name == "__init__.py" and docs[0].name != "index.md":
            problems.append(
                f"{file}: covered by {docs[0]}, but a package's __init__.py belongs "
                f"to the package's index.md."
            )
    for directory in sorted({file.parent for file in files}):
        index = mirror_dir(directory) / "index.md"
        if not exists_exact(root, index):
            problems.append(
                f"{directory}/: holds code but {index} does not exist. Create it: "
                f"what the package is for, how its modules connect, its invariants."
            )
    return problems


def check_own_docs(root: Path, public_files: frozenset[PurePosixPath]) -> list[str]:
    """Rule: public or long modules have their own ``<module>.md`` doc."""
    problems = []
    owners = owners_of(root)
    for file in code_files(root):
        if file.name == "__init__.py":
            continue
        lines = len(read(root, file).splitlines())
        if file in public_files:
            reason = "exports public names (easy_viz.__all__)"
        elif lines > OWN_DOC_MIN_LINES:
            reason = f"has {lines} lines (more than {OWN_DOC_MIN_LINES})"
        else:
            continue
        doc = mirror_dir(file.parent) / f"{file.stem}.md"
        if doc not in owners.get(file, []):
            problems.append(
                f"{file}: {reason}, so it needs its own doc {doc} with the file in "
                f"its Covers line (move the module's section out of the package's "
                f"index.md into it) and a link to it from index.md."
            )
    for doc in architecture_docs(root):
        stem = doc.stem
        covered = {PurePosixPath(p) for p in parse_covers(read(root, doc)) or []}
        if doc.name != "index.md" and not any(
            c.suffix == ".py" and c.stem == stem for c in covered
        ):
            problems.append(
                f"{doc}: a doc named '{stem}.md' must cover the module '{stem}.py'. "
                f"Rename the doc after its module, or list the module in Covers."
            )
    return problems


def check_no_orphan_directories(root: Path) -> list[str]:
    """Rule: every architecture directory mirrors an existing source directory."""
    directories: set[PurePosixPath] = set()
    for doc in architecture_docs(root):
        directories.update(p for p in doc.parents if ARCH in p.parents)
    problems = []
    for directory in sorted(directories):
        source = source_dir_for(root, directory)
        if not (root / source).is_dir():
            problems.append(
                f"{directory}/: documents '{source}/', which does not exist. Delete "
                f"or move this doc directory (docs follow the code); a renamed "
                f"directory means a renamed doc directory."
            )
    return problems


def check_architecture_reachable(root: Path) -> list[str]:
    """Rule: each doc is linked from its parent index and reachable from the root."""
    docs = set(architecture_docs(root))
    if ARCH_INDEX not in docs:
        return [f"{ARCH_INDEX}: missing. It is the overview that links every doc."]
    links: dict[PurePosixPath, set[PurePosixPath]] = {}
    for doc in docs:
        targets = {
            resolve_relative(doc, re.split(r"[#?]", unquote(t), maxsplit=1)[0])
            for _, t in links_in(read(root, doc))
            if not EXTERNAL.match(t)
        }
        links[doc] = {t for t in targets if t in docs}
    reached, queue = {ARCH_INDEX}, deque([ARCH_INDEX])
    while queue:
        for target in links[queue.popleft()] - reached:
            reached.add(target)
            queue.append(target)
    problems = [
        f"{doc}: not reachable from {ARCH_INDEX}. Link it from its parent index.md."
        for doc in sorted(docs - reached)
    ]
    for doc in sorted(docs - {ARCH_INDEX}):
        parent = _parent_index(doc, docs)
        if parent is not None and doc not in links[parent]:
            problems.append(
                f"{doc}: not linked from {parent}. Every doc is linked from the "
                f"index.md of its directory (add a relative link and a one-line "
                f"description)."
            )
    return problems


def _parent_index(doc: PurePosixPath, docs: set[PurePosixPath]) -> PurePosixPath | None:
    """The index.md that must link ``doc``: same directory, or the nearest above."""
    directory = doc.parent.parent if doc.name == "index.md" else doc.parent
    while directory == ARCH or ARCH in directory.parents:
        if directory / "index.md" in docs:
            return directory / "index.md"
        directory = directory.parent
    return None


# --- Rules: plans and guide references -------------------------------------------


def check_plan_status(root: Path) -> list[str]:
    """Rule: every plan has a valid ``**Status:**``."""
    problems = []
    for plan in find_files(root, "docs/plans", lambda name: name.endswith(".md")):
        match = STATUS.search(read(root, plan))
        if match is None:
            problems.append(
                f"{plan}: no '**Status:** <status>' line. Add one of "
                f"{list(PLAN_STATUSES)} under the title."
            )
        elif match.group(1) not in PLAN_STATUSES:
            problems.append(
                f"{plan}: Status '{match.group(1)}' is not valid. Use one of "
                f"{list(PLAN_STATUSES)} (a finished plan is deleted, not marked)."
            )
    return problems


def check_no_guide_references(
    root: Path, files: list[PurePosixPath], exclude: frozenset[PurePosixPath]
) -> list[str]:
    """Rule: no file in ``files`` links to or names an agent guide's path.

    Guides are gitignored, so a reference would dangle for every other reader. Config
    files may *exclude* guides (bare names, ``**/`` globs); prose files may not even
    name them.
    """
    problems = []
    for file in files:
        if file in exclude or not (root / file).is_file():
            continue
        try:
            text = read(root, file)
        except (UnicodeDecodeError, OSError):
            continue  # binary file
        strict = file.suffix in STRICT_SUFFIXES
        for number, line in enumerate(text.splitlines(), start=1):
            if GUIDE_LINK.search(line):
                what = "links to an agent guide"
            elif GUIDE_PATH.search(line):
                what = "names the path of an agent guide"
            elif strict and GUIDE_NAME.search(line):
                what = "mentions an agent guide"
            else:
                continue
            problems.append(
                f"{file}:{number}: {what}. Guides are local-only and gitignored, so "
                f"the reference would dangle. Remove it (config files may only "
                f"exclude guides, e.g. a '**/' glob)."
            )
    return problems


def repository_files(root: Path) -> list[PurePosixPath] | None:
    """Files git tracks plus those it would track; None if git can't say."""
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return [PurePosixPath(p) for p in result.stdout.split("\0") if p]


# --- Rules: local guides (skipped when the root guide is absent) -----------------


def guides_on_disk(root: Path) -> list[PurePosixPath]:
    return find_files(root, ".", lambda name: name == "CLAUDE.md")


def check_guide_table(root: Path) -> list[str]:
    """Rule: the root guide's table lists exactly the guides that exist."""
    text = read(root, PurePosixPath("CLAUDE.md"))
    section = re.search(r"^## Guide system\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if section is None:
        return ["CLAUDE.md: no '## Guide system' section with the guide table."]
    listed = {
        PurePosixPath(m.group(1))
        for m in re.finditer(r"^\|\s*`([^`]+)`\s*\|", section.group(1), re.M)
    }
    on_disk = set(guides_on_disk(root))
    problems = [
        f"{guide}: exists but is not in the root guide's table. Add a row, or "
        f"delete the guide if it has no rules of its own."
        for guide in sorted(on_disk - listed)
    ]
    problems += [
        f"{guide}: listed in the root guide's table but missing on disk. Remove the "
        f"row, or restore the guide."
        for guide in sorted(listed - on_disk)
    ]
    return problems


def check_guide_links(root: Path) -> list[str]:
    """Rule: relative links and ``@imports`` inside guides resolve."""
    problems = []
    for guide in guides_on_disk(root):
        text = read(root, guide)
        references = links_in(text) + [
            (number, m.group(1).rstrip(".,;:"))
            for number, line in prose_lines(text)
            for m in IMPORT.finditer(line)
        ]
        for number, target in references:
            problem = link_problem(root, guide, target)
            if problem:
                problems.append(
                    f"{guide}:{number}: reference '{target}' {problem}. Fix the "
                    f"path (relative to the guide's own directory)."
                )
    return problems


# --- Tests on the real repository ------------------------------------------------


def public_module_files(root: Path) -> frozenset[PurePosixPath]:
    """Source files defining an object of ``easy_viz.__all__`` (``__init__`` aside)."""
    files = set()
    for name in easy_viz.__all__:
        module = getattr(getattr(easy_viz, name), "__module__", None)
        if isinstance(module, str):
            candidate = PurePosixPath("src", *module.split(".")).with_suffix(".py")
            if (root / candidate).is_file():
                files.add(candidate)
    return frozenset(files)


def assert_clean(problems: list[str]) -> None:
    assert not problems, "\n" + "\n".join(problems)


needs_local_guides = pytest.mark.skipif(
    not (ROOT / "CLAUDE.md").is_file(),
    reason="the root agent guide is absent (CI, fresh clone): guides are gitignored",
)


def test_relative_links_resolve() -> None:
    assert_clean(check_links(ROOT))


def test_covers_paths_exist() -> None:
    assert_clean(check_covers_exist(ROOT))


def test_architecture_docs_follow_the_format() -> None:
    assert_clean(check_doc_format(ROOT))


def test_every_code_file_has_exactly_one_owner_doc() -> None:
    assert_clean(check_code_coverage(ROOT))


def test_public_or_long_modules_have_their_own_doc() -> None:
    assert_clean(check_own_docs(ROOT, public_module_files(ROOT)))


def test_architecture_directories_mirror_source_directories() -> None:
    assert_clean(check_no_orphan_directories(ROOT))


def test_every_architecture_doc_is_reachable() -> None:
    assert_clean(check_architecture_reachable(ROOT))


def test_plans_have_a_valid_status() -> None:
    assert_clean(check_plan_status(ROOT))


def test_no_tracked_file_references_a_guide() -> None:
    files = repository_files(ROOT)
    if files is None:
        pytest.skip("git is unavailable or ROOT is not a git repository")
    assert_clean(check_no_guide_references(ROOT, files, frozenset({SELF})))


@needs_local_guides
def test_guides_match_the_root_table() -> None:
    assert_clean(check_guide_table(ROOT))


@needs_local_guides
def test_guide_links_resolve() -> None:
    assert_clean(check_guide_links(ROOT))


# --- The rules themselves, on small temporary trees ------------------------------


def doc(covers: str = "src/easy_viz/a.py", sections: tuple[str, ...] = SECTIONS) -> str:
    """A well-formed architecture doc."""
    body = "\n".join(f"## {s}\ntext\n" for s in sections)
    return f"# Title\n\nCovers: {covers}\n\n{body}"


def build(tmp_path: Path, files: dict[str, str]) -> Path:
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return tmp_path


def index(*links: str, covers: str = "nothing directly") -> str:
    """An overview or package index linking the given relative paths."""
    return doc(covers) + "\n" + "\n".join(f"[x]({link})" for link in links) + "\n"


def test_link_rule_catches_missing_target_wrong_case_and_root_links(
    tmp_path: Path,
) -> None:
    root = build(
        tmp_path,
        {
            "README.md": "[ok](docs/a.md) [web](https://x.io/Y) [top](#top)",
            "docs/a.md": (
                "[gone](missing.md)\n[case](B.md#sec)\n[root](/docs/b.md)\n"
                "[up](../../x.md)\n[ok](b.md#sec) [dir](../docs/)\n"
                "`[code](nope.md)`\n```\n[fenced](nope.md)\n```\n"
                "![img](pic.png)\n[ref]: gone.md\n"
            ),
            "docs/b.md": "text",
        },
    )
    problems = check_links(root)
    flagged = {p.split(": link ")[0] for p in problems}
    assert flagged == {
        "docs/a.md:1",
        "docs/a.md:2",
        "docs/a.md:3",
        "docs/a.md:4",
        "docs/a.md:10",
        "docs/a.md:11",
    }


def test_coverage_rule_requires_exactly_one_owner_at_the_mirrored_path(
    tmp_path: Path,
) -> None:
    root = build(
        tmp_path,
        {
            "src/easy_viz/__init__.py": "",
            "src/easy_viz/a.py": "",
            "src/easy_viz/b.py": "",
            "src/easy_viz/c.py": "",
            "src/easy_viz/theme/__init__.py": "",
            "src/easy_viz/theme/t.py": "",
            "docs/architecture/easy_viz/index.md": doc(
                "src/easy_viz/__init__.py, src/easy_viz/a.py, src/easy_viz/b.py, "
                "src/easy_viz/theme/t.py"
            ),
            "docs/architecture/easy_viz/b.md": doc("src/easy_viz/b.py"),
            "docs/architecture/easy_viz/theme/index.md": doc(
                "src/easy_viz/theme/__init__.py"
            ),
        },
    )
    problems = check_code_coverage(root)
    by_file = {p.split(":")[0]: p for p in problems}
    assert "named in the Covers line of 2 docs" in by_file["src/easy_viz/b.py"]
    assert "not named in the Covers line" in by_file["src/easy_viz/c.py"]
    assert (
        "must live in docs/architecture/easy_viz/theme/"
        in by_file["src/easy_viz/theme/t.py"]
    )
    assert "src/easy_viz/theme/__init__.py" not in by_file
    assert "src/easy_viz/a.py" not in by_file
    assert "src/easy_viz/__init__.py" not in by_file


def test_coverage_rule_ties_init_to_the_index_and_requires_an_index(
    tmp_path: Path,
) -> None:
    root = build(
        tmp_path,
        {
            "src/easy_viz/__init__.py": "",
            "scripts/build.py": "",
            "docs/architecture/easy_viz/other.md": doc("src/easy_viz/__init__.py"),
        },
    )
    problems = "\n".join(check_code_coverage(root))
    assert "a package's __init__.py belongs to the package's index.md" in problems
    assert "docs/architecture/easy_viz/index.md does not exist" in problems
    assert "scripts/build.py: not named" in problems
    assert "docs/architecture/scripts/index.md does not exist" in problems


def test_own_doc_rule_for_public_and_long_modules(tmp_path: Path) -> None:
    root = build(
        tmp_path,
        {
            "src/easy_viz/__init__.py": "\n" * 500,  # __init__ is never "long"
            "src/easy_viz/small.py": "x = 1\n",
            "src/easy_viz/long.py": "x = 1\n" * 151,
            "src/easy_viz/exact.py": "x = 1\n" * 150,
            "src/easy_viz/pub.py": "x = 1\n",
            "src/easy_viz/ok.py": "x = 1\n" * 200,
            "docs/architecture/easy_viz/ok.md": doc("src/easy_viz/ok.py"),
            "docs/architecture/easy_viz/index.md": doc("src/easy_viz/small.py"),
            "docs/architecture/easy_viz/misnamed.md": doc("src/easy_viz/exact.py"),
        },
    )
    problems = check_own_docs(root, frozenset({PurePosixPath("src/easy_viz/pub.py")}))
    flagged = {p.split(":")[0] for p in problems}
    assert flagged == {
        "src/easy_viz/long.py",
        "src/easy_viz/pub.py",
        "docs/architecture/easy_viz/misnamed.md",
    }


def test_orphan_rule_maps_directories_including_the_renamed_ci(tmp_path: Path) -> None:
    root = build(
        tmp_path,
        {
            "src/easy_viz/plots/p.py": "",
            "scripts/s.py": "",
            ".github/workflows/ci.yml": "",
            "docs/architecture/index.md": doc(),
            "docs/architecture/easy_viz/plots/index.md": doc(),
            "docs/architecture/scripts/index.md": doc(),
            "docs/architecture/ci/index.md": doc(".github/workflows/ci.yml"),
            "docs/architecture/easy_viz/stats/index.md": doc(),
            "docs/architecture/gallery/index.md": doc(),
        },
    )
    flagged = {p.split("/: ")[0] for p in check_no_orphan_directories(root)}
    assert flagged == {
        "docs/architecture/easy_viz/stats",
        "docs/architecture/gallery",
    }


def test_reachability_rule_requires_a_link_from_the_parent_index(
    tmp_path: Path,
) -> None:
    root = build(
        tmp_path,
        {
            "docs/architecture/index.md": index("easy_viz/index.md", "tests/index.md"),
            "docs/architecture/easy_viz/index.md": index("linked.md"),
            "docs/architecture/easy_viz/linked.md": doc(),
            "docs/architecture/easy_viz/forgotten.md": doc(),
            "docs/architecture/easy_viz/theme/index.md": doc(),
            # linked from the root overview, but not from its own directory's index
            "docs/architecture/tests/index.md": doc(),
            "docs/architecture/tests/extra.md": doc(),
        },
    )
    flagged = {p.split(": ")[0] for p in check_architecture_reachable(root)}
    assert flagged == {
        "docs/architecture/easy_viz/forgotten.md",
        "docs/architecture/easy_viz/theme/index.md",
        "docs/architecture/tests/extra.md",
    }


def test_format_rule_covers_line_forms_and_section_order(tmp_path: Path) -> None:
    root = build(
        tmp_path,
        {
            "docs/architecture/index.md": index(),  # "nothing directly" is allowed
            "docs/architecture/good.md": doc("a.py,\n  b.py"),
            "docs/architecture/nothing.md": doc("nothing directly"),
            "docs/architecture/scripts/index.md": doc("nothing directly"),
            "docs/architecture/no_covers.md": "# T\n## Responsibilities\n",
            "docs/architecture/missing.md": doc(sections=SECTIONS[:3]),
            "docs/architecture/order.md": doc(sections=SECTIONS[::-1]),
            "docs/architecture/no_title.md": doc().replace("# Title", "Title"),
        },
    )
    flagged = {p.split(": ")[0] for p in check_doc_format(root)}
    assert flagged == {
        "docs/architecture/nothing.md",
        "docs/architecture/no_covers.md",
        "docs/architecture/missing.md",
        "docs/architecture/order.md",
        "docs/architecture/no_title.md",
    }
    assert parse_covers("Covers: a.py,\n  `b.py`, c.py\n\nCovers: z.py") == [
        "a.py",
        "b.py",
        "c.py",
    ]
    assert parse_covers("```\nCovers: a.py\n```\n") is None


def test_covers_rule_flags_missing_paths_and_globs(tmp_path: Path) -> None:
    root = build(
        tmp_path,
        {
            "real.py": "",
            "docs/architecture/d.md": doc("real.py, Real.py, gone.py, *.py"),
        },
    )
    flagged = [p.split("'")[1] for p in check_covers_exist(root)]
    assert flagged == ["Real.py", "gone.py", "*.py"]


def test_plan_status_rule(tmp_path: Path) -> None:
    root = build(
        tmp_path,
        {
            "docs/plans/0001-a.md": "# P\n\n**Status:** in progress\n",
            "docs/plans/0002-b.md": "# P\n\n**Status:** done\n",
            "docs/plans/0003-c.md": "# P\n\nno status\n",
        },
    )
    flagged = {p.split(":")[0] for p in check_plan_status(root)}
    assert flagged == {"docs/plans/0002-b.md", "docs/plans/0003-c.md"}


def test_guide_reference_rule_separates_exclusion_from_reference(
    tmp_path: Path,
) -> None:
    # Built from parts so this file itself never contains a reference to scan.
    guide = "CLAUDE" + ".md"
    local = "CLAUDE" + ".local.md"
    files = {
        "pyproject.toml": f'exclude = ["**/{guide}", "{guide}", "{local}"]\n',
        ".gitignore": f"{guide}\n{local}\n.claude/\n",
        "docs/conf.py": f'exclude_patterns = ["{guide}"]\n',
        "README.md": "no reference\n",
        "docs/a.md": f"see src/easy_viz/{guide} for rules\n",
        "docs/b.md": f"[guide](../{guide})\n",
        "docs/c.md": f"the root {guide} says\n",
        "docs/d.md": f"[x](docs/{local})\n",
        "src/m.py": f'"""See ./{guide}."""\n',
        "docs/e.md": f"glob **/{guide} in config is fine in code only\n",
    }
    root = build(tmp_path, files)
    paths = [PurePosixPath(name) for name in files]
    flagged = {
        p.split(":")[0] for p in check_no_guide_references(root, paths, frozenset())
    }
    assert flagged == {
        "docs/a.md",
        "docs/b.md",
        "docs/c.md",
        "docs/d.md",
        "src/m.py",
        "docs/e.md",
    }
    excluded = check_no_guide_references(
        root, paths, frozenset(PurePosixPath(n) for n in files)
    )
    assert excluded == []


def test_guide_table_and_link_rules(tmp_path: Path) -> None:
    table = (
        "## Guide system\n| Guide | Covers |\n|---|---|\n"
        "| `CLAUDE.md` | root |\n| `src/CLAUDE.md` | src |\n| `gone/CLAUDE.md` | x |\n"
        "\n## Next\n| `other/CLAUDE.md` | not in the section |\n"
    )
    root = build(
        tmp_path,
        {
            "CLAUDE.md": table + "[ok](src/CLAUDE.md) [bad](nope.md)\n",
            "src/CLAUDE.md": "@../docs/conventions.md\n@../missing.md.\n`@../x/y.md`\n"
            "Use @pytest.mark.export and a@b.com\n",
            "docs/conventions.md": "",
            "docs/CLAUDE.md": "unlisted",
            ".venv/lib/CLAUDE.md": "ignored: hidden directory",
            "legacy/CLAUDE.md": "ignored: skipped directory",
        },
    )
    table_problems = "\n".join(check_guide_table(root))
    assert (
        "docs/CLAUDE.md: exists but is not in the root guide's table" in table_problems
    )
    assert (
        "gone/CLAUDE.md: listed in the root guide's table but missing" in table_problems
    )
    assert "other" not in table_problems and ".venv" not in table_problems
    link_problems = check_guide_links(root)
    assert [p.split(" reference ")[1].split("'")[1] for p in link_problems] == [
        "nope.md",
        "../missing.md",
    ]
