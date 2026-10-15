from collections.abc import Iterator

import plotly.graph_objects as go
import pytest
from plotly.subplots import make_subplots

from easy_viz._layout import (
    apply_base_layout,
    auto_height,
    d3_format,
    escape_text,
    format_value,
    grid_geometry,
)
from easy_viz.config import get_config, set_config
from easy_viz.theme import get_theme
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
    g = grid_geometry(27, 3, width=1400, height=None, theme=DARK, caller="facet_plot")
    assert (g.n_rows, g.n_cols) == (9, 3)
    assert g.height == 9 * (DARK.row_plot_px + DARK.row_gap_px)
    assert g.v_spacing == pytest.approx(DARK.row_gap_px / g.height)
    assert g.h_spacing == pytest.approx(DARK.col_gap_px / 1400)
    row_px = (1 - (g.n_rows - 1) * g.v_spacing) / g.n_rows * g.height
    assert row_px >= DARK.row_plot_px


def test_forced_small_height_caps_spacing_and_make_subplots_accepts_it() -> None:
    g = grid_geometry(9, 1, width=300, height=300, theme=DARK, caller="facet_plot")
    # Uncapped, 90 px of 300 would be 0.3 per gap: 8 gaps = 240% of the figure.
    assert g.v_spacing == pytest.approx(0.5 / 8)
    assert (g.n_rows - 1) * g.v_spacing == pytest.approx(0.5)
    make_subplots(rows=g.n_rows, cols=g.n_cols, vertical_spacing=g.v_spacing)
    narrow = grid_geometry(
        4, 4, width=200, height=None, theme=DARK, caller="facet_plot"
    )
    assert narrow.h_spacing == pytest.approx(0.5 / 3)


def test_fewer_plots_than_columns_use_one_column_per_plot() -> None:
    g = grid_geometry(2, 3, width=1400, height=None, theme=DARK, caller="facet_plot")
    assert (g.n_rows, g.n_cols, g.v_spacing) == (1, 2, 0.0)
    single = grid_geometry(
        1, 3, width=1400, height=None, theme=DARK, caller="facet_plot"
    )
    assert (single.n_cols, single.h_spacing, single.v_spacing) == (1, 0.0, 0.0)


@pytest.mark.parametrize(("n_plots", "n_cols"), [(0, 3), (3, 0)])
def test_grid_needs_a_plot_and_a_column(n_plots: int, n_cols: int) -> None:
    with pytest.raises(ValueError, match=r"^facet_plot: "):
        grid_geometry(
            n_plots, n_cols, width=1400, height=None, theme=DARK, caller="facet_plot"
        )


@pytest.mark.parametrize(
    ("width", "height", "named"),
    [(1400, 0, "height=0"), (0, None, "width=0"), (1400, -5, "height=-5")],
)
def test_grid_rejects_sizes_it_would_divide_by(
    width: int, height: int | None, named: str
) -> None:
    # Unchecked, height=0 is a ZeroDivisionError and negatives give negative
    # spacings that Plotly rejects with an unrelated message.
    with pytest.raises(ValueError, match=rf"^facet_plot: {named} is not valid"):
        grid_geometry(4, 2, width=width, height=height, theme=DARK, caller="facet_plot")


@pytest.mark.usefixtures("config_width_900")
def test_width_none_uses_config() -> None:
    g = grid_geometry(2, 2, width=None, height=None, theme=DARK, caller="facet_plot")
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


def test_each_line_break_adds_a_line_to_the_top_margin() -> None:
    # A one-line-per-field margin let a <br> subtitle run into the plot below.
    def margin(title: str, subtitle: str) -> int:
        fig = go.Figure()
        apply_base_layout(
            fig, title=title, subtitle=subtitle, width=None, height=None, theme=DARK
        )
        return int(fig.layout.margin.t)

    single = margin("Revenue", "Sum")
    assert margin("Revenue<br>by region", "Sum") > single
    # Every spelling Plotly honours counts, so all three add the same height.
    three_subtitle_lines = {
        margin("Revenue", f"Sum{tag}2026{tag}warehouse")
        for tag in ("<br>", "<BR/>", "<br />")
    }
    assert len(three_subtitle_lines) == 1
    assert three_subtitle_lines.pop() - single == round(
        2 * DARK.subtitle_font_size * 1.5
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (862_289.0, "862k"),
        (1_081_928.0, "1.08M"),
        (999_999.0, "1M"),  # rounding carries into the next unit, never "1e+03k"
        (-2_500.0, "-2.5k"),
        (939.0, "939"),
        (0.4213, "0.421"),
        (4.2e12, "4.2T"),
    ],
)
def test_the_automatic_value_format(value: float, expected: str) -> None:
    assert format_value(value, None) == expected


def test_an_explicit_value_format_is_a_python_spec() -> None:
    assert format_value(1234.5, ",.0f") == "1,234"


def test_auto_height_keeps_the_aspect_and_grows_with_category_bands() -> None:
    theme = get_theme("dark")
    flat = auto_height(1000, theme=theme, title="t", subtitle=None)
    assert flat == 400
    few = auto_height(1000, theme=theme, title="t", subtitle=None, bands=3)
    many = auto_height(1000, theme=theme, title="t", subtitle=None, bands=40)
    assert few == flat and many > flat


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        (",.0f", ",.0f"),
        ("+.1%", "+.1%"),
        (".2e", ".2e"),
        (".3g", None),  # Python and d3 round g differently around exponents
        ("$,.0f", None),  # not a Python spec at all
        (None, None),
    ],
)
def test_only_specs_that_mean_the_same_reach_the_axis(
    spec: str | None, expected: str | None
) -> None:
    assert d3_format(spec) == expected
