"""The built-in themes, the active global theme, and their Plotly templates."""

from typing import Literal, get_args

import plotly.graph_objects as go
import plotly.io as pio

from easy_viz._validate import message, setting
from easy_viz.theme.theme import Theme, build_template

ThemeName = Literal["dark", "light"]

# Prefix of the Plotly template names the built-ins are registered under, so users
# can style their own figures with template="easy_viz_dark".
TEMPLATE_PREFIX = "easy_viz_"

# The house style of the original module: a near-black page around a neutral dark
# plot area, Plotly's qualitative palette, gold reference lines.
DARK = Theme(
    background="#0e1117",
    plot_background="#1a1a1a",
    grid="rgba(128,128,128,0.2)",
    axis_line="#454a54",
    text="#ffffff",
    muted_text="#aab0bb",
    overlay_background="rgba(0,0,0,0.6)",
    overlay_border="rgba(255,255,255,0.15)",
    colorway=(
        "#636EFA",
        "#EF553B",
        "#00CC96",
        "#AB63FA",
        "#FFA15A",
        "#19D3F3",
        "#FF6692",
        "#B6E880",
        "#FF97FF",
        "#FECB52",
    ),
    other="#4a4a4a",
    dimmed="#3a3e47",
    neutral="rgba(220,220,220,0.6)",
    mark_outline="rgba(255,255,255,0.25)",
    reference="#FFD700",
    reference_secondary="#FF6B6B",
    positive="#00CC96",
    negative="#EF553B",
    cell_text="#ffffff",
    # Anchored on a dark slate at 0 and interpolated in OKLab to red/blue poles:
    # every stop clears 4.5:1 under white cell text (classic RdBu peaks near
    # white at 0 and drops to 1.1:1), and lightness grows with |value|, so weak
    # values recede instead of glaring.
    diverging_scale=(
        (0.0, "#E3223A"),
        (0.1, "#C90430"),
        (0.2, "#A61A30"),
        (0.3, "#7C2B35"),
        (0.4, "#503038"),
        (0.5, "#272C35"),
        (0.6, "#273B55"),
        (0.7, "#204978"),
        (0.8, "#16579A"),
        (0.9, "#1566B6"),
        (1.0, "#2877C8"),
    ),
    # Plot background up to #1566B6, the lightest blue that still clears 4.5:1
    # under white cell text.
    sequential_scale=(
        (0.0, "#1a1a1a"),
        (0.25, "#1c3350"),
        (0.5, "#1c4374"),
        (0.75, "#175496"),
        (1.0, "#1566B6"),
    ),
    # Classic RdBu: markers carry no text, so its near-white midpoint is fine.
    marker_diverging_scale=(
        (0.0, "#B2182B"),
        (0.1, "#D6604D"),
        (0.2, "#F4A582"),
        (0.35, "#FDDBC7"),
        (0.5, "#F7F7F7"),
        (0.65, "#D1E5F0"),
        (0.8, "#92C5DE"),
        (0.9, "#4393C3"),
        (1.0, "#2166AC"),
    ),
    severity_scale=((0.0, "#00CC96"), (0.5, "#FFA15A"), (1.0, "#EF553B")),
    font_family="Arial, Helvetica, sans-serif",
    font_size=13,
    title_font_size=18,
    subtitle_font_size=14,
    label_font_size=11,
    title_top_px=20,
    title_gap_px=50,
    row_gap_px=90,
    col_gap_px=110,
    row_plot_px=260,
)

