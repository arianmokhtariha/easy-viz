"""Layering rules between the library's sub-packages.

* ``stats/`` is pure computation: it never imports ``plotly`` or ``easy_viz.plots``.
* ``theme/`` never imports ``easy_viz.plots``.

Imports are read with ``ast``, so every form is seen: ``import x``,
``from x import y``, relative imports, and imports inside functions or under
``if TYPE_CHECKING``. A rule whose directory does not exist yet holds vacuously.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
PACKAGE = "easy_viz"

# Sub-package of ``easy_viz`` -> module prefixes it must never import.
FORBIDDEN: dict[str, tuple[str, ...]] = {
    "stats": ("plotly", "easy_viz.plots"),
    "theme": ("easy_viz.plots",),
}


def module_name(path: Path, src: Path) -> str:
    """Dotted module name of ``path`` (``src/easy_viz/a/x.py`` -> ``easy_viz.a.x``)."""
    parts = list(path.relative_to(src).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imported_modules(
    source: str, module: str, is_package: bool
) -> list[tuple[int, str]]:
    """List every ``(line, imported module)`` pair in ``source``.

    ``from a import b`` yields both ``a`` and ``a.b``, because ``b`` may be a
    submodule (``from easy_viz import plots``). Relative imports are resolved
    against ``module`` (the importing module's dotted name).
    """
    package = module if is_package else module.rpartition(".")[0]
    found: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                anchor = package.split(".")[
                    : len(package.split(".")) - (node.level - 1)
                ]
                base = ".".join([*anchor, *([base] if base else [])])
            found.append((node.lineno, base))
            found.extend(
                (node.lineno, f"{base}.{alias.name}")
                for alias in node.names
                if alias.name != "*"
            )
    return sorted(found)


def matching_prefix(module: str, prefixes: tuple[str, ...]) -> str | None:
    """Return the forbidden prefix that ``module`` equals or sits under."""
    for prefix in prefixes:
        if module == prefix or module.startswith(prefix + "."):
            return prefix
    return None


def layering_violations(src: Path, subpackage: str) -> list[str]:
    """Describe every forbidden import in ``src/easy_viz/<subpackage>/``."""
    prefixes = FORBIDDEN[subpackage]
    messages: list[str] = []
    for path in sorted((src / PACKAGE / subpackage).rglob("*.py")):
        seen: set[tuple[int, str]] = set()
        module = module_name(path, src)
        imports = imported_modules(
            path.read_text(encoding="utf-8"), module, path.name == "__init__.py"
        )
        for line, imported in imports:
            prefix = matching_prefix(imported, prefixes)
            if prefix is None or (line, prefix) in seen:
                continue
            seen.add((line, prefix))
            messages.append(
                f"{path.relative_to(src.parent).as_posix()}:{line}: imports "
                f"'{imported}', but {subpackage}/ must never import '{prefix}'. "
                f"Move the shared code into a '_'-prefixed internal module (or the "
                f"layer below) and import it from there."
            )
    return messages


@pytest.mark.parametrize("subpackage", sorted(FORBIDDEN))
def test_subpackage_respects_layering(subpackage: str) -> None:
    violations = layering_violations(SRC, subpackage)
    assert not violations, "\n" + "\n".join(violations)


@pytest.mark.parametrize(
    ("source", "module", "is_package", "expected"),
    [
        pytest.param(
            "import plotly", "easy_viz.stats.a", False, ["plotly"], id="import"
        ),
        pytest.param(
            "import plotly.graph_objects as go",
            "easy_viz.stats.a",
            False,
            ["plotly.graph_objects"],
            id="import-as",
        ),
        pytest.param(
            "from plotly import graph_objects",
            "easy_viz.stats.a",
            False,
            ["plotly", "plotly.graph_objects"],
            id="from-import-submodule",
        ),
        pytest.param(
            "from easy_viz import plots",
            "easy_viz.theme.a",
            False,
            ["easy_viz", "easy_viz.plots"],
            id="from-package-import-submodule",
        ),
        pytest.param(
            "def f():\n    import plotly\n",
            "easy_viz.stats.a",
            False,
            ["plotly"],
            id="inside-function",
        ),
        pytest.param(
            "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n"
            "    from easy_viz.plots import bar\n",
            "easy_viz.stats.a",
            False,
            ["easy_viz.plots", "easy_viz.plots.bar", "typing", "typing.TYPE_CHECKING"],
            id="type-checking-block",
        ),
        pytest.param(
            "from .. import plots",
            "easy_viz.stats.a",
            False,
            ["easy_viz", "easy_viz.plots"],
            id="relative-two-up",
        ),
        pytest.param(
            "from ..plots import bar",
            "easy_viz.stats.a",
            False,
            ["easy_viz.plots", "easy_viz.plots.bar"],
            id="relative-sibling-package",
        ),
        pytest.param(
            "from . import plots",
            "easy_viz.theme",
            True,
            ["easy_viz.theme", "easy_viz.theme.plots"],
            id="relative-in-init",
        ),
        pytest.param(
            "from numpy import *",
            "easy_viz.stats.a",
            False,
            ["numpy"],
            id="star-import",
        ),
    ],
)
def test_import_detector_sees_every_form(
    source: str, module: str, is_package: bool, expected: list[str]
) -> None:
    found = [imported for _, imported in imported_modules(source, module, is_package)]
    assert sorted(found) == sorted(expected)


@pytest.mark.parametrize(
    ("module", "forbidden"),
    [
        ("plotly", True),
        ("plotly.graph_objects", True),
        ("plotlyx", False),  # shares a prefix as text only, not as a package
        ("easy_viz.plots", True),
        ("easy_viz.plots.bar", True),
        ("easy_viz.plots_helper", False),
        ("easy_viz._layout", False),
    ],
)
def test_prefix_matching_respects_package_boundaries(
    module: str, forbidden: bool
) -> None:
    prefixes = ("plotly", "easy_viz.plots")
    assert (matching_prefix(module, prefixes) is not None) is forbidden


def test_violations_name_file_line_and_import(tmp_path: Path) -> None:
    package = tmp_path / "src" / PACKAGE / "stats"
    package.mkdir(parents=True)
    (package / "bad.py").write_text(
        "import numpy\n\n\ndef f() -> None:\n    import plotly.express\n",
        encoding="utf-8",
    )
    (package / "good.py").write_text("import numpy\n", encoding="utf-8")

    violations = layering_violations(tmp_path / "src", "stats")

    assert len(violations) == 1
    assert violations[0].startswith(
        "src/easy_viz/stats/bad.py:5: imports 'plotly.express'"
    )
