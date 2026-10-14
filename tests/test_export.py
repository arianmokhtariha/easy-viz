"""Tests for static image export.

Tests marked ``export`` run real kaleido exports and skip when Chrome is missing.
The rest need no Chrome: they check validation and how Plotly is called.
"""

import struct
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio
import pytest

from easy_viz.config import get_config, set_config
from easy_viz.export import save, save_many


@pytest.fixture(autouse=True)
def restore_config() -> Iterator[None]:
    """Give every test the defaults it found."""
    saved = get_config()
    yield
    set_config(width=saved.width, export_scale=saved.export_scale)


@pytest.fixture(scope="session")
def chrome(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Skip the test unless kaleido can really export (needs Chrome)."""
    pytest.importorskip("kaleido")
    probe = tmp_path_factory.mktemp("chrome_probe") / "probe.png"
    try:
        pio.write_image(go.Figure(), probe)
    except RuntimeError as error:  # plotly's "Kaleido requires Google Chrome"
        pytest.skip(f"static export unavailable: {error}".strip())


def make_fig(width: int | None = 400, height: int | None = 300) -> go.Figure:
    """A small figure with the given layout size."""
    fig = go.Figure(go.Bar(x=["a", "b", "c"], y=[3, 1, 2]))
    fig.update_layout(width=width, height=height, title="Revenue")
    return fig


def png_size(path: Path) -> tuple[int, int]:
    """Read (width, height) in pixels from a PNG header."""
    width, height = struct.unpack(">II", path.read_bytes()[16:24])
    return width, height


# --- real exports (need Chrome) -------------------------------------------------


@pytest.mark.export
@pytest.mark.parametrize(
    ("filename", "magic"),
    [
        ("chart.png", b"\x89PNG\r\n\x1a\n"),
        ("chart.SVG", b"<svg"),  # extension case is ignored
        ("chart.pdf", b"%PDF"),
        ("chart.jpeg", b"\xff\xd8\xff"),
    ],
)
@pytest.mark.usefixtures("chrome")
def test_save_picks_the_format_from_the_extension(
    tmp_path: Path, filename: str, magic: bytes
) -> None:
    written = save(make_fig(), tmp_path / filename)
    assert written.read_bytes().startswith(magic)


@pytest.mark.export
@pytest.mark.usefixtures("chrome")
def test_save_scale_comes_from_config_unless_overridden(tmp_path: Path) -> None:
    set_config(export_scale=1.5)
    fig = make_fig(width=400, height=300)

    from_config = save(fig, tmp_path / "config.png")
    explicit = save(fig, tmp_path / "explicit.png", scale=1, width=250)

    assert png_size(from_config) == (600, 450)  # 400 x 1.5, 300 x 1.5
    assert png_size(explicit) == (250, 300)  # width override, figure's own height


@pytest.mark.export
@pytest.mark.usefixtures("chrome")
def test_save_creates_parents_returns_absolute_path_and_keeps_fig_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    fig = make_fig()
    before = fig.to_json()

    written = save(fig, Path("reports") / "q3" / "chart.png")

    assert written == tmp_path.resolve() / "reports" / "q3" / "chart.png"
    assert written.is_file()
    assert fig.to_json() == before


@pytest.mark.export
@pytest.mark.usefixtures("chrome")
def test_save_many_keeps_each_figures_own_size_and_input_order(
    tmp_path: Path,
) -> None:
    # pio.write_images alone would size both at Plotly's 700x500 default.
    figs = {"wide": make_fig(width=500), "narrow": make_fig(width=200)}

    written = save_many(figs, tmp_path / "out", scale=1)

    assert [p.name for p in written] == ["wide.png", "narrow.png"]
    assert [png_size(p)[0] for p in written] == [500, 200]


# --- no Chrome needed -------------------------------------------------------------


def test_save_many_makes_one_batch_call_with_sizes_and_config_scale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, object]] = []

    def fake_write_images(
        figures: list[go.Figure], files: list[Path], **kw: object
    ) -> None:
        calls.append({"figures": figures, "files": files, **kw})

    monkeypatch.setattr(pio, "write_images", fake_write_images)
    set_config(export_scale=3)
    figs = {"a": make_fig(width=500, height=None), "b": make_fig(width=200)}

    # Upper case works, as it does for save()'s file extension.
    written = save_many(figs, tmp_path / "new_dir", format="WEBP")  # type: ignore[arg-type]

    assert len(calls) == 1  # one call = one Chrome start
    (call,) = calls
    assert (
        call["files"]
        == written
        == [
            (tmp_path / "new_dir").resolve() / "a.webp",
            (tmp_path / "new_dir").resolve() / "b.webp",
        ]
    )
    assert call["figures"] == list(figs.values())
    assert (call["format"], call["scale"]) == ("webp", 3)
    assert (call["width"], call["height"]) == ([500, 200], [None, 300])
    assert (tmp_path / "new_dir").is_dir()


@pytest.mark.parametrize("filename", ["chart", "chart.txt", "chart.eps", ".png.bak"])
def test_save_rejects_unsupported_extensions_before_touching_disk(
    tmp_path: Path, filename: str
) -> None:
    with pytest.raises(ValueError, match=r"^save: .*png, jpg, jpeg, webp, svg, pdf"):
        save(make_fig(), tmp_path / "new_dir" / filename)
    assert not (tmp_path / "new_dir").exists()


@pytest.mark.parametrize(
    ("kwargs", "named"),
    [
        ({"scale": 0}, "scale=0"),  # plotly would treat 0 as "use the default"
        ({"scale": -2}, "scale=-2"),
        ({"scale": True}, "scale=True"),
        ({"scale": float("nan")}, "scale=nan"),  # passes "<= 0", fails in Chrome
        ({"width": 0}, "width=0"),
        ({"height": 12.5}, "height=12.5"),
    ],
)
def test_save_rejects_unusable_scale_and_sizes(
    tmp_path: Path, kwargs: dict[str, object], named: str
) -> None:
    with pytest.raises(ValueError, match=named):
        save(make_fig(), tmp_path / "chart.png", **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "name",
    # Windows refuses the second line too; caught up front, so a batch never
    # fails half-written.
    [
        *("", "a/b", "a\\b", "..", ".", "C:x", "../escape"),
        *("Margin?", "a|b", "NUL", "con.v2", "trailing.", "tab\there"),
    ],
)
def test_save_many_rejects_names_that_are_not_plain_file_names(
    tmp_path: Path, name: str
) -> None:
    with pytest.raises(ValueError, match=r"^save_many: .*invalid file name"):
        save_many({"ok": make_fig(), name: make_fig()}, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_save_many_rejects_names_that_differ_only_by_case(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="'Sales' and 'sales'"):
        save_many({"Sales": make_fig(), "sales": make_fig()}, tmp_path)


def test_save_many_rejects_empty_mapping_and_unknown_format(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="figs is empty"):
        save_many({}, tmp_path)
    with pytest.raises(ValueError, match="format='eps'"):
        save_many({"a": make_fig()}, tmp_path, format="eps")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "export",
    [
        lambda p: save(make_fig(), p / "chart.png"),
        lambda p: save_many({"chart": make_fig()}, p),
    ],
    ids=["save", "save_many"],
)
def test_missing_kaleido_gives_the_install_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, export: Callable[[Path], object]
) -> None:
    monkeypatch.setitem(sys.modules, "kaleido", None)  # makes `import kaleido` fail
    with pytest.raises(ImportError, match=r'pip install "easy-viz\[export\]"'):
        export(tmp_path)
