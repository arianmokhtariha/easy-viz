"""The pure parts of ``scripts/build_gallery.py``, on synthetic notebooks.

Executing notebooks and rendering PNGs needs a kernel and Chrome; the logic that
decides what gets rendered, named, embedded and deleted does not, and is tested
here.
"""

import base64
from pathlib import Path, PurePosixPath

import pytest
from conftest import load_script
from nbformat import NotebookNode
from nbformat.v4 import (
    new_code_cell,
    new_markdown_cell,
    new_notebook,
    new_output,
)

build = load_script("build_gallery")

NB = PurePosixPath("gallery/comparison/bar_plot.ipynb")
OTHER = PurePosixPath("gallery/trend/line_plot.ipynb")
SPEC = {"data": [{"type": "bar", "x": ["a"], "y": [1]}], "layout": {}}


def figure() -> NotebookNode:
    """A figure output, as the plotly_mimetype renderer displays it."""
    return new_output("display_data", data={build.PLOTLY_MIME: SPEC})


def text() -> NotebookNode:
    return new_output("stream", name="stdout", text="rows: 3\n")


def cell(*outputs: NotebookNode, tags: tuple[str, ...] = ()) -> NotebookNode:
    code = new_code_cell("fig", execution_count=1, outputs=list(outputs))
    if tags:
        code.metadata["tags"] = list(tags)
    return code


def notebook(*cells: NotebookNode) -> NotebookNode:
    return new_notebook(cells=list(cells))


def test_figures_are_named_by_cell_index_and_numbered_within_a_cell() -> None:
    nb = notebook(
        new_markdown_cell("# The question"),  # markdown cells count in the index
        cell(text(), figure()),
        cell(figure(), text(), figure()),
        cell(text()),
    )
    found = build.figure_outputs(NB, nb)
    assert [(f.cell, f.name) for f in found] == [
        (1, "cell-01"),
        (2, "cell-02-1"),
        (2, "cell-02-2"),
    ]
    # Each result points at the real output, so embedding edits the notebook.
    assert found[2].output is nb.cells[2].outputs[2]


def test_a_valid_readme_tag_exports_its_cells_figure() -> None:
    nb = notebook(cell(figure()), cell(text(), figure(), tags=("other", "readme:hero")))
    exports, problems = build.readme_exports({NB: nb})
    assert problems == []
    assert list(exports) == ["hero"]
    assert exports["hero"].output is nb.cells[1].outputs[1]


@pytest.mark.parametrize("name", ["Hero", "-hero", "", "hero chart", "hero.png"])
def test_an_invalid_readme_name_is_reported_with_its_cell(name: str) -> None:
    nb = notebook(new_markdown_cell("x"), cell(figure(), tags=(f"readme:{name}",)))
    exports, problems = build.readme_exports({NB: nb})
    assert exports == {}
    assert len(problems) == 1
    assert f"{NB}, cell 1" in problems[0]
    assert "invalid name" in problems[0]


@pytest.mark.parametrize("figures", [0, 2])
def test_a_readme_cell_needs_exactly_one_figure(figures: int) -> None:
    nb = notebook(cell(*[figure() for _ in range(figures)], tags=("readme:hero",)))
    exports, problems = build.readme_exports({NB: nb})
    assert exports == {}
    assert len(problems) == 1
    assert f"found {figures}" in problems[0]


def test_readme_names_are_unique_across_notebooks() -> None:
    first = notebook(cell(figure(), tags=("readme:hero",)))
    second = notebook(new_markdown_cell("x"), cell(figure(), tags=("readme:hero",)))
    exports, problems = build.readme_exports({NB: first, OTHER: second})
    assert exports["hero"].notebook == NB
    assert len(problems) == 1
    assert f"{OTHER}, cell 1" in problems[0]
    assert f"already used by {NB}, cell 0" in problems[0]


def test_a_cell_with_two_readme_tags_is_reported() -> None:
    nb = notebook(cell(figure(), tags=("readme:a", "readme:b")))
    exports, problems = build.readme_exports({NB: nb})
    assert exports == {}
    assert "2 readme tags" in problems[0]


