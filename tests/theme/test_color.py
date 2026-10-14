import pytest

from easy_viz.theme._color import contrast_ratio, parse_color, with_alpha

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
