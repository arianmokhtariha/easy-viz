import dataclasses
import re

import pytest

from easy_viz.theme.registry import (
    BUILTIN_THEMES,
    DARK,
)
from easy_viz.theme.theme import build_template

# --- template --------------------------------------------------------------------


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
        # float() reads these, Plotly's colour validator doesn't.
        ({"grid": "rgb(1e2,0,0)"}, "Theme: grid='rgb(1e2,0,0)' is not a colour"),
        ({"grid": "rgb(-0,0,0)"}, "Theme: grid='rgb(-0,0,0)' is not a colour"),
        # One bad part rejects the whole colour, it is never skipped.
        ({"grid": "rgb(1,2,3,abc)"}, "Theme: grid='rgb(1,2,3,abc)' is not a colour"),
        ({"grid": "rgb(1,2,3,)"}, "Theme: grid='rgb(1,2,3,)' is not a colour"),
        # Plotly allows spaces around numbers, not tabs.
        # The message shows the value's repr, so the tab appears as "\t".
        ({"grid": "rgb(1,\t2,3)"}, r"Theme: grid='rgb(1,\t2,3)' is not a colour"),
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
    with pytest.raises(ValueError, match=re.escape(message)):
        dataclasses.replace(DARK, **change)  # type: ignore[arg-type]
