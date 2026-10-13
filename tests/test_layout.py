from collections.abc import Iterator

import plotly.graph_objects as go
import pytest
from plotly.subplots import make_subplots

from easy_viz._layout import apply_base_layout, escape_text, grid_geometry
from easy_viz.config import get_config, set_config
from easy_viz.theme.registry import DARK, LIGHT


@pytest.fixture
def config_width_900() -> Iterator[None]:
    previous = get_config()
    set_config(width=900)
    yield
    set_config(width=previous.width, export_scale=previous.export_scale)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Revenue", "Revenue"),
        ("Cost in $", "Cost in &#36;"),
        ("From $1M to $3M", "From &#36;1M to &#36;3M"),
        ("<b>bold</b> stays", "<b>bold</b> stays"),
    ],
)
def test_escape_text(text: str, expected: str) -> None:
    assert escape_text(text) == expected


def test_nine_rows_do_not_collapse() -> None:
    # The original bug: a fixed v_spacing=0.12 left nine rows ~11 px each.
    g = grid_geometry(27, 3, width=1400, height=None, theme=DARK)
    assert (g.n_rows, g.n_cols) == (9, 3)
    assert g.height == 9 * (DARK.row_plot_px + DARK.row_gap_px)
    assert g.v_spacing == pytest.approx(DARK.row_gap_px / g.height)
    assert g.h_spacing == pytest.approx(DARK.col_gap_px / 1400)
    row_px = (1 - (g.n_rows - 1) * g.v_spacing) / g.n_rows * g.height
    assert row_px >= DARK.row_plot_px


def test_forced_small_height_caps_spacing_and_make_subplots_accepts_it() -> None:
    g = grid_geometry(9, 1, width=300, height=300, theme=DARK)
    # Uncapped, 90 px of 300 would be 0.3 per gap: 8 gaps = 240% of the figure.
    assert g.v_spacing == pytest.approx(0.5 / 8)
    assert (g.n_rows - 1) * g.v_spacing == pytest.approx(0.5)
    make_subplots(rows=g.n_rows, cols=g.n_cols, vertical_spacing=g.v_spacing)
    narrow = grid_geometry(4, 4, width=200, height=None, theme=DARK)
    assert narrow.h_spacing == pytest.approx(0.5 / 3)


def test_fewer_plots_than_columns_use_one_column_per_plot() -> None:
    g = grid_geometry(2, 3, width=1400, height=None, theme=DARK)
    assert (g.n_rows, g.n_cols, g.v_spacing) == (1, 2, 0.0)
    single = grid_geometry(1, 3, width=1400, height=None, theme=DARK)
    assert (single.n_cols, single.h_spacing, single.v_spacing) == (1, 0.0, 0.0)


@pytest.mark.parametrize(("n_plots", "n_cols"), [(0, 3), (3, 0)])
def test_grid_needs_a_plot_and_a_column(n_plots: int, n_cols: int) -> None:
    with pytest.raises(ValueError, match="grid_geometry"):
        grid_geometry(n_plots, n_cols, width=1400, height=None, theme=DARK)


@pytest.mark.usefixtures("config_width_900")
def test_width_none_uses_config() -> None:
    g = grid_geometry(2, 2, width=None, height=None, theme=DARK)
    assert g.h_spacing == pytest.approx(DARK.col_gap_px / 900)
    fig = go.Figure()
    apply_base_layout(
        fig, title="t", subtitle=None, width=None, height=None, theme=DARK
    )
    assert fig.layout.width == 900
    assert fig.layout.height is None  # Plotly auto-sizes


def test_base_layout_title_block() -> None:
    fig = go.Figure()
    apply_base_layout(
        fig,
        title="From $1M to $3M",
        subtitle="in $",
        width=1000,
        height=500,
        theme=LIGHT,
    )
    layout = fig.layout
    assert layout.title.text == "<b>From &#36;1M to &#36;3M</b>"
    assert layout.title.subtitle.text == "in &#36;"
    assert (layout.width, layout.height) == (1000, 500)
    assert fig.to_dict()["layout"]["template"]["layout"]["paper_bgcolor"] == (
        LIGHT.background
    )
    # The top margin holds the top padding, both lines and the gap to the plot.
    lines = LIGHT.title_font_size + LIGHT.subtitle_font_size
    assert layout.margin.t >= LIGHT.title_top_px + lines + LIGHT.title_gap_px


def test_subtitle_adds_to_the_top_margin_and_empty_text_shows_nothing() -> None:
    with_subtitle, without = go.Figure(), go.Figure()
    apply_base_layout(
        with_subtitle, title="t", subtitle="s", width=None, height=None, theme=DARK
    )
    apply_base_layout(
        without, title="t", subtitle="", width=None, height=None, theme=DARK
    )
    assert with_subtitle.layout.margin.t > without.layout.margin.t
    assert without.layout.title.subtitle.text is None
