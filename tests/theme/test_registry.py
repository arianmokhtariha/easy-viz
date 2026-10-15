import dataclasses
import re
from collections.abc import Callable, Iterator
from typing import get_args

import plotly.io as pio
import pytest

from easy_viz.theme import registry
from easy_viz.theme._color import contrast_ratio, parse_color
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


@BUILTINS
def test_value_coloured_marks_stay_visible_at_every_value(theme: Theme) -> None:
    # Bars coloured by value: the smallest one must not vanish into the plot area.
    for position, color in theme.marker_sequential_scale:
        ratio = contrast_ratio(color, theme.plot_background)
        assert ratio >= MARK_CONTRAST, (position, color, ratio)


def test_builtins_are_in_parity() -> None:
    assert set(get_args(ThemeName)) == set(BUILTIN_THEMES)
    assert len(DARK.colorway) == len(LIGHT.colorway)
    for field in dataclasses.fields(Theme):
        dark, light = getattr(DARK, field.name), getattr(LIGHT, field.name)
        if field.name.endswith("_scale"):
            # Same stop positions: a value lands on the same stop in either theme.
            assert [p for p, _ in dark] == [p for p, _ in light], field.name


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
    ("call", "named"),
    [
        (lambda: resolve_theme("blue", caller="bar_plot"), "bar_plot: theme='blue'"),  # type: ignore[arg-type]
        (lambda: set_theme("blue"), "set_theme: theme='blue'"),  # type: ignore[arg-type]
        # get_theme's parameter is `name`: the message names the one the user typed.
        (lambda: get_theme("blue"), "get_theme: name='blue'"),  # type: ignore[arg-type]
        (lambda: resolve_theme(3, caller="bar_plot"), "bar_plot: theme=3"),  # type: ignore[arg-type]
    ],
)
def test_unknown_theme_names_the_caller_parameter_and_value(
    call: Callable[[], object], named: str
) -> None:
    with pytest.raises(ValueError, match=rf"^{re.escape(named)} is not a built-in"):
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
