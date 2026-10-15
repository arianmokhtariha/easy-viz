"""Repository-wide checks that the gallery matches the library.

The gallery is the visual guide to every public plot function and the source of the
README images (``gallery/CLAUDE.md``). Each rule is a pure function that takes the
repository root and returns a list of problems (empty when it holds); each problem
names the file, the broken rule and the fix. The tests run every rule on the real
repository, and on small temporary trees that prove the rule fails when it should.

Rules
-----
* Every public plot function (a callable in ``easy_viz.__all__`` defined under
  ``easy_viz.plots``) has ``gallery/<family>/<function>.ipynb``, where the family is
  the last part of its module, and ``gallery/README.md`` links to it.
* Every keyword-only parameter of the function is passed to that function
  (``ev.bar_plot(..., top_n=5)``) in a code cell of its notebook. Prose, plain
  assignments and other calls (``fig.update_layout(title=...)``) do not count: the
  option must be shown working.
* Every gallery notebook is linked from ``gallery/README.md``.
* Every gallery notebook is committed executed: each non-empty code cell has an
  execution count, no output is an error, and every Plotly figure output also
  carries a static ``image/png`` (GitHub cannot display the interactive one).
* README images: links into ``docs/images/readme/`` from ``README.md`` and
  ``gallery/README.md`` resolve; every ``readme:<name>`` tag has its
  ``docs/images/readme/<name>.png``; every PNG there comes from a tag; tag names are
  unique.

Gallery notebooks are ``gallery/**/*.ipynb`` except names starting with ``_`` (the
template). The rules that need a plot function skip on the real repository while
none exists; the others pass while the gallery is empty and enforce as soon as files
appear.
"""

import ast
import inspect
import re
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath

import nbformat
import pytest
from conftest import load_script, public_plot_functions
from nbformat import NotebookNode
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook, new_output
from test_knowledge_base import exists_exact, links_in, resolve_relative

build = load_script("build_gallery")

ROOT = Path(__file__).resolve().parents[1]
INDEX = PurePosixPath("gallery/README.md")
README_IMAGES = PurePosixPath("docs/images/readme")
IMAGE_LINK_SOURCES = (PurePosixPath("README.md"), INDEX)
HTML_SRC = re.compile(r"""\bsrc\s*=\s*["']([^"']+)["']""")
REBUILD = f"Re-run {build.BUILD_COMMAND} --only {{stem}}"
NO_FUNCTIONS = (
    "No public plot function exists yet, so there is no function notebook to check."
)

PlotFunctions = Mapping[str, Callable[..., object]]


# --- Reading ---------------------------------------------------------------------


def family(function: Callable[..., object]) -> str:
    """Gallery folder of a plot function: the last part of its module."""
    module: str = function.__module__
    return module.rsplit(".", 1)[-1]


def notebook_for(name: str, function: Callable[..., object]) -> PurePosixPath:
    return PurePosixPath("gallery", family(function), f"{name}.ipynb")


def read_notebook(root: Path, rel: PurePosixPath) -> NotebookNode:
    nb: NotebookNode = nbformat.read(root / rel, as_version=4)
    return nb


def index_links(root: Path) -> set[PurePosixPath]:
    """Repository paths that ``gallery/README.md`` links to."""
    if not (root / INDEX).is_file():
        return set()
    text = (root / INDEX).read_text(encoding="utf-8")
    targets = {resolve_relative(INDEX, t.split("#")[0]) for _, t in links_in(text)}
    return {t for t in targets if t is not None}


def keywords_passed_to(nb: NotebookNode, function: str) -> set[str]:
    """Keyword names given to calls of ``function``: ``ev.f(...)`` or ``f(...)``."""
    used: set[str] = set()
    for cell in nb.cells:
        if cell.cell_type != "code":
            continue
        # IPython magics and shell escapes are not Python syntax.
        source = "\n".join(
            line
            for line in cell.source.splitlines()
            if not line.lstrip().startswith(("%", "!"))
        )
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call):
                continue
            callee = node.func
            if isinstance(callee, ast.Attribute):
                called = callee.attr
            elif isinstance(callee, ast.Name):
                called = callee.id
            else:
                continue
            if called == function:
                used.update(k.arg for k in node.keywords if k.arg is not None)
    return used


