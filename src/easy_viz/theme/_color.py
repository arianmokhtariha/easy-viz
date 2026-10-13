"""Colour parsing and WCAG contrast maths, shared by theme validation and tests."""

import re
from typing import NamedTuple

# The colour forms a theme accepts. CSS colour names ("white") are left out on
# purpose: reading them would need a 148-entry lookup table, and hex says the same
# thing unambiguously.
_HEX = re.compile(r"#(?P<digits>[0-9a-fA-F]{3}|[0-9a-fA-F]{6})")
_FUNCTION = re.compile(r"(?P<name>rgba?)\((?P<args>[^()]*)\)")

ACCEPTED_FORMS = "hex ('#1a2b3c' or '#abc'), 'rgb(r, g, b)' or 'rgba(r, g, b, a)'"


class RGBA(NamedTuple):
    """A parsed colour: channels in 0-255, alpha in 0-1."""

    r: float
    g: float
    b: float
    a: float


def parse_color(color: str) -> RGBA:
    """Read a hex, ``rgb()`` or ``rgba()`` colour string.

    Parameters
    ----------
    color : str
        The colour, e.g. ``"#1a1a1a"``, ``"#fff"``, ``"rgb(26, 26, 26)"`` or
        ``"rgba(0, 0, 0, 0.6)"``. Surrounding whitespace is ignored.

    Returns
    -------
    RGBA
        Channels in 0-255 and alpha in 0-1.

    Raises
    ------
    ValueError
        If ``color`` is in none of those forms, or a channel is out of range.
    """
    text = color.strip() if isinstance(color, str) else ""
    if match := _HEX.fullmatch(text):
        digits = match["digits"]
        if len(digits) == 3:
            digits = "".join(d * 2 for d in digits)
        red, green, blue = (int(digits[i : i + 2], 16) for i in (0, 2, 4))
        return RGBA(red, green, blue, 1.0)
    if match := _FUNCTION.fullmatch(text):
        parts = [p.strip() for p in match["args"].split(",")]
        expected = 4 if match["name"] == "rgba" else 3
        try:
            values = [float(p) for p in parts]
        except ValueError:
            values = []
        if len(values) == expected:
            r, g, b = values[:3]
            a = values[3] if expected == 4 else 1.0
            if all(0 <= c <= 255 for c in (r, g, b)) and 0 <= a <= 1:
                return RGBA(r, g, b, a)
    raise ValueError(f"{color!r} is not a colour in a form easy-viz reads")


def is_color(color: str) -> bool:
    """Return whether :func:`parse_color` can read ``color``."""
    try:
        parse_color(color)
    except ValueError:
        return False
    return True


def with_alpha(color: str, alpha: float) -> str:
    """Return ``color`` as an ``rgba()`` string with the given opacity.

    Parameters
    ----------
    color : str
        Any colour :func:`parse_color` reads. Its own alpha is replaced.
    alpha : float
        Opacity in [0, 1], e.g. 0.25 for a translucent band fill.

    Returns
    -------
    str
        ``"rgba(r,g,b,alpha)"``.
    """
    if not 0 <= alpha <= 1:
        raise ValueError(
            f"with_alpha: alpha={alpha} is outside [0, 1]. Pass a value from 0 to 1."
        )
    r, g, b, _ = parse_color(color)
    return f"rgba({r:g},{g:g},{b:g},{alpha:g})"


def _channel_to_linear(channel: float) -> float:
    """Undo the sRGB gamma curve for one 0-255 channel (WCAG 2.x formula)."""
    c = channel / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(color: RGBA) -> float:
    """WCAG relative luminance of an opaque colour: 0 = black, 1 = white."""
    r, g, b = (_channel_to_linear(c) for c in color[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG contrast ratio between a colour and the opaque surface it sits on.

    A translucent foreground (e.g. ``rgba(255,255,255,0.6)``) is first blended
    onto the background, because that blend is what the reader actually sees.

    Parameters
    ----------
    foreground : str
        Text or mark colour.
    background : str
        Opaque surface colour.

    Returns
    -------
    float
        From 1 (no contrast) to 21 (black on white). WCAG asks 4.5 for text.

    Raises
    ------
    ValueError
        If ``background`` is translucent: the result would depend on whatever
        lies behind it.
    """
    bg = parse_color(background)
    if bg.a < 1:
        raise ValueError(
            f"contrast_ratio: background={background!r} is translucent. "
            "Pass an opaque surface colour."
        )
    fg = parse_color(foreground)
    blended = RGBA(
        fg.r * fg.a + bg.r * (1 - fg.a),
        fg.g * fg.a + bg.g * (1 - fg.a),
        fg.b * fg.a + bg.b * (1 - fg.a),
        1.0,
    )
    lighter, darker = sorted((_luminance(blended), _luminance(bg)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)
