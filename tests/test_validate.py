import re
from typing import Literal

import numpy as np
import pytest

from easy_viz._typing import Agg, Orientation
from easy_viz._validate import (
    check_choice,
    check_conflict,
    check_positive_int,
    check_range,
    check_requires,
    message,
    warn_no_effect,
)
from easy_viz._warnings import EasyVizWarning


def test_message_adds_one_final_period() -> None:
    assert message("f", "x is wrong", "Fix it") == "f: x is wrong. Fix it."
    assert message("f", "x is wrong", "Did you mean 'y'?") == (
        "f: x is wrong. Did you mean 'y'?"
    )


def test_check_choice_reads_the_literal_alias() -> None:
    check_choice("bar_plot", "orientation", "vertical", Orientation)
    with pytest.raises(ValueError) as error:
        check_choice("bar_plot", "orientation", "sideways", Orientation)
    assert str(error.value) == (
        "bar_plot: orientation='sideways' is not valid. "
        "Use one of 'vertical', 'horizontal'."
    )
    # Unhashable and None values are reported, not crashed on.
    with pytest.raises(ValueError, match=r"agg=\['sum'\] is not valid"):
        check_choice("bar_plot", "agg", ["sum"], Agg)
    with pytest.raises(ValueError, match="agg=None is not valid"):
        check_choice("bar_plot", "agg", None, Agg)


def test_check_choice_rejects_a_non_literal() -> None:
    with pytest.raises(TypeError):
        check_choice("f", "p", "a", str)


def test_check_conflict_message_matches_conventions() -> None:
    with pytest.raises(ValueError) as error:
        check_conflict("bar_plot", color_by_value=True, color="region")
    assert str(error.value) == (
        "bar_plot: color_by_value=True cannot be combined with color='region'. "
        "Remove one of them."
    )


# np.False_ arrives when an option value is read from a table cell.
@pytest.mark.parametrize("unset", [None, False, np.False_, "", [], ()])
def test_check_conflict_ignores_unset_options(unset: object) -> None:
    check_conflict("bar_plot", color_by_value=unset, color="region")


def test_check_conflict_counts_zero_as_set() -> None:
    with pytest.raises(ValueError, match="top_n=0 cannot be combined with sort_by='y'"):
        check_conflict("bar_plot", top_n=0, sort_by="y")


def test_check_requires() -> None:
    check_requires(
        "line_plot", "avg_group_line", False, needs="color", needs_value=None
    )
    check_requires("line_plot", "avg_group_line", True, needs="color", needs_value="r")
    with pytest.raises(ValueError) as error:
        check_requires(
            "line_plot", "avg_group_line", True, needs="color", needs_value=None
        )
    assert str(error.value) == (
        "line_plot: avg_group_line=True needs color to be set. "
        "Set color, or remove avg_group_line."
    )


@pytest.mark.parametrize("value", [1, 25, np.int64(3)])
def test_check_positive_int_accepts(value: object) -> None:
    check_positive_int("bar_plot", "top_n", value)


@pytest.mark.parametrize("value", [0, -2, True, 2.0, "3", None])
def test_check_positive_int_rejects(value: object) -> None:
    expected = (
        f"bar_plot: top_n={value!r} is not valid. Use a whole number of 1 or more."
    )
    with pytest.raises(ValueError, match=re.escape(expected)):
        check_positive_int("bar_plot", "top_n", value)


def test_check_range_open_interval() -> None:
    check_range(
        "f", "ci_level", 0.95, low=0, high=1, include_low=False, include_high=False
    )
    for bad in (0, 1, 95, float("nan"), True, "0.9"):
        with pytest.raises(ValueError) as error:
            check_range(
                "f",
                "ci_level",
                bad,
                low=0,
                high=1,
                include_low=False,
                include_high=False,
            )
        assert str(error.value) == (
            f"f: ci_level={bad!r} is not valid. "
            "Use a number greater than 0 and less than 1."
        )


def test_check_range_closed_and_one_sided_bounds() -> None:
    check_range("f", "cutoff", 1.0, low=0, high=1, include_low=False)
    check_range("f", "bins", 0, low=0)
    with pytest.raises(ValueError, match=r"cutoff=1\.5 .* at most 1\."):
        check_range("f", "cutoff", 1.5, low=0, high=1, include_low=False)
    with pytest.raises(ValueError, match=r"bins=-1 .* Use a number at least 0\."):
        check_range("f", "bins", -1, low=0)


def test_warn_no_effect() -> None:
    mode: Literal["pooled"] = "pooled"
    with pytest.warns(EasyVizWarning) as record:
        warn_no_effect("line_plot", "avg_line_mode", mode, "without color")
    assert str(record[0].message) == (
        "line_plot: avg_line_mode='pooled' has no effect without color. Remove it."
    )
    # Points at the caller's line, not at easy-viz internals.
    assert record[0].filename == __file__