# --- Rules -----------------------------------------------------------------------


def check_function_notebooks(root: Path, functions: PlotFunctions) -> list[str]:
    """Rule: each plot function has its notebook, linked from the gallery index."""
    problems = []
    linked = index_links(root)
    for name, function in sorted(functions.items()):
        notebook = notebook_for(name, function)
        if not (root / notebook).is_file():
            problems.append(
                f"{notebook}: missing. Every public plot function has a gallery "
                f"notebook: copy gallery/_template.ipynb there, fill it in and run "
                f"{build.BUILD_COMMAND} --only {name}."
            )
        if notebook not in linked:
            problems.append(
                f"{INDEX}: no link to {notebook}. Add the function's row to the "
                f"gallery index."
            )
    return problems


def check_keyword_parameters(root: Path, functions: PlotFunctions) -> list[str]:
    """Rule: every keyword-only parameter is passed to the function in a code cell."""
    problems = []
    for name, function in sorted(functions.items()):
        notebook = notebook_for(name, function)
        if not (root / notebook).is_file():
            continue  # reported by check_function_notebooks
        used = keywords_passed_to(read_notebook(root, notebook), name)
        missing = [
            p.name
            for p in inspect.signature(function).parameters.values()
            if p.kind is inspect.Parameter.KEYWORD_ONLY and p.name not in used
        ]
        if missing:
            problems.append(
                f"{notebook}: never passes the keyword parameter(s) {missing} to "
                f"{name}. Show each one in a call such as ev.{name}(..., "
                f"{missing[0]}=...) in the Parameter tour (markdown, assignments "
                f"and other calls do not count)."
            )
    return problems


def check_notebooks_linked(root: Path) -> list[str]:
    """Rule: the gallery index links every gallery notebook."""
    linked = index_links(root)
    return [
        f"{notebook}: not linked from {INDEX}. Add a row for it to the index."
        for notebook in build.discover_notebooks(root)
        if notebook not in linked
    ]


def check_notebooks_executed(root: Path) -> list[str]:
    """Rule: notebooks are committed executed, with a PNG next to every figure."""
    problems = []
    for notebook in build.discover_notebooks(root):
        fix = REBUILD.format(stem=notebook.stem)
        for index, cell in enumerate(read_notebook(root, notebook).cells):
            if cell.cell_type != "code" or not cell.source.strip():
                continue
            where = f"{notebook}, cell {index}"
            if cell.execution_count is None:
                problems.append(f"{where}: not executed. {fix}.")
            for output in cell.outputs:
                if output.output_type == "error":
                    problems.append(
                        f"{where}: has an error output ({output.ename}). Fix the "
                        f"cell, then {fix[0].lower()}{fix[1:]}."
                    )
                data = output.get("data", {})
                if build.PLOTLY_MIME in data and build.PNG_MIME not in data:
                    problems.append(
                        f"{where}: a figure without its static image/png, so "
                        f"GitHub shows nothing. {fix}."
                    )
    return problems


