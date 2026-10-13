import dataclasses
from collections.abc import Callable, Iterator
from typing import get_args

import plotly.io as pio
import pytest

from easy_viz.theme import registry
from easy_viz.theme._color import contrast_ratio, parse_color, with_alpha
from easy_viz.theme.registry import (
    BUILTIN_THEMES,
    DARK,
    LIGHT,
    ThemeName,
    get_theme,
    resolve_theme,
    set_theme,
)
from easy_viz.theme.theme import Theme, build_template

TEXT_CONTRAST = 4.5  # WCAG AA for text
MARK_CONTRAST = 3.0  # WCAG AA for graphical objects

BUILTINS = pytest.mark.parametrize("theme", BUILTIN_THEMES.values(), ids=BUILTIN_THEMES)


@pytest.fixture
def restore_theme() -> Iterator[None]:
    previous = get_theme()
    yield
    set_theme(previous)


# --- colour maths ---------------------------------------------------------------


def test_contrast_ratio_extremes_and_blending() -> None:
    assert contrast_ratio("#000", "#ffffff") == pytest.approx(21)
    # Fully transparent text is invisible: it blends into the surface.
    assert contrast_ratio("rgba(255,255,255,0)", "#000000") == pytest.approx(1)
    # Half-transparent white on black is a mid grey, far below opaque white.
    assert 1 < contrast_ratio("rgba(255,255,255,0.5)", "#000000") < 21 / 2
    with pytest.raises(ValueError, match="translucent"):
        contrast_ratio("#fff", "rgba(0,0,0,0.5)")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("#abc", (170, 187, 204, 1.0)),
        (" rgb(1, 2, 3) ", (1, 2, 3, 1.0)),
        ("rgba(255,255,255,0.25)", (255, 255, 255, 0.25)),
    ],
)
def test_parse_color_accepted_forms(
    text: str, expected: tuple[float, float, float, float]
) -> None:
    assert parse_color(text) == expected


@pytest.mark.parametrize(
    "text", ["white", "#abcd", "rgb(300,0,0)", "rgba(1,2,3)", "rgb(1,2,3,0.5)", ""]
)
def test_parse_color_rejects_unreadable(text: str) -> None:
    with pytest.raises(ValueError, match="not a colour"):
        parse_color(text)


def test_with_alpha_replaces_opacity() -> None:
    assert with_alpha("rgba(10,20,30,0.9)", 0.25) == "rgba(10,20,30,0.25)"


# --- built-in themes: the tested invariants ---------------------------------------


@BUILTINS
def test_text_is_readable_on_both_surfaces(theme: Theme) -> None:
    for surface in (theme.background, theme.plot_background):
        for text in (theme.text, theme.muted_text):
            assert contrast_ratio(text, surface) >= TEXT_CONTRAST, (text, surface)


@BUILTINS
def test_colours_that_label_annotations_are_readable(theme: Theme) -> None:
    # Reference and positive/negative colours also colour their call-out text.
    for color in (
        theme.reference,
        theme.reference_secondary,
        theme.positive,
        theme.negative,
    ):
        assert contrast_ratio(color, theme.plot_background) >= TEXT_CONTRAST, color
    # Text inside an overlay box, the translucent box sitting on the plot area.
    box = _blend(theme.overlay_background, theme.plot_background)
    assert contrast_ratio(theme.text, box) >= TEXT_CONTRAST


@BUILTINS
def test_label_carrying_scales_are_readable_under_cell_text(theme: Theme) -> None:
    for scale in (theme.diverging_scale, theme.sequential_scale):
        for position, color in scale:
            ratio = contrast_ratio(theme.cell_text, color)
            assert ratio >= TEXT_CONTRAST, (position, color, ratio)


@BUILTINS
def test_series_colours_stand_out_from_the_plot_area(theme: Theme) -> None:
    for color in theme.colorway:
        assert contrast_ratio(color, theme.plot_background) >= MARK_CONTRAST, color


def test_builtins_are_in_parity() -> None:
    assert set(get_args(ThemeName)) == set(BUILTIN_THEMES)
    assert len(DARK.colorway) == len(LIGHT.colorway)
    for field in dataclasses.fields(Theme):
        dark, light = getattr(DARK, field.name), getattr(LIGHT, field.name)
        if field.name.endswith("_scale"):
            # Same stop positions: a value lands on the same stop in either theme.
            assert [p for p, _ in dark] == [p for p, _ in light], field.name


def test_heatmap_template_uses_cell_text() -> None:
    # The scale contrast invariant only holds if cells are labelled in cell_text.
    for theme in BUILTIN_THEMES.values():
        heatmap = build_template(theme).data.heatmap[0]
        assert heatmap.textfont.color == theme.cell_text


