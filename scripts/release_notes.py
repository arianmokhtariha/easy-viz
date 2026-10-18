"""Print the GitHub release body of one version, taken from ``CHANGELOG.md``.

The release workflow (``.github/workflows/release.yml``) runs it before building,
so a version without a valid changelog section never reaches PyPI::

    uv run --no-project python scripts/release_notes.py 0.2.0 --repo owner/name

The changelog has a strict format, so every release body has the same structure
(decision 0013). The whole file is checked, not only the requested version:

- ``## Unreleased`` comes first. It may be empty or hold sections.
- Each release is ``## X.Y.Z - YYYY-MM-DD``, newest first. Versions strictly
  decrease and dates never increase.
- Under a release heading: a summary, one paragraph of plain prose. Then at least
  one ``###`` section, using only the names in ``SECTIONS``, in that order. Each
  section is a non-empty bullet list.

The body is the summary and the sections as written, plus a fixed footer: the
install command and a link to every commit since the previous release.

Stdlib only: CI runs it without installing the project.
"""

import argparse
import datetime
import re
import sys
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
UNRELEASED = "Unreleased"
# The only section names a release may use, in the order they must appear.
SECTIONS = (
    "Added",
    "Changed",
    "Deprecated",
    "Removed",
    "Fixed",
    "Security",
    "Internal",
)
RELEASE_HEADING = re.compile(r"(\d+)\.(\d+)\.(\d+) - (\d{4}-\d{2}-\d{2})")


class ChangelogError(ValueError):
    """The changelog breaks its format; the message says where and how to fix it."""


@dataclass(frozen=True)
class Release:
    """One ``##`` entry of the changelog."""

    version: str  # "Unreleased" or "X.Y.Z"
    date: datetime.date | None  # None for Unreleased
    summary: str
    sections: tuple[tuple[str, str], ...]  # (name, bullet list) in file order


def _split(text: str, marker: str) -> tuple[str, list[tuple[str, str]]]:
    """Split ``text`` at lines starting with ``marker``: (preamble, [(title, body)])."""
    preamble: list[str] = []
    parts: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        if line.startswith(marker):
            parts.append((line.removeprefix(marker).strip(), []))
        elif parts:
            parts[-1][1].append(line)
        else:
            preamble.append(line)
    return "\n".join(preamble).strip(), [(t, "\n".join(b).strip()) for t, b in parts]


def _check_sections(heading: str, sections: list[tuple[str, str]]) -> None:
    """Raise unless the ``###`` sections are known, in order, and bullet lists."""
    names = [name for name, _ in sections]
    for name in names:
        if name not in SECTIONS:
            raise ChangelogError(
                f"## {heading}: unknown section '### {name}'. "
                f"Use one of: {', '.join(SECTIONS)}."
            )
    if names != sorted(names, key=SECTIONS.index) or len(set(names)) < len(names):
        raise ChangelogError(
            f"## {heading}: sections are {', '.join(names)}. Use each at most once, "
            f"in this order: {', '.join(SECTIONS)}."
        )
    for name, body in sections:
        lines = [line for line in body.splitlines() if line.strip()]
        if not lines:
            raise ChangelogError(f"## {heading}: '### {name}' is empty. Remove it.")
        # A bullet's continuation lines are indented under it.
        if not lines[0].startswith("- ") or any(
            not (line.startswith("- ") or line.startswith("  ")) for line in lines
        ):
            raise ChangelogError(
                f"## {heading}: '### {name}' must be a bullet list ('- ' items)."
            )


def parse_changelog(text: str) -> list[Release]:
    """Parse and check the whole changelog; return its entries, newest first."""
    _, entries = _split(text, "## ")
    if not entries or entries[0][0] != UNRELEASED:
        raise ChangelogError(f"The first entry must be '## {UNRELEASED}'.")
    releases: list[Release] = []
    for heading, body in entries:
        summary, sections = _split(body, "### ")
        _check_sections(heading, sections)
        if heading == UNRELEASED:
            if releases:
                raise ChangelogError(f"'## {UNRELEASED}' must appear only once, first.")
            if summary:
                raise ChangelogError(
                    f"## {UNRELEASED}: text before the first section. The summary is "
                    "written when the version is released."
                )
            releases.append(Release(UNRELEASED, None, "", tuple(sections)))
            continue
        match = RELEASE_HEADING.fullmatch(heading)
        if match is None:
            raise ChangelogError(
                f"'## {heading}': a release heading is '## X.Y.Z - YYYY-MM-DD'."
            )
        try:
            date = datetime.date.fromisoformat(match[4])
        except ValueError as error:
            raise ChangelogError(f"## {heading}: {match[4]} is not a date.") from error
        if not summary or "\n\n" in summary or summary.startswith(("- ", "#")):
            raise ChangelogError(
                f"## {heading}: start with a summary of the release, one paragraph "
                "of prose, before the first section."
            )
        if not sections:
            raise ChangelogError(f"## {heading}: a release needs at least one section.")
        version = f"{match[1]}.{match[2]}.{match[3]}"
        previous = releases[-1]
        if previous.date is not None:
            if _key(version) >= _key(previous.version):
                raise ChangelogError(
                    f"## {heading} follows {previous.version}: versions must "
                    "decrease from the top."
                )
            if date > previous.date:
                raise ChangelogError(
                    f"## {heading} is dated after {previous.version}, which is above "
                    "it. Newest release first."
                )
        releases.append(Release(version, date, summary, tuple(sections)))
    return releases


def _key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def release_body(
    releases: Sequence[Release], version: str, repo: str, package: str
) -> str:
    """Return the GitHub release body of ``version``: its entry plus a footer."""
    released = [r for r in releases if r.version != UNRELEASED]
    versions = [r.version for r in released]
    if version not in versions:
        raise ChangelogError(
            f"CHANGELOG.md has no '## {version} - YYYY-MM-DD' entry. Move the "
            f"'## {UNRELEASED}' notes under it before releasing."
        )
    index = versions.index(version)
    release = released[index]
    if index + 1 < len(released):
        changes = (
            f"https://github.com/{repo}/compare/"
            f"v{released[index + 1].version}...v{version}"
        )
    else:
        changes = f"https://github.com/{repo}/commits/v{version}"
    sections = "\n\n".join(f"### {name}\n{body}" for name, body in release.sections)
    return (
        f"{release.summary}\n\n{sections}\n\n---\n\n"
        f"Install or upgrade: `pip install --upgrade {package}`\n\n"
        f"Full list of changes: {changes}\n"
    )


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Read the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", help="the version to release, e.g. 0.2.0")
    parser.add_argument("--repo", required=True, help="GitHub repository, owner/name")
    parser.add_argument("--changelog", type=Path, default=REPO / "CHANGELOG.md")
    parser.add_argument("--pyproject", type=Path, default=REPO / "pyproject.toml")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Print the release body, or exit with the changelog's format error."""
    args = parse_args(argv)
    package = tomllib.loads(args.pyproject.read_text(encoding="utf-8"))["project"]
    try:
        releases = parse_changelog(args.changelog.read_text(encoding="utf-8"))
        body = release_body(releases, args.version, args.repo, package["name"])
    except ChangelogError as error:
        raise SystemExit(f"release_notes: {error}") from error
    sys.stdout.write(body)


if __name__ == "__main__":
    main()