def check_readme_images(root: Path) -> list[str]:
    """Rule: README image links resolve, and tags and PNGs match one to one."""
    problems = []
    for source in IMAGE_LINK_SOURCES:
        if not (root / source).is_file():
            continue
        text = (root / source).read_text(encoding="utf-8")
        targets = [t for _, t in links_in(text)] + HTML_SRC.findall(text)
        for target in targets:
            resolved = resolve_relative(source, target.split("#")[0])
            if (
                resolved is not None
                and README_IMAGES in resolved.parents
                and not exists_exact(root, resolved)
            ):
                problems.append(
                    f"{source}: image '{target}' does not exist. README images come "
                    f"from cells tagged readme:<name>: tag the cell and run "
                    f"{build.BUILD_COMMAND}, or fix the link."
                )
    tags: dict[str, PurePosixPath] = {}
    for notebook in build.discover_notebooks(root):
        for index, cell in enumerate(read_notebook(root, notebook).cells):
            for name in build.readme_tags(cell):
                if name in tags:
                    problems.append(
                        f"{notebook}, cell {index}: tag 'readme:{name}' is also used "
                        f"in {tags[name]}. README image names are unique: rename one."
                    )
                    continue
                tags[name] = notebook
                if not exists_exact(root, README_IMAGES / f"{name}.png"):
                    problems.append(
                        f"{notebook}, cell {index}: tag 'readme:{name}' has no "
                        f"{README_IMAGES}/{name}.png. "
                        f"{REBUILD.format(stem=notebook.stem)}."
                    )
    folder = root / README_IMAGES
    images = sorted(folder.glob("*.png")) if folder.is_dir() else []
    problems += [
        f"{README_IMAGES}/{image.name}: no notebook cell is tagged "
        f"'readme:{image.stem}'. README images are generated, never added by hand: "
        f"tag the cell that makes it, or delete the file (a full run of "
        f"{build.BUILD_COMMAND} removes it)."
        for image in images
        if image.stem not in tags
    ]
    return problems


# --- Tests on the real repository ------------------------------------------------


def assert_clean(problems: list[str]) -> None:
    assert not problems, "\n" + "\n".join(problems)


@pytest.fixture
def functions() -> PlotFunctions:
    found = public_plot_functions()
    if not found:
        pytest.skip(NO_FUNCTIONS)
    return found


def test_every_plot_function_has_a_linked_notebook(functions: PlotFunctions) -> None:
    assert_clean(check_function_notebooks(ROOT, functions))


def test_every_keyword_parameter_appears_in_its_notebook(
    functions: PlotFunctions,
) -> None:
    assert_clean(check_keyword_parameters(ROOT, functions))


def test_every_notebook_is_linked_from_the_index() -> None:
    assert_clean(check_notebooks_linked(ROOT))


def test_notebooks_are_committed_executed() -> None:
    assert_clean(check_notebooks_executed(ROOT))


def test_readme_images_match_their_tags() -> None:
    assert_clean(check_readme_images(ROOT))


# --- The rules themselves, on small temporary trees ------------------------------


def bar_plot(
    df: object,
    x: str,
    *,
    color: str | None = None,
    top_n: int | None = None,
    title: str | None = None,
) -> None:
    """A stand-in plot function in the ``comparison`` family."""


bar_plot.__module__ = "easy_viz.plots.comparison"
FAKE = {"bar_plot": bar_plot}
BAR = PurePosixPath("gallery/comparison/bar_plot.ipynb")
PLOTLY = {"data": [], "layout": {}}


def figure(*, png: bool = True) -> NotebookNode:
    data: dict[str, object] = {build.PLOTLY_MIME: PLOTLY}
    if png:
        data[build.PNG_MIME] = "iVBORw0KGgo="
    return new_output("display_data", data=data)


def code(
    source: str, *outputs: NotebookNode, tags: tuple[str, ...] = ()
) -> NotebookNode:
    cell = new_code_cell(source, execution_count=1, outputs=list(outputs))
    if tags:
        cell.metadata["tags"] = list(tags)
    return cell


def build_tree(
    tmp_path: Path,
    notebooks: Mapping[str, list[NotebookNode]],
    files: Mapping[str, str] | None = None,
) -> Path:
    for name, cells in notebooks.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        nbformat.write(new_notebook(cells=cells), path)
    for name, content in (files or {}).items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return tmp_path


def test_function_rule_needs_the_notebook_in_its_family_and_a_link(
    tmp_path: Path,
) -> None:
    # In the wrong family folder, and the index links a different file.
    root = build_tree(
        tmp_path,
        {"gallery/trend/bar_plot.ipynb": []},
        {str(INDEX): "[bar_plot](trend/bar_plot.ipynb)\n"},
    )
    problems = check_function_notebooks(root, FAKE)
    assert len(problems) == 2
    assert problems[0].startswith(f"{BAR}: missing")
    assert f"no link to {BAR}" in problems[1]

    build_tree(
        tmp_path, {str(BAR): []}, {str(INDEX): "[bar_plot](comparison/bar_plot.ipynb)"}
    )
    assert check_function_notebooks(root, FAKE) == []