# --- validation -------------------------------------------------------------------


def test_lists_are_stored_as_tuples_so_a_theme_stays_hashable() -> None:
    theme = dataclasses.replace(
        DARK,
        colorway=["#111111", "#222222"],  # type: ignore[arg-type]
        severity_scale=[[0, "#000000"], [1, "#ffffff"]],  # type: ignore[arg-type]
    )
    assert theme.colorway == ("#111111", "#222222")
    assert theme.severity_scale == ((0.0, "#000000"), (1.0, "#ffffff"))
    assert hash(theme) == hash(dataclasses.replace(theme))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"text": "white"}, "Theme: text='white' is not a colour"),
        ({"colorway": ()}, "Theme: colorway is empty"),
        ({"colorway": ("#fff", "blue")}, "Theme: colorway='blue' is not a colour"),
        (
            {"sequential_scale": ((0.1, "#000"), (1, "#fff"))},
            "Theme: sequential_scale must run from position 0 to position 1",
        ),
        (
            {
                "diverging_scale": (
                    (0, "#000"),
                    (0.6, "#111"),
                    (0.5, "#222"),
                    (1, "#fff"),
                )
            },
            "Theme: diverging_scale positions must rise, got 0.5 after 0.6",
        ),
        ({"severity_scale": ((0, "#000"),)}, "must run from position 0"),
        ({"font_size": 0}, "Theme: font_size=0 is not valid. Use a whole number"),
        ({"row_gap_px": True}, "Theme: row_gap_px=True is not valid"),
        (
            # NaN compares False with everything, so an ordering check alone
            # would let it through.
            {"sequential_scale": ((0, "#000"), (float("nan"), "#888"), (1, "#fff"))},
            "Theme: sequential_scale position=nan is not valid",
        ),
        ({"font_family": " "}, "Theme: font_family=' ' must be a non-empty string"),
    ],
)
def test_invalid_values_raise_naming_the_field(
    change: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message.replace("(", r"\(")):
        dataclasses.replace(DARK, **change)  # type: ignore[arg-type]


# --- global theme, per-call override, templates -------------------------------------


@pytest.mark.usefixtures("restore_theme")
def test_per_call_theme_beats_the_global_one() -> None:
    set_theme("light")
    assert get_theme() is LIGHT
    assert resolve_theme(None, caller="bar_plot") is LIGHT
    assert resolve_theme("dark", caller="bar_plot") is DARK
    custom = dataclasses.replace(DARK, grid="#333333")
    assert resolve_theme(custom, caller="bar_plot") is custom
    # Built-ins by name never change, whatever the global theme is.
    set_theme(custom)
    assert get_theme("dark") is DARK


@pytest.mark.usefixtures("restore_theme")
def test_set_theme_leaves_plotlys_default_template_alone() -> None:
    before = pio.templates.default
    set_theme("light")
    assert pio.templates.default == before


@pytest.mark.parametrize(
    ("call", "caller"),
    [
        (lambda: resolve_theme("blue", caller="bar_plot"), "bar_plot"),  # type: ignore[arg-type]
        (lambda: set_theme("blue"), "set_theme"),  # type: ignore[arg-type]
        (lambda: get_theme("blue"), "get_theme"),  # type: ignore[arg-type]
        (lambda: resolve_theme(3, caller="bar_plot"), "bar_plot"),  # type: ignore[arg-type]
    ],
)
def test_unknown_theme_names_the_caller_and_the_value(
    call: Callable[[], object], caller: str
) -> None:
    with pytest.raises(ValueError, match=rf"^{caller}: theme=.* is not a built-in"):
        call()


def test_builtins_are_registered_as_plotly_templates() -> None:
    for name, theme in BUILTIN_THEMES.items():
        template = pio.templates[registry.TEMPLATE_PREFIX + name]
        assert template.layout.paper_bgcolor == theme.background
        assert list(template.layout.colorway) == list(theme.colorway)
    # The registered copy is not the cached one: editing it can't leak into plots.
    pio.templates["easy_viz_dark"].layout.paper_bgcolor = "#123456"
    try:
        assert build_template(DARK).layout.paper_bgcolor == DARK.background
    finally:
        pio.templates["easy_viz_dark"].layout.paper_bgcolor = DARK.background


def _blend(foreground: str, background: str) -> str:
    """Hex of ``foreground`` composited over an opaque ``background``."""
    fg, bg = parse_color(foreground), parse_color(background)
    channels = (f * fg.a + b * (1 - fg.a) for f, b in zip(fg[:3], bg[:3], strict=True))
    return "#" + "".join(f"{round(c):02x}" for c in channels)
