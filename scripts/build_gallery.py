"""Build the gallery: regenerate the data, execute the notebooks, render images.

Steps, in order:

1. Find the gallery notebooks (``gallery/**/*.ipynb``; names starting with ``_``,
   such as the template, are not gallery notebooks) and apply ``--only``.
2. Check that DuckDB, which the notebooks query the data with, is installed.
3. Regenerate the showcase data with ``gallery/data/generate.py``.
4. Execute each notebook top to bottom in a fresh kernel. Plotly's renderer is set
   to ``plotly_mimetype``, so every figure output carries the figure as JSON: the
   interactive form, for the docs site.
5. Render every figure to PNG in one batch (one Chrome session) and embed each PNG
   next to its JSON, so the notebook shows a static image on GitHub.
6. Write the executed notebooks back, before the side outputs below.
7. Save each PNG to ``.review/<notebook>/<cell>.png`` for the visual review loop.
8. Export the figure of every cell tagged ``readme:<name>`` to
   ``docs/images/readme/<name>.png`` at the configured export scale. A full run
   removes README images that no tag produces any more. Old images that can't be
   deleted (open in another program) are listed instead of failing the run.

A notebook whose execution fails is reported and not written; the others still are,
and the script exits with an error. A misused ``readme:`` tag (invalid or repeated
name, or not exactly one figure in its cell) stops the run before anything is
written.

DuckDB has no Python 3.15 wheel yet, so the gallery builds on Python 3.14 in an
isolated environment (the project's own ``.venv`` is not touched)::

    uv run --isolated --python 3.14 python scripts/build_gallery.py
    uv run --isolated --python 3.14 python scripts/build_gallery.py --only bar_plot
"""

import argparse
import base64
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import warnings
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import nbformat
import plotly.graph_objects as go
from jupyter_client.kernelspec import KernelSpecManager
from jupyter_client.manager import KernelManager
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError, CellTimeoutError, DeadKernelError
from nbformat import NotebookNode

from easy_viz import save_many

REPO = Path(__file__).resolve().parents[1]
GENERATOR = REPO / "gallery" / "data" / "generate.py"
README_IMAGES = REPO / "docs" / "images" / "readme"
REVIEW = REPO / ".review"

BUILD_COMMAND = "uv run --isolated --python 3.14 python scripts/build_gallery.py"
PLOTLY_MIME = "application/vnd.plotly.v1+json"
PNG_MIME = "image/png"
README_TAG = "readme:"
README_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
KERNEL = "python3"
CELL_TIMEOUT_S = 600  # generous: a cell may bootstrap a model or a large query


@dataclass(frozen=True, eq=False)
class FigureOutput:
    """One figure in an executed notebook.

    Parameters
    ----------
    notebook : PurePosixPath
        The notebook, relative to the repository root.
    cell : int
        Index of the cell in the notebook (markdown cells count).
    name : str
        ``cell-NN``, or ``cell-NN-K`` for the K-th of several figures in one cell.
    output : NotebookNode
        The output holding the figure. Embedding a PNG changes it in place.
    """

    notebook: PurePosixPath
    cell: int
    name: str
    output: NotebookNode = field(repr=False)


# --- Pure functions: no kernel, no Chrome, no files ------------------------------


def select_notebooks(
    notebooks: Sequence[PurePosixPath], only: Sequence[str]
) -> list[PurePosixPath]:
    """Return the notebooks to build: all of them, or those named in ``only``.

    Parameters
    ----------
    notebooks : sequence of PurePosixPath
        Every gallery notebook.
    only : sequence of str
        Notebook stems to keep (``bar_plot``); empty keeps all.

    Returns
    -------
    list of PurePosixPath
        The selected notebooks, in the given order.

    Raises
    ------
    ValueError
        If two notebooks share a stem (``--only`` and ``.review/`` name notebooks
        by stem), or ``only`` names a notebook that does not exist.
    """
    by_stem: dict[str, PurePosixPath] = {}
    for notebook in notebooks:
        if (other := by_stem.setdefault(notebook.stem, notebook)) != notebook:
            raise ValueError(
                f"{other} and {notebook} share the name {notebook.stem!r}. Notebook "
                "names must be unique across the gallery: rename one."
            )
    unknown = sorted(set(only) - by_stem.keys())
    if unknown:
        raise ValueError(
            f"--only names unknown notebook(s) {unknown}. Use a notebook's file name "
            f"without .ipynb; available: {sorted(by_stem)}."
        )
    return [nb for nb in notebooks if not only or nb.stem in only]