def test_embedding_keeps_the_plotly_json_and_adds_the_png() -> None:
    output = figure()
    png = b"\x89PNG\r\n\x1a\nfake"
    build.embed_png(output, png)
    assert output.data[build.PLOTLY_MIME] == SPEC
    assert base64.b64decode(output.data[build.PNG_MIME]) == png
    # Still rebuildable as a figure after embedding, and a display "config" in
    # the bundle does not break it.
    output.data[build.PLOTLY_MIME]["config"] = {"responsive": True}
    assert build.to_figure(output).data[0].y == (1,)


def test_stale_readme_images_are_pngs_no_tag_produced(tmp_path: Path) -> None:
    files = [tmp_path / n for n in ("hero.png", "old.png", "notes.txt", "hero.svg")]
    assert build.stale_readme_images(files, {"hero"}) == [tmp_path / "old.png"]


def test_a_review_image_that_cannot_be_deleted_does_not_fail_the_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # On Windows, a PNG open in an image viewer cannot be deleted. The build used
    # to crash at this point, after executing every notebook, writing none.
    monkeypatch.setattr(build, "REVIEW", tmp_path)
    review = tmp_path / NB.stem
    review.mkdir()
    locked, old = review / "cell-07.png", review / "cell-09.png"
    locked.write_bytes(b"old")
    old.write_bytes(b"old")
    real_unlink = Path.unlink

    def unlink(path: Path, missing_ok: bool = False) -> None:
        if path == locked:
            raise PermissionError("in use by another process")
        real_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", unlink)
    output = figure()
    build.embed_png(output, b"new")
    kept = build.save_review_images({NB: notebook(cell(output))})
    assert kept == [locked]
    assert not old.exists()
    assert (review / "cell-00.png").read_bytes() == b"new"


def test_only_selects_by_stem_and_rejects_unknown_or_ambiguous_names() -> None:
    assert build.select_notebooks([NB, OTHER], ["line_plot"]) == [OTHER]
    assert build.select_notebooks([NB, OTHER], []) == [NB, OTHER]
    with pytest.raises(ValueError, match=r"unknown notebook\(s\) \['bar_plt'\]"):
        build.select_notebooks([NB, OTHER], ["bar_plt"])
    twin = PurePosixPath("gallery/trend/bar_plot.ipynb")
    with pytest.raises(ValueError, match="share the name 'bar_plot'"):
        build.select_notebooks([NB, twin], [])


def test_discovery_skips_the_template_and_checkpoints(tmp_path: Path) -> None:
    for name in (
        "gallery/comparison/bar_plot.ipynb",
        "gallery/meet_the_data.ipynb",
        "gallery/_template.ipynb",
        "gallery/comparison/.ipynb_checkpoints/bar_plot-checkpoint.ipynb",
    ):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text("{}", encoding="utf-8")
    assert build.discover_notebooks(tmp_path) == [
        PurePosixPath("gallery/comparison/bar_plot.ipynb"),
        PurePosixPath("gallery/meet_the_data.ipynb"),
    ]


def test_written_notebooks_are_lf_and_drop_the_python_patch_version(
    tmp_path: Path,
) -> None:
    nb = notebook(cell(figure()))
    nb.metadata["language_info"] = {"name": "python", "version": "3.14.6"}
    build.drop_volatile_metadata(nb)
    path = tmp_path / "nb.ipynb"
    build.write_notebook(nb, path)
    raw = path.read_bytes()
    assert b"\r\n" not in raw  # Windows would otherwise write CRLF
    assert raw.endswith(b"\n")
    assert b"3.14.6" not in raw


def test_warnings_lose_the_kernels_temporary_path_and_source_echo() -> None:
    printed = (
        r"C:\Users\someone\AppData\Local\Temp\ipykernel_5528\1331079986.py:2: "
        "EasyVizWarning: bar_plot: dropped 4 of 10 rows.\n"
        '  ev.bar_plot(income, "segment", "annual_income")\n'
        "/tmp/ipykernel_77/42.py:9: UserWarning: second\n"
        "  source()\n"
        "plain output stays\n"
    )
    cell = new_code_cell(outputs=[new_output("stream", name="stderr", text=printed)])
    nb = new_notebook(cells=[cell])
    build.scrub_warning_locations(nb)
    assert nb.cells[0].outputs[0]["text"] == (
        "EasyVizWarning: bar_plot: dropped 4 of 10 rows.\n"
        "UserWarning: second\n"
        "plain output stays\n"
    )
