"""The built library contains the package and none of the agent files.

Agent guides (``CLAUDE.md``) and agent definitions (``.claude/``) are tracked in the
repository, some of them inside the package directory, but they are not part of the
library. ``source-exclude`` in ``pyproject.toml`` keeps them out of both the source
distribution and the wheel; this test builds both for real and looks inside.

It also keeps the package metadata PyPI shows in line with what CI tests.
"""

import re
import shutil
import subprocess
import tarfile
import tomllib
import zipfile
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

import pytest

ROOT = Path(__file__).resolve().parents[1]
AGENT_FILE_NAMES = frozenset({"CLAUDE.md", "CLAUDE.local.md"})


def agent_files(names: Iterable[str]) -> list[str]:
    """Return the archive entries that are agent guides or agent definitions."""
    return [
        name
        for name in names
        if PurePosixPath(name).name in AGENT_FILE_NAMES
        or ".claude" in PurePosixPath(name).parts
    ]


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[list[str], list[str]]:
    """Build the sdist and the wheel; return the entry names of (sdist, wheel)."""
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is not on PATH, so the package cannot be built")
    out = tmp_path_factory.mktemp("dist")
    subprocess.run(
        [uv, "build", "--quiet", "--out-dir", str(out), str(ROOT)],
        check=True,
        capture_output=True,
    )
    (sdist,) = out.glob("*.tar.gz")
    (wheel,) = out.glob("*.whl")
    with tarfile.open(sdist) as archive:
        sdist_names = archive.getnames()
    with zipfile.ZipFile(wheel) as archive:
        wheel_names = archive.namelist()
    return sdist_names, wheel_names


def test_the_repository_has_agent_files_to_exclude() -> None:
    # Without them the build checks below would pass for the wrong reason.
    assert (ROOT / "src" / "easy_viz" / "CLAUDE.md").is_file()
    assert (ROOT / ".claude" / "agents").is_dir()


def test_wheel_holds_the_package_and_no_agent_file(
    built: tuple[list[str], list[str]],
) -> None:
    _, wheel = built
    assert {"easy_viz/__init__.py", "easy_viz/py.typed"} <= set(wheel)
    assert agent_files(wheel) == [], "Add them to source-exclude in pyproject.toml."


def test_sdist_holds_the_package_and_no_agent_file(
    built: tuple[list[str], list[str]],
) -> None:
    sdist, _ = built
    assert any(name.endswith("/src/easy_viz/__init__.py") for name in sdist)
    assert agent_files(sdist) == [], "Add them to source-exclude in pyproject.toml."


def test_python_classifiers_match_the_ci_matrix() -> None:
    # PyPI shows the classifiers as the supported versions; CI is what tests them.
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    classifiers = {
        c.removeprefix("Programming Language :: Python :: ")
        for c in project["project"]["classifiers"]
        if re.fullmatch(r"Programming Language :: Python :: 3\.\d+", c)
    }
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    matrix = re.search(r"python-version: \[(.*?)\]", ci)
    assert matrix is not None
    assert classifiers == set(re.findall(r"\"([\d.]+)\"", matrix[1]))


def test_agent_file_detector() -> None:
    names = [
        "easy_viz/CLAUDE.md",
        "pkg-1.0/CLAUDE.local.md",
        "pkg-1.0/.claude/agents/code-reviewer.md",
        "easy_viz/claude_md.py",
        "easy_viz/docs/NOT_CLAUDE.md",
        "easy_viz/__init__.py",
    ]
    assert agent_files(names) == names[:3]