def figure_outputs(notebook: PurePosixPath, nb: NotebookNode) -> list[FigureOutput]:
    """Return every figure output of an executed notebook, named after its cell.

    Parameters
    ----------
    notebook : PurePosixPath
        The notebook's path, recorded in each result.
    nb : NotebookNode
        The executed notebook.

    Returns
    -------
    list of FigureOutput
        In notebook order. A cell with one figure gives ``cell-NN``; a cell with
        several gives ``cell-NN-1``, ``cell-NN-2``, ...
    """
    found: list[FigureOutput] = []
    for index, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue
        outputs = [o for o in cell.outputs if PLOTLY_MIME in o.get("data", {})]
        base = f"cell-{index:02d}"
        found.extend(
            FigureOutput(
                notebook,
                index,
                base if len(outputs) == 1 else f"{base}-{k}",
                output,
            )
            for k, output in enumerate(outputs, start=1)
        )
    return found


def readme_tags(cell: NotebookNode) -> list[str]:
    """Return the names in a cell's ``readme:<name>`` tags (unvalidated)."""
    tags: list[str] = cell.get("metadata", {}).get("tags", [])
    return [tag.removeprefix(README_TAG) for tag in tags if tag.startswith(README_TAG)]


def readme_exports(
    notebooks: Mapping[PurePosixPath, NotebookNode],
) -> tuple[dict[str, FigureOutput], list[str]]:
    """Find the figures that become README images, and every misuse of the tag.

    A cell tagged ``readme:<name>`` exports its figure as ``<name>.png``. The cell
    has one such tag and exactly one figure; the name matches
    ``^[a-z0-9][a-z0-9_-]*$`` and is unique across ``notebooks``.

    Parameters
    ----------
    notebooks : mapping of PurePosixPath to NotebookNode
        Executed notebooks, by path.

    Returns
    -------
    exports : dict of str to FigureOutput
        README image name to figure, for the valid tags.
    problems : list of str
        One message per misuse, naming the notebook, the cell and the fix.
    """
    exports: dict[str, FigureOutput] = {}
    problems: list[str] = []
    for path, nb in notebooks.items():
        figures = figure_outputs(path, nb)
        for index, cell in enumerate(nb.cells):
            names = readme_tags(cell)
            if not names:
                continue
            where = f"{path}, cell {index}"
            in_cell = [figure for figure in figures if figure.cell == index]
            if len(names) > 1:
                problems.append(
                    f"{where}: has {len(names)} readme tags {names}. A cell exports "
                    "one README image: keep one tag."
                )
                continue
            name = names[0]
            if not README_NAME.match(name):
                problems.append(
                    f"{where}: tag 'readme:{name}' has an invalid name. Use lowercase "
                    "letters, digits, '-' and '_', starting with a letter or digit "
                    "(e.g. 'readme:pareto-cutoff')."
                )
            elif len(in_cell) != 1:
                problems.append(
                    f"{where}: tag 'readme:{name}' needs exactly one figure in the "
                    f"cell, found {len(in_cell)}. Move the tag to a cell that "
                    "displays one figure."
                )
            elif name in exports:
                problems.append(
                    f"{where}: tag 'readme:{name}' is already used by "
                    f"{exports[name].notebook}, cell {exports[name].cell}. README "
                    "image names are unique: rename one tag."
                )
            else:
                exports[name] = in_cell[0]
    return exports, problems


def to_figure(output: NotebookNode) -> go.Figure:
    """Rebuild the ``go.Figure`` that a figure output displays."""
    spec = output.data[PLOTLY_MIME]
    # The bundle may carry a display "config" too; a figure takes only these keys.
    return go.Figure(
        {key: spec[key] for key in ("data", "layout", "frames") if key in spec}
    )


def embed_png(output: NotebookNode, png: bytes) -> None:
    """Add ``png`` to a figure output, next to its Plotly JSON.

    GitHub shows the static ``image/png``; Jupyter and the docs site show the
    interactive figure from the JSON.
    """
    output.data[PNG_MIME] = base64.b64encode(png).decode("ascii")


def stale_readme_images(
    existing: Iterable[Path], produced: Collection[str]
) -> list[Path]:
    """Return the README images that no ``readme:<name>`` tag produced.

    Parameters
    ----------
    existing : iterable of Path
        Files in the README image folder.
    produced : collection of str
        Image names (without ``.png``) produced by the tags.

    Returns
    -------
    list of Path
        The ``.png`` files to delete, sorted. Other files are left alone.
    """
    return sorted(p for p in existing if p.suffix == ".png" and p.stem not in produced)


def drop_volatile_metadata(nb: NotebookNode) -> None:
    """Remove metadata that changes with the machine, so rebuilds stay diff-clean.

    The kernel records the exact Python version (``3.14.6``); a patch upgrade would
    otherwise rewrite every notebook.
    """
    nb.metadata.get("language_info", {}).pop("version", None)


