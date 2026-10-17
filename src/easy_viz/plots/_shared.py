"""What several plot functions share: option defaults, checks, labels, lines.

The library guide forbids copied logic between modules, so everything two plot
functions do the same way lives here once: the interval options and their
checks, the value label and format check, colour-map checks, and the
reference lines drawn across the plot (averages, targets, events).
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

from easy_viz._layout import format_value
from easy_viz._meta import tag
from easy_viz._typing import Agg
from easy_viz._validate import (
    check_positive_int,
    check_range,
    message,
    setting,
    warn_no_effect,
)
from easy_viz.stats.intervals import CiMethod, RandomState
from easy_viz.theme._color import ACCEPTED_FORMS, is_color
from easy_viz.theme.theme import Theme

# Option defaults shared by every function with confidence intervals, named so
# the no-effect warnings can tell a changed value.
CI_LEVEL = 0.95
N_BOOT = 2000
RANDOM_STATE = 0

# How an aggregate is named in titles and hover text ("Mean order_value").
AGG_WORDS: dict[str, str] = {
    "sum": "Total",
    "mean": "Mean",
    "median": "Median",
    "min": "Min",
    "max": "Max",
    "count": "Count",
}


def names(value: str | Sequence[str] | None) -> list[str]:
    """Return a slot or option given as one name or several, as a list."""
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)


def text(value: object) -> str:
    """Show a data value as plain text: dates without a midnight time part."""
    strftime = getattr(value, "strftime", None)
    if strftime is not None and hasattr(value, "hour"):
        midnight = (value.hour, value.minute, value.second) == (0, 0, 0)  # type: ignore[attr-defined]
        return str(strftime("%Y-%m-%d" if midnight else "%Y-%m-%d %H:%M"))
    return str(value)


def value_label(agg: Agg | None, ys: Sequence[str], series: str | None = None) -> str:
    """Name what the marks measure: the y column(s) with their aggregate.

    ``series`` names one column of a wide table; otherwise every ``y`` is
    listed.
    """
    if agg == "count":
        return AGG_WORDS["count"]
    label = series if series is not None else ", ".join(ys)
    return label if agg is None else f"{AGG_WORDS[agg]} {label}"


def plotly_list(values: npt.NDArray[np.float64]) -> list[float | None]:
    """NaN as None: Plotly draws no mark for a missing value."""
    return [None if math.isnan(v) else float(v) for v in values]


def conflict(
    func: str, param: str, value: object, other: str, other_value: object
) -> str:
    """Build the standard message for two options set together."""
    return message(
        func,
        f"{setting(param, value)} cannot be combined with "
        f"{setting(other, other_value)}",
        "Remove one of them",
    )


def check_shape(
    func: str,
    *,
    x: str,
    y: object,
    ys: Sequence[str],
    color: str | None,
    agg: Agg | None,
    same_column_fix: str,
) -> None:
    """Check the query-result shape (conventions, rules 2 and 3).

    ``y`` is needed unless ``agg="count"``; ``color`` can't be ``x`` itself
    (``same_column_fix`` says what to use instead); a list ``y`` (wide) and
    ``color`` (long) are two shapes and can't be combined.
    """
    if not ys and agg != "count":
        raise ValueError(
            message(
                func,
                "y is not set",
                "Pass the measure column as y, or use agg='count' to count rows",
            )
        )
    if color is not None and color == x:
        raise ValueError(
            message(
                func,
                f"{setting('color', color)} is the same column as x",
                same_column_fix,
            )
        )
    if len(ys) > 1 and color is not None:
        raise ValueError(
            message(
                func,
                f"{setting('y', y)} cannot be combined with {setting('color', color)}",
                "Pick one shape: a list y for one column per series, or color "
                "for series stacked in one column",
            )
        )


def check_value_format(func: str, spec: str | None) -> None:
    """Raise unless ``value_format`` is ``None`` or a Python format spec."""
    try:
        format_value(1234.5, spec)
    except (ValueError, TypeError):
        raise ValueError(
            message(
                func,
                f"{setting('value_format', spec)} is not a Python format spec",
                "Use one such as '.3g', ',.0f' or '.1%'",
            )
        ) from None


def check_interval_options(
    func: str,
    *,
    ci: CiMethod | None,
    agg: Agg | None,
    ci_level: float,
    n_boot: int,
    random_state: RandomState,
) -> None:
    """Check ``ci`` and its settings; warn for settings without effect.

    ``ci`` needs ``agg="mean"`` or ``"median"`` (an interval describes rows
    combined into one value), and ``"sem"`` describes a mean only.
    """
    if ci is not None:
        if agg not in ("mean", "median"):
            raise ValueError(
                message(
                    func,
                    f"{setting('ci', ci)} needs agg='mean' or agg='median', got "
                    f"{setting('agg', agg)}",
                    "Pass the raw rows with agg='mean' or 'median', or remove ci",
                )
            )
        if ci == "sem" and agg == "median":
            raise ValueError(
                message(
                    func,
                    "ci='sem' cannot be combined with agg='median'",
                    "The standard error describes a mean: use ci='bootstrap', or "
                    "agg='mean'",
                )
            )
    check_range(func, "ci_level", ci_level, low=0, high=1, include_low=False,
                include_high=False)  # fmt: skip
    check_positive_int(func, "n_boot", n_boot)
    if not (
        random_state is None
        or isinstance(random_state, np.random.Generator)
        or (
            isinstance(random_state, int)
            and not isinstance(random_state, bool)
            and random_state >= 0
        )
    ):
        raise ValueError(
            message(
                func,
                f"{setting('random_state', random_state)} is not valid",
                "Use a whole number of 0 or more, a numpy Generator, or None",
            )
        )
    if ci is None and ci_level != CI_LEVEL:
        warn_no_effect(func, "ci_level", ci_level, "without ci")
    if ci != "bootstrap":
        if n_boot != N_BOOT:
            warn_no_effect(func, "n_boot", n_boot, "unless ci='bootstrap'")
        if not (isinstance(random_state, int) and random_state == RANDOM_STATE):
            warn_no_effect(func, "random_state", random_state, "unless ci='bootstrap'")


def warn_hover_with_agg(
    func: str, hover: Sequence[str], agg: Agg | None, mark: str
) -> None:
    """Warn that ``hover`` has no effect once rows are combined into one ``mark``."""
    if hover and agg is not None:
        shown = hover[0] if len(hover) == 1 else list(hover)
        warn_no_effect(
            func,
            "hover",
            shown,
            f"with {setting('agg', agg)}: a combined {mark} has no single value for it",
        )


def check_color_map(
    func: str, color_map: Mapping[str, str] | None, *, multi: bool, fix: str
) -> None:
    """Raise unless ``color_map`` is unset, or maps series to readable colours.

    ``multi`` tells whether the call draws several series; ``fix`` is the
    advice when it doesn't.
    """
    if color_map is None:
        return
    if not multi:
        raise ValueError(message(func, "color_map needs several series", fix))
    for name, value in color_map.items():
        if not isinstance(value, str) or not is_color(value):
            raise ValueError(
                message(
                    func,
                    f"color_map[{name!r}]={value!r} is not a colour easy-viz can read",
                    f"Use {ACCEPTED_FORMS}",
                )
            )


def check_series_colours(
    func: str,
    coloured: Sequence[str],
    color_map: Mapping[str, str] | None,
    theme: Theme,
    fix: str,
) -> None:
    """Raise if a series drawn in colour has none.

    With ``color_map``, it must cover every series in ``coloured``; without
    it, the theme's ``colorway`` must have a colour for each.
    """
    if color_map is not None:
        uncovered = [s for s in coloured if s not in color_map]
        if uncovered:
            raise ValueError(
                message(
                    func,
                    f"color_map has no colour for {uncovered[0]!r} "
                    f"({len(uncovered)} series without one)",
                    "Add every series to color_map",
                )
            )
    elif len(coloured) > len(theme.colorway):
        raise ValueError(
            message(
                func,
                f"{len(coloured)} series need {len(coloured)} colours, but the theme "
                f"has {len(theme.colorway)}",
                fix,
            )
        )


@dataclass(frozen=True, slots=True)
class ReferenceLine:
    """One labelled line across the plot, at ``value`` on a data axis."""

    group: str  # the trace's role group: "average", "target", "event"
    value: object  # a number, or a date or category on an x axis
    label: str  # already escaped
    color: str
    dash: str


def add_reference_lines(
    fig: go.Figure,
    lines: Sequence[ReferenceLine],
    theme: Theme,
    *,
    on: Literal["x", "y"],
) -> None:
    """Add labelled lines across the whole plot, as traces a role can select.

    ``on`` is the data axis the values sit on: ``"y"`` draws horizontal lines,
    ``"x"`` vertical ones. A line must span the whole plot, which a trace on
    the other data axis can't do (its ends would sit at the outer data points).
    Each line is drawn on a hidden overlay axis running from 0 to 1 across the
    plot instead. A layout shape would span the plot too, but carry no role.
    """
    for line in lines:
        if on == "x":
            # Above the plot area, where no mark can sit under the label.
            where: dict[str, object] = {
                "x": [line.value, line.value],
                "y": [0, 1],
                "yaxis": "y2",
            }
            position = "top center"
        else:
            where = {"x": [0, 1], "y": [line.value, line.value], "xaxis": "x2"}
            position = "top left"
        trace = go.Scatter(
            mode="lines+text",
            line={"color": line.color, "dash": line.dash},
            text=["", line.label],
            textposition=position,
            textfont={"color": line.color, "size": theme.label_font_size},
            hovertemplate=f"{line.label}<extra></extra>",
            showlegend=False,
            cliponaxis=False,
            **where,
        )
        fig.add_trace(tag(trace, "reference", line.group))
    if lines:
        # The overlay is the other axis letter: vertical lines span a y2 laid
        # over y, horizontal ones an x2 laid over x.
        across = "y" if on == "x" else "x"
        overlay = {"overlaying": across, "range": [0, 1], "visible": False,
                   "fixedrange": True}  # fmt: skip
        fig.update_layout({f"{across}axis2": overlay})