def test_keyword_rule_counts_only_keywords_passed_to_the_function(
    tmp_path: Path,
) -> None:
    cells = [
        new_markdown_cell("Use `top_n=5` to keep the largest categories."),
        code('%matplotlib inline\nev.bar_plot(df, "region", color="segment")'),
        code("assert top_n == 3"),  # a comparison is not an option being used
        code("top_n = 5"),  # nor a plain assignment
        # nor a keyword of the same name given to another call (Plotly's title)
        code('fig.update_layout(title="Revenue")\nfig.update_traces(top_n=1)'),
    ]
    root = build_tree(tmp_path, {str(BAR): cells})
    problems = check_keyword_parameters(root, FAKE)
    assert len(problems) == 1
    assert "['top_n', 'title']" in problems[0]  # not color, not the positional x


def test_index_rule_flags_unlinked_notebooks_but_not_the_template(
    tmp_path: Path,
) -> None:
    root = build_tree(
        tmp_path,
        {
            str(BAR): [],
            "gallery/meet_the_data.ipynb": [],
            "gallery/_template.ipynb": [],
        },
        {str(INDEX): "[Meet the data](meet_the_data.ipynb#top)\n"},
    )
    problems = check_notebooks_linked(root)
    assert [p.split(":")[0] for p in problems] == [str(BAR)]


def test_execution_rule_flags_unrun_cells_errors_and_figures_without_png(
    tmp_path: Path,
) -> None:
    unrun = new_code_cell("x = 1")
    error = new_output("error", ename="KeyError", evalue="'x'", traceback=[])
    root = build_tree(
        tmp_path,
        {
            str(BAR): [
                new_markdown_cell("# Title"),
                code("fig", figure()),
                new_code_cell("   \n"),  # blank: nbclient never runs it
                unrun,
                code("df['x']", error),
                code("fig", figure(png=False)),
            ],
            # The template is never executed, so it is not checked.
            "gallery/_template.ipynb": [new_code_cell("# placeholder")],
        },
    )
    problems = check_notebooks_executed(root)
    assert len(problems) == 3, problems
    assert problems[0].startswith(f"{BAR}, cell 3: not executed")
    assert problems[1].startswith(f"{BAR}, cell 4: has an error output (KeyError)")
    assert problems[2].startswith(f"{BAR}, cell 5: a figure without its static")
    assert "--only bar_plot" in problems[0]


def test_readme_rule_matches_links_tags_and_images(tmp_path: Path) -> None:
    root = build_tree(
        tmp_path,
        {
            str(BAR): [
                code("fig", figure(), tags=("readme:hero",)),
                code("fig", figure(), tags=("readme:missing",)),
            ],
            "gallery/trend/line_plot.ipynb": [
                code("fig", figure(), tags=("readme:hero",)),
            ],
        },
        {
            "README.md": (
                "![hero](docs/images/readme/hero.png)\n"
                '<img src="docs/images/readme/gone.png" width="600">\n'
                "![logo](docs/logo.png)\n"  # outside the README image folder
            ),
            str(INDEX): "![hero](../docs/images/readme/Hero.png)\n",
            "docs/images/readme/hero.png": "",
            "docs/images/readme/orphan.png": "",
        },
    )
    problems = check_readme_images(root)
    assert len(problems) == 5, problems
    joined = "\n".join(problems)
    assert "README.md: image 'docs/images/readme/gone.png'" in joined
    # Exact letter case: the Linux CI runner would not find Hero.png.
    assert f"{INDEX}: image '../docs/images/readme/Hero.png'" in joined
    assert "tag 'readme:missing' has no docs/images/readme/missing.png" in joined
    assert "gallery/trend/line_plot.ipynb, cell 0: tag 'readme:hero' is also" in joined
    assert "readme/orphan.png: no notebook cell is tagged" in joined