# A warning as Python prints it from a notebook cell: the kernel's temporary file for
# the cell (a local path with the kernel's process id), the line, then the warning;
# the next line echoes the source. Neither the path nor the echo belongs in a
# committed notebook.
_CELL_WARNING = re.compile(
    r"^[^\n]*ipykernel_\d+[\\/]\d+\.py:\d+: (?P<warning>\w+: [^\n]*)\n(?:  [^\n]*\n)?",
    re.MULTILINE,
)


def scrub_warning_locations(nb: NotebookNode) -> None:
    """Strip the kernel's temporary file paths from warnings in cell outputs.

    They hold the user's home directory and a process id that changes on every
    run, so they would leak a local path and make rebuilds differ. The warning
    category and message are kept.
    """
    for cell in nb.cells:
        for output in cell.get("outputs", []):
            if output.get("output_type") == "stream":
                output["text"] = _CELL_WARNING.sub(r"\g<warning>\n", output["text"])


# --- I/O --------------------------------------------------------------------------


def discover_notebooks(root: Path) -> list[PurePosixPath]:
    """List the gallery notebooks under ``root/gallery``, relative to ``root``.

    Files starting with ``_`` (the template) and Jupyter's checkpoint copies are
    not gallery notebooks.

    Parameters
    ----------
    root : Path
        The repository root.

    Returns
    -------
    list of PurePosixPath
        Sorted; empty if there is no gallery directory.
    """
    return sorted(
        PurePosixPath(path.relative_to(root).as_posix())
        for path in (root / "gallery").rglob("*.ipynb")
        if not path.name.startswith("_")
        and ".ipynb_checkpoints" not in path.relative_to(root).parts
    )


def require_duckdb() -> None:
    """Exit with the build command if DuckDB, which the notebooks use, is missing."""
    if importlib.util.find_spec("duckdb") is None:
        raise SystemExit(
            "DuckDB is not installed in this environment. The gallery notebooks query "
            "the showcase data with it, and it has no Python 3.15 wheel yet, so build "
            f"the gallery on Python 3.14:\n    {BUILD_COMMAND}"
        )


def regenerate_data() -> None:
    """Run the showcase data generator; exit if it is missing or fails."""
    if not GENERATOR.is_file():
        raise SystemExit(
            f"{GENERATOR.relative_to(REPO).as_posix()} not found. The build "
            "regenerates the showcase data before executing the notebooks; restore "
            "the generator."
        )
    print(f"Regenerating data: {GENERATOR.relative_to(REPO).as_posix()}", flush=True)
    result = subprocess.run([sys.executable, str(GENERATOR)], cwd=REPO, check=False)
    if result.returncode != 0:
        raise SystemExit(f"The data generator failed (exit code {result.returncode}).")


def execute(path: Path) -> NotebookNode:
    """Execute a notebook top to bottom in a fresh kernel, in its own directory.

    Raises
    ------
    CellExecutionError, CellTimeoutError, DeadKernelError
        If a cell raises, runs past the timeout, or the kernel dies.
    """
    # nbformat's read and writes carry no type annotations; a notebook is a
    # NotebookNode, a dict of untyped JSON values.
    nb: NotebookNode = nbformat.read(path, as_version=4)  # type: ignore[no-untyped-call]
    # No kernel directories: always the kernel of this interpreter, never a user's
    # "python3" kernelspec that may point at another Python without DuckDB.
    manager = KernelManager(
        kernel_name=KERNEL, kernel_spec_manager=KernelSpecManager(kernel_dirs=[])
    )
    client = NotebookClient(
        nb,
        km=manager,
        timeout=CELL_TIMEOUT_S,
        record_timing=False,
        resources={"metadata": {"path": str(path.parent)}},
    )
    client.execute()
    return nb


def write_notebook(nb: NotebookNode, path: Path) -> None:
    """Write a notebook as nbformat v4 JSON with LF line endings."""
    text: str = nbformat.writes(nb, version=4)  # type: ignore[no-untyped-call]
    path.write_text(text if text.endswith("\n") else text + "\n", "utf-8", newline="\n")


def remove_files(paths: Iterable[Path]) -> list[Path]:
    """Delete ``paths`` one by one; return those that could not be deleted.

    On Windows a file open in another program (an image viewer showing a review
    PNG) cannot be deleted. That must not fail a build whose notebooks are done, so
    the caller reports the leftovers instead.
    """
    kept: list[Path] = []
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            kept.append(path)
    return kept


