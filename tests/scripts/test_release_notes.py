"""``scripts/release_notes.py``: the changelog format and the release body.

The real ``CHANGELOG.md`` is checked on every run, so a pull request that breaks
its format fails here, long before a release would.
"""

import pytest
from conftest import ROOT, load_script

notes = load_script("release_notes")

INTRO = "# Changelog\n\nIntro text.\n\n"
CHANGELOG = INTRO + (
    "## Unreleased\n\n### Fixed\n- a fix not released yet\n\n"
    "## 0.2.0 - 2026-11-02\n\nFaster and steadier.\n\n"
    "### Added\n- `pie_plot`\n  with a hole option\n\n"
    "### Internal\n- CI on macOS\n\n"
    "## 0.1.0 - 2026-10-18\n\nThe first release.\n\n### Added\n- `bar_plot`\n"
)


def body(version: str) -> str:
    releases = notes.parse_changelog(CHANGELOG)
    return str(notes.release_body(releases, version, "me/repo", "easy-viz"))


def test_the_real_changelog_follows_the_format() -> None:
    notes.parse_changelog((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))


def test_body_is_the_entry_plus_a_link_to_the_previous_release() -> None:
    text = body("0.2.0")
    assert text.startswith("Faster and steadier.\n\n### Added\n- `pie_plot`\n  with")
    assert "### Internal\n- CI on macOS" in text
    assert "not released yet" not in text and "`bar_plot`" not in text
    assert "pip install --upgrade easy-viz" in text
    assert text.endswith("https://github.com/me/repo/compare/v0.1.0...v0.2.0\n")


def test_first_release_links_to_its_commits() -> None:
    assert body("0.1.0").endswith("https://github.com/me/repo/commits/v0.1.0\n")


def test_a_version_without_an_entry_is_refused() -> None:
    with pytest.raises(notes.ChangelogError, match=r"no '## 0\.3\.0"):
        body("0.3.0")


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("### Added\n- `pie_plot`", "### New\n- `pie_plot`", "unknown section"),
        (
            "### Added\n- `pie_plot`\n  with a hole option\n\n### Internal\n- CI",
            "### Internal\n- CI on macOS\n\n### Added\n- `pie_plot`",
            "in this order",
        ),
        ("Faster and steadier.\n\n", "", "summary"),
        ("Faster and steadier.", "One.\n\nTwo.", "summary"),
        ("### Internal\n- CI on macOS", "### Internal\n", "empty"),
        ("### Internal\n- CI on macOS", "### Internal\nCI on macOS", "bullet list"),
        ("## 0.2.0 - 2026-11-02", "## 0.0.9 - 2026-11-02", "decrease"),
        ("## 0.2.0 - 2026-11-02", "## 0.2.0 - 2026-10-01", "Newest release first"),
        ("## 0.2.0 - 2026-11-02", "## 0.2.0 (2026-11-02)", "X.Y.Z - YYYY-MM-DD"),
        ("## 0.2.0 - 2026-11-02", "## 0.2.0 - 2026-13-02", "not a date"),
        ("## Unreleased\n\n", "## Unreleased\n\nA note.\n\n", "Unreleased"),
        # Two pull requests that each add a "### Fixed" merge into duplicates.
        (
            "### Fixed\n- a fix",
            "### Fixed\n- one\n\n### Fixed\n- a fix",
            "at most once",
        ),
        ("## 0.1.0 - ", "## Unreleased\n\n## 0.1.0 - ", "only once"),
        (
            "The first release.\n\n### Added\n- `bar_plot`\n",
            "The first release.\n",
            "at least one",
        ),
    ],
)
def test_format_errors_are_refused(old: str, new: str, message: str) -> None:
    assert old in CHANGELOG
    with pytest.raises(notes.ChangelogError, match=message):
        notes.parse_changelog(CHANGELOG.replace(old, new, 1))


def test_unreleased_must_come_first() -> None:
    text = CHANGELOG.replace(
        "## Unreleased\n\n### Fixed\n- a fix not released yet\n\n", ""
    )
    with pytest.raises(notes.ChangelogError, match="first entry"):
        notes.parse_changelog(text)