# The dark theme's equal for white-page reports. Same roles, same hue order (series
# 3 is green in both), darkened where white needs it: every series colour clears
# 3:1 on the plot area, and text, reference and positive/negative colours 4.5:1.
LIGHT = Theme(
    background="#ffffff",
    plot_background="#f6f7f9",
    grid="#e1e4e9",
    axis_line="#b9bfc8",
    text="#1f2328",
    muted_text="#5b616e",
    overlay_background="rgba(255,255,255,0.85)",
    overlay_border="rgba(31,35,40,0.15)",
    colorway=(
        "#3b5bdb",
        "#e03e1a",
        "#0a9e73",
        "#8b48e0",
        "#d9700a",
        "#0b98b8",
        "#e0457b",
        "#5f9419",
        "#c445c4",
        "#a87e00",
    ),
    other="#9ea4ad",
    dimmed="#d3d7de",
    neutral="rgba(70,76,88,0.6)",
    mark_outline="rgba(255,255,255,0.7)",
    reference="#8a5c00",
    reference_secondary="#c0392b",
    positive="#1a7f37",
    negative="#cf222e",
    cell_text="#1f2328",
    # The mirror image of the dark scale: a near-white midpoint, OKLab-interpolated
    # to soft red/blue poles that stay light enough for dark cell text (4.8:1 at
    # the poles). Saturation, not lightness, grows with |value|.
    diverging_scale=(
        (0.0, "#ee5f56"),
        (0.1, "#f28076"),
        (0.2, "#f59d95"),
        (0.3, "#f5b9b4"),
        (0.4, "#f3d5d3"),
        (0.5, "#eef0f3"),
        (0.6, "#d0ddf4"),
        (0.7, "#b2c9f4"),
        (0.8, "#94b5f3"),
        (0.9, "#77a1f2"),
        (1.0, "#5a8cef"),
    ),
    # Plot background up to a mid blue that still clears 4.5:1 under dark text.
    sequential_scale=(
        (0.0, "#f6f7f9"),
        (0.25, "#ceddf9"),
        (0.5, "#a7c3f7"),
        (0.75, "#80a8f4"),
        (1.0, "#5a8cef"),
    ),
    # RdBu poles with a grey midpoint: RdBu's near-white middle vanishes on white.
    marker_diverging_scale=(
        (0.0, "#b2182b"),
        (0.1, "#bd4b4c"),
        (0.2, "#c66e6c"),
        (0.35, "#ce9f9d"),
        (0.5, "#cfcfcf"),
        (0.65, "#9db0c6"),
        (0.8, "#6b91bc"),
        (0.9, "#497cb4"),
        (1.0, "#2166ac"),
    ),
    severity_scale=((0.0, "#0a9e73"), (0.5, "#d9700a"), (1.0, "#e03e1a")),
    font_family="Arial, Helvetica, sans-serif",
    font_size=13,
    title_font_size=18,
    subtitle_font_size=14,
    label_font_size=11,
    title_top_px=20,
    title_gap_px=50,
    row_gap_px=90,
    col_gap_px=110,
    row_plot_px=260,
)

BUILTIN_THEMES: dict[str, Theme] = {"dark": DARK, "light": LIGHT}

_active: Theme = DARK


def _builtin(name: object, caller: str, param: str = "theme") -> Theme:
    """Return the built-in theme called ``name``, or raise naming ``caller``.

    ``param`` is the caller's parameter that received ``name``, for the message.
    """
    if isinstance(name, str) and name in BUILTIN_THEMES:
        return BUILTIN_THEMES[name]
    names = " or ".join(repr(n) for n in get_args(ThemeName))
    raise ValueError(
        message(
            caller,
            f"{setting(param, name)} is not a built-in theme",
            f"Use {names}, or pass an ev.Theme",
        )
    )


def get_theme(name: ThemeName | None = None) -> Theme:
    """Return the active theme, or a built-in one by name.

    Parameters
    ----------
    name : {"dark", "light"} or None, default None
        ``None`` returns the theme every plot currently uses (see
        :func:`set_theme`). A name returns that built-in, unchanged by
        :func:`set_theme`.

    Returns
    -------
    Theme
        Immutable. Customise a copy with ``dataclasses.replace``.

    Examples
    --------
    >>> import dataclasses
    >>> import easy_viz as ev
    >>> ev.get_theme().background == ev.get_theme("dark").background
    True
    >>> quiet = dataclasses.replace(ev.get_theme("light"), grid="#f0f0f0")
    """
    return _active if name is None else _builtin(name, "get_theme", "name")


def set_theme(theme: ThemeName | Theme) -> None:
    """Set the theme every later plot uses when its ``theme`` is ``None``.

    Only easy-viz figures change: Plotly's own default template
    (``plotly.io.templates.default``) is left alone, so other Plotly figures in
    the session keep their look. Each built-in is also registered as a Plotly
    template, ``"easy_viz_dark"`` and ``"easy_viz_light"``, for styling your own
    figures.

    Parameters
    ----------
    theme : {"dark", "light"} or Theme
        A built-in by name, or a custom :class:`Theme`.

    Examples
    --------
    >>> import easy_viz as ev
    >>> ev.set_theme("light")
    >>> ev.get_theme().background
    '#ffffff'
    >>> ev.set_theme("dark")
    """
    global _active
    _active = resolve_theme(theme, caller="set_theme")


def resolve_theme(theme: ThemeName | Theme | None, *, caller: str) -> Theme:
    """Return the theme a call should draw with.

    Parameters
    ----------
    theme : {"dark", "light"}, Theme or None
        A plot's ``theme`` argument. ``None`` means the active global theme.
    caller : str
        Name of the public function, used in the error message.

    Returns
    -------
    Theme
        The per-call theme if given, else the global one.

    Raises
    ------
    ValueError
        If ``theme`` is neither a built-in name, a :class:`Theme` nor ``None``.
    """
    if theme is None:
        return _active
    if isinstance(theme, Theme):
        return theme
    return _builtin(theme, caller)


for _name, _theme in BUILTIN_THEMES.items():
    # A copy, so editing pio.templates[...] can never reach the cached template.
    pio.templates[TEMPLATE_PREFIX + _name] = go.layout.Template(build_template(_theme))
