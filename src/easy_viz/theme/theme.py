"""The ``Theme`` dataclass: every colour, font and size a figure uses, by role."""

from collections.abc import Sequence
from dataclasses import dataclass, fields
from functools import cache
from itertools import pairwise

import plotly.graph_objects as go

from easy_viz.theme._color import ACCEPTED_FORMS, is_color

type Color = str
"""A colour string: hex (``"#1a1a1a"``), ``"rgb(r, g, b)"`` or ``"rgba(...)"``."""

type ColorScale = tuple[tuple[float, Color], ...]
"""Colour scale stops ``((position, colour), ...)``, positions rising from 0 to 1."""

type Px = int
"""A size in screen pixels (font sizes included)."""


@dataclass(frozen=True, slots=True)
class Theme:
    """Every colour, font and size easy-viz draws with, named by the role it plays.

    A theme is immutable. Start from a built-in and change what you need::

        import dataclasses
        import easy_viz as ev

        brand = dataclasses.replace(ev.get_theme("light"), colorway=("#0b5cad",))
        ev.set_theme(brand)

    Lists passed for ``colorway`` or a colour scale are stored as tuples, so a
    theme stays hashable. Colours are hex, ``rgb()`` or ``rgba()`` strings.

    Parameters
    ----------
    background : str
        Figure surface around the plot area (Plotly ``paper_bgcolor``).
    plot_background : str
        Surface inside the axes (Plotly ``plot_bgcolor``).
    grid : str
        Grid lines.
    axis_line : str
        Zero lines, axis lines and ticks: one step stronger than ``grid``.
    text : str
        Titles, axis titles, legend and annotation text.
    muted_text : str
        Secondary text: subtitle and tick labels.
    overlay_background : str
        Fill of boxes drawn over the plot (legend boxes, annotation call-outs).
    overlay_border : str
        Border of those boxes.
    colorway : tuple of str
        Series colours, in the order series receive them.
    other : str
        The "Other" bucket that collects categories beyond ``top_n``.
    dimmed : str
        Marks pushed into the background by ``highlight``.
    neutral : str
        Marks that carry no series identity: outlier points, connector lines,
        an "overall" line drawn over coloured series.
    mark_outline : str
        Thin outline that separates overlapping markers and bars.
    reference : str
        Reference lines and their labels: averages, targets, cut-offs.
    reference_secondary : str
        A second reference line that must read apart from ``reference``
        (e.g. the median next to the mean).
    positive : str
        Good direction: gains, the maximum, values above target.
    negative : str
        Bad direction: losses, the minimum, values below target.
    cell_text : str
        Text on heatmap cells. Plotly draws all cell labels in one colour, so
        ``diverging_scale`` and ``sequential_scale`` are built to stay readable
        under it.
    diverging_scale : tuple of (float, str)
        Scale centred on a neutral midpoint, for cells that carry labels
        (correlations, differences).
    sequential_scale : tuple of (float, str)
        Low-to-high scale for cells that carry labels (counts, rates).
    marker_diverging_scale : tuple of (float, str)
        Diverging scale for markers, which carry no text, so its midpoint may
        be as light or dark as the surface allows.
    severity_scale : tuple of (float, str)
        Healthy-to-alarming ramp (e.g. share of missing values).
    font_family : str
        CSS font list for all text.
    font_size : int
        Base text size in px: ticks, legend, axis titles.
    title_font_size : int
        Figure title size in px.
    subtitle_font_size : int
        Subtitle size in px.
    label_font_size : int
        Small text in px: annotations and data labels.
    title_top_px : int
        Space between the figure's top edge and the title.
    title_gap_px : int
        Space between the title block and the plot area; subplot titles sit in
        it.
    row_gap_px : int
        Vertical gap between subplot rows: the lower row's title plus the upper
        row's tick labels.
    col_gap_px : int
        Horizontal gap between subplot columns: tick labels plus breathing room.
    row_plot_px : int
        Drawing height reserved for one subplot row.
    """

    background: Color
    plot_background: Color
    grid: Color
    axis_line: Color
    text: Color
    muted_text: Color
    overlay_background: Color
    overlay_border: Color
    colorway: tuple[Color, ...]
    other: Color
    dimmed: Color
    neutral: Color
    mark_outline: Color
    reference: Color
    reference_secondary: Color
    positive: Color
    negative: Color
    cell_text: Color
    diverging_scale: ColorScale
    sequential_scale: ColorScale
    marker_diverging_scale: ColorScale
    severity_scale: ColorScale
    font_family: str
    font_size: Px
    title_font_size: Px
    subtitle_font_size: Px
    label_font_size: Px
    title_top_px: Px
    title_gap_px: Px
    row_gap_px: Px
    col_gap_px: Px
    row_plot_px: Px

    def __post_init__(self) -> None:
        """Store sequences as tuples and reject values no figure can draw.

        Every field is checked by its declared type (``Color``, ``ColorScale``,
        ``Px``), so a new field is validated as soon as it is declared.
        """
        for field in fields(self):
            name, value = field.name, getattr(self, field.name)
            if field.type is Color:
                _check_color(name, value)
            elif field.type == tuple[Color, ...]:
                colorway = _as_tuple(name, value)
                if not colorway:
                    raise ValueError(
                        f"Theme: {name} is empty. Give at least one colour."
                    )
                for color in colorway:
                    _check_color(name, color)
                object.__setattr__(self, name, colorway)
            elif field.type is ColorScale:
                object.__setattr__(self, name, _checked_scale(name, value))
            elif field.type is Px:
                _check_px(name, value)
            elif field.type is str:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(
                        f"Theme: {name}={value!r} must be a non-empty string. "
                        "Pass a CSS font list such as 'Arial, sans-serif'."
                    )
            else:  # pragma: no cover - fails at import, when a built-in is made
                raise TypeError(
                    f"Theme: field {name} has a type with no validation rule. "
                    "Declare it as Color, ColorScale, Px or str."
                )