def render_figures(executed: Mapping[PurePosixPath, NotebookNode]) -> int:
    """Embed a PNG in every figure output, next to its Plotly JSON.

    All figures render in one ``save_many`` batch at scale 1, so Chrome starts
    once.

    Returns
    -------
    int
        The number of figures rendered.
    """
    figures = [f for path, nb in executed.items() for f in figure_outputs(path, nb)]
    if figures:
        with tempfile.TemporaryDirectory() as folder:
            paths = save_many(
                {f"figure-{i:05d}": to_figure(f.output) for i, f in enumerate(figures)},
                folder,
                scale=1,
            )
            for figure, path in zip(figures, paths, strict=True):
                embed_png(figure.output, path.read_bytes())
    return len(figures)


def save_review_images(executed: Mapping[PurePosixPath, NotebookNode]) -> list[Path]:
    """Save every embedded PNG to ``.review/<notebook>/<cell>.png``.

    Each notebook's old review images are deleted first, so the folder never shows
    a figure the notebook no longer makes.

    Returns
    -------
    list of Path
        Old images that could not be deleted (open in another program).
    """
    kept: list[Path] = []
    for notebook, nb in executed.items():
        review = REVIEW / notebook.stem
        if review.is_dir():
            kept += remove_files(p for p in review.iterdir() if p.is_file())
        review.mkdir(parents=True, exist_ok=True)
        for figure in figure_outputs(notebook, nb):
            png = base64.b64decode(figure.output.data[PNG_MIME])
            (review / f"{figure.name}.png").write_bytes(png)
    return kept


def write_readme_images(
    exports: Mapping[str, FigureOutput], *, remove_stale: bool
) -> tuple[list[Path], list[Path]]:
    """Export the README images at the configured scale, and remove stale ones.

    Parameters
    ----------
    exports : mapping of str to FigureOutput
        README image name to figure.
    remove_stale : bool
        Delete README images that no tag produced. Only safe when every notebook
        was read: a full run without failures.

    Returns
    -------
    removed : list of Path
        The stale images deleted.
    kept : list of Path
        The stale images that could not be deleted (open in another program).
    """
    if exports:
        save_many(
            {name: to_figure(f.output) for name, f in exports.items()}, README_IMAGES
        )
    if not remove_stale or not README_IMAGES.is_dir():
        return [], []
    stale = stale_readme_images(README_IMAGES.iterdir(), exports.keys())
    kept = remove_files(stale)
    return [p for p in stale if p not in kept], kept


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Read the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--only",
        nargs="+",
        default=[],
        metavar="NAME",
        help="build only these notebooks (file names without .ipynb)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Build the gallery; see the module docstring for the steps."""
    args = parse_args(argv)
    try:
        selected = select_notebooks(discover_notebooks(REPO), args.only)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    full_run = not args.only
    require_duckdb()
    regenerate_data()

    # Read by Plotly when the kernel imports it: every figure output then carries
    # the figure's JSON. The kernel inherits this process's environment.
    os.environ["PLOTLY_RENDERER"] = "plotly_mimetype"
    # pyzmq's notice about Windows' default event loop; it handles it itself.
    warnings.filterwarnings("ignore", "Proactor event loop", RuntimeWarning)

    executed: dict[PurePosixPath, NotebookNode] = {}
    failures: list[str] = []
    for notebook in selected:
        print(f"Executing {notebook}", flush=True)
        try:
            executed[notebook] = execute(REPO / notebook)
        except (CellExecutionError, CellTimeoutError, DeadKernelError) as error:
            failures.append(f"{notebook}: {error}")

    exports, problems = readme_exports(executed)
    if problems:
        raise SystemExit(
            "Invalid readme tags (nothing was written):\n" + "\n".join(problems)
        )

    rendered = render_figures(executed)
    # The notebooks are the build's product: write them before the side outputs,
    # so a problem with .review/ or the README images can't lose them.
    for path, nb in executed.items():
        drop_volatile_metadata(nb)
        scrub_warning_locations(nb)
        write_notebook(nb, REPO / path)
    kept = save_review_images(executed)
    # A failed notebook's tags were never read: its images are not stale.
    removed, kept_stale = write_readme_images(
        exports, remove_stale=full_run and not failures
    )

    print(
        f"Notebooks executed: {len(executed)} of {len(selected)}. "
        f"Figures rendered: {rendered} (see {REVIEW.relative_to(REPO)}/). "
        f"README images written: {len(exports)}, removed: {len(removed)}."
    )
    if kept or kept_stale:
        print(
            "Could not delete these old images (open in another program?); close "
            "them and re-run to remove them:\n"
            + "\n".join(f"    {p.relative_to(REPO)}" for p in kept + kept_stale)
        )
    if failures:
        raise SystemExit("Failed (not written):\n" + "\n\n".join(failures))


if __name__ == "__main__":
    main()