def _as_tuple(name: str, value: object) -> tuple[object, ...]:
    """Return a list or tuple as a tuple; reject anything else."""
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise TypeError(
            f"Theme: {name} must be a list or tuple, got {value!r}. "
            "Wrap the values in a list."
        )
    return tuple(value)


def _check_color(name: str, value: object) -> None:
    """Raise unless ``value`` is a colour string easy-viz can read."""
    if not isinstance(value, str) or not is_color(value):
        raise ValueError(
            f"Theme: {name}={value!r} is not a colour easy-viz can read. "
            f"Use {ACCEPTED_FORMS}."
        )


def _check_px(name: str, value: object) -> None:
    """Raise unless ``value`` is a positive whole number of pixels."""
    # bool is an int subclass; True would otherwise pass as 1 px.
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(
            f"Theme: {name}={value!r} must be a positive whole number of px. "
            "Pass a value such as 12."
        )


def _checked_scale(name: str, value: object) -> ColorScale:
    """Validate a colour scale and return it as a tuple of ``(float, str)``."""
    stops: list[tuple[float, Color]] = []
    for stop in _as_tuple(name, value):
        if isinstance(stop, str) or not isinstance(stop, Sequence) or len(stop) != 2:
            raise ValueError(
                f"Theme: {name} has the stop {stop!r}. "
                "Write each stop as (position, colour)."
            )
        position, color = stop
        if isinstance(position, bool) or not isinstance(position, int | float):
            raise ValueError(
                f"Theme: {name} has the position {position!r}. "
                "Positions are numbers from 0 to 1."
            )
        _check_color(name, color)
        stops.append((float(position), color))
    if len(stops) < 2 or stops[0][0] != 0 or stops[-1][0] != 1:
        positions = [p for p, _ in stops]
        raise ValueError(
            f"Theme: {name} must run from position 0 to position 1, got "
            f"{positions}. Start the first stop at 0 and end the last at 1."
        )
    for (before, _), (after, _) in pairwise(stops):
        if after <= before:
            raise ValueError(
                f"Theme: {name} positions must rise, got {after} after {before}. "
                "List the stops in ascending order."
            )
    return tuple(stops)


def _scale(scale: ColorScale) -> list[list[float | str]]:
    """Return a scale in the nested-list form Plotly documents."""
    return [[position, color] for position, color in scale]


@cache
def build_template(theme: Theme) -> go.layout.Template:
    """Turn a theme into a Plotly template (cached: a theme is immutable).

    The template carries only styling. Placement that depends on the figure
    (margins, size) is set by ``easy_viz._layout.apply_base_layout``.

    Parameters
    ----------
    theme : Theme
        The theme to convert.

    Returns
    -------
    go.layout.Template
        Assigning it to ``fig.layout.template`` copies it, so the cached
        object is never changed through a figure.
    """
    axis = {
        "gridcolor": theme.grid,
        "zerolinecolor": theme.axis_line,
        "linecolor": theme.axis_line,
        "tickcolor": theme.axis_line,
        "tickfont": {"color": theme.muted_text},
        "title": {"font": {"color": theme.text}},
    }
    polar_axis = {
        "gridcolor": theme.grid,
        "linecolor": theme.axis_line,
        "tickcolor": theme.axis_line,
        "tickfont": {"color": theme.muted_text},
    }
    colorbar = {
        "outlinewidth": 0,
        "tickcolor": theme.axis_line,
        "tickfont": {"color": theme.muted_text},
        "title": {"font": {"color": theme.text}},
    }
    layout = {
        "colorway": list(theme.colorway),
        "paper_bgcolor": theme.background,
        "plot_bgcolor": theme.plot_background,
        "font": {
            "family": theme.font_family,
            "size": theme.font_size,
            "color": theme.text,
        },
        "title": {
            "font": {"size": theme.title_font_size, "color": theme.text},
            "subtitle": {
                "font": {
                    "size": theme.subtitle_font_size,
                    "color": theme.muted_text,
                }
            },
            # Centred, anchored by its top edge at a fixed px distance from the
            # figure's top, so the title never depends on the figure height.
            "x": 0.5,
            "xanchor": "center",
            "yref": "container",
            "y": 1,
            "yanchor": "top",
            "pad": {"t": theme.title_top_px},
        },
        "xaxis": axis,
        "yaxis": axis,
        "polar": {
            "bgcolor": theme.plot_background,
            "angularaxis": polar_axis,
            "radialaxis": polar_axis,
        },
        "colorscale": {
            "sequential": _scale(theme.sequential_scale),
            "diverging": _scale(theme.diverging_scale),
        },
        "coloraxis": {
            "colorscale": _scale(theme.sequential_scale),
            "colorbar": colorbar,
        },
        "hoverlabel": {"font": {"family": theme.font_family}},
        "annotationdefaults": {
            "font": {"color": theme.text},
            "arrowcolor": theme.muted_text,
        },
        # add_hline / add_vline draw shapes: by default they are reference lines.
        "shapedefaults": {"line": {"color": theme.reference}},
    }
    heatmap = {
        "colorscale": _scale(theme.sequential_scale),
        "textfont": {"color": theme.cell_text},
        "colorbar": colorbar,
    }
    return go.layout.Template(
        layout=layout,
        data={"heatmap": [heatmap], "contour": [{"colorbar": colorbar}]},
    )
