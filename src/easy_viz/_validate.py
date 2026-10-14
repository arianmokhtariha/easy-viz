"""Runtime checks of plot options, with every message in one format.

Users don't run a type checker, so a public function re-checks its options at
runtime before computing anything. Every error and warning text is built by
:func:`message`, so the ``"<function>: <what is wrong>. <how to fix it>."``
format of ``docs/conventions.md`` can't drift between functions.
"""

import math
from collections.abc import Sized
from numbers import Integral, Real
from typing import get_args

import numpy as np

from easy_viz._warnings import warn


def message(func: str, problem: str, fix: str) -> str:
    """Build ``"<func>: <problem>. <fix>."``, the one message format.

    Parameters
    ----------
    func : str
        Public function name, e.g. ``"bar_plot"``.
    problem : str
        What is wrong, without a final period.
    fix : str
        How to fix it. A final period is added unless it already ends in
        ``.``, ``?`` or ``!``.

    Returns
    -------
    str
        The formatted message.
    """
    end = "" if fix.endswith((".", "?", "!")) else "."
    return f"{func}: {problem}. {fix}{end}"


def setting(param: str, value: object) -> str:
    """Show an option as the user wrote it: ``param=repr(value)``."""
    return f"{param}={value!r}"


def is_set(value: object) -> bool:
    """Whether an option counts as set: anything but ``None``, ``False`` or empty.

    ``0`` counts as set: it is a value the user chose (range checks reject it
    where it isn't allowed).
    """
    # numpy's False (e.g. read from a table cell) is not the False singleton.
    if value is None or value is False or (isinstance(value, np.bool_) and not value):
        return False
    return not (isinstance(value, Sized) and len(value) == 0)


def check_choice(func: str, param: str, value: object, choices: object) -> None:
    """Raise if ``value`` is not one of the values of the Literal alias ``choices``.

    Parameters
    ----------
    func, param : str
        Public function and parameter names, for the message.
    value : object
        The value received.
    choices : Literal alias
        E.g. ``Orientation``; its allowed values are read with ``get_args``.

    Raises
    ------
    ValueError
        ``"bar_plot: orientation='sideways' is not valid. Use one of
        'vertical', 'horizontal'."``
    """
    allowed = get_args(choices)
    if not allowed:
        raise TypeError(
            message("check_choice", f"{choices!r} is not a Literal alias", "Pass one")
        )
    if value not in allowed:
        options = ", ".join(repr(choice) for choice in allowed)
        raise ValueError(
            message(
                func, f"{setting(param, value)} is not valid", f"Use one of {options}"
            )
        )


def check_conflict(func: str, /, **options: object) -> None:
    """Raise if more than one of ``options`` is set (see :func:`is_set`).

    Pass the options as keywords, e.g.
    ``check_conflict("bar_plot", color_by_value=color_by_value, color=color)``.

    Raises
    ------
    ValueError
        Naming the first two options that are set, with their values.
    """
    chosen = [setting(name, value) for name, value in options.items() if is_set(value)]
    if len(chosen) > 1:
        raise ValueError(
            message(
                func,
                f"{chosen[0]} cannot be combined with {chosen[1]}",
                "Remove one of them",
            )
        )


def check_requires(
    func: str, param: str, value: object, *, needs: str, needs_value: object
) -> None:
    """Raise if option ``param`` is set but the option it depends on is not.

    Raises
    ------
    ValueError
        E.g. ``"line_plot: avg_group_line=True needs color to be set. Set color,
        or remove avg_group_line."``
    """
    if is_set(value) and not is_set(needs_value):
        raise ValueError(
            message(
                func,
                f"{setting(param, value)} needs {needs} to be set",
                f"Set {needs}, or remove {param}",
            )
        )


def check_positive_int(func: str, param: str, value: object) -> None:
    """Raise unless ``value`` is a whole number of 1 or more (``bool`` excluded).

    Raises
    ------
    ValueError
        ``"bar_plot: top_n=0 is not valid. Use a whole number of 1 or more."``
    """
    # bool is checked first: True is an Integral to Python, but never a count.
    ok = not isinstance(value, bool) and isinstance(value, Integral) and int(value) >= 1
    if not ok:
        raise ValueError(
            message(
                func,
                f"{setting(param, value)} is not valid",
                "Use a whole number of 1 or more",
            )
        )


def check_range(
    func: str,
    param: str,
    value: object,
    *,
    low: float | None = None,
    high: float | None = None,
    include_low: bool = True,
    include_high: bool = True,
) -> None:
    """Raise unless ``value`` is a real number within the given bounds.

    Parameters
    ----------
    func, param : str
        Public function and parameter names, for the message.
    value : object
        The value received. ``bool``, NaN and infinity are rejected.
    low, high : float or None, default None
        Bounds; ``None`` means unbounded on that side.
    include_low, include_high : bool, default True
        Whether each bound itself is allowed.

    Raises
    ------
    ValueError
        E.g. ``"line_plot: ci_level=95 is not valid. Use a number greater than 0
        and less than 1."``
    """
    number = (
        float(value)
        if not isinstance(value, bool) and isinstance(value, Real)
        else math.nan
    )
    ok = math.isfinite(number)
    if ok and low is not None:
        ok = number >= low if include_low else number > low
    if ok and high is not None:
        ok = number <= high if include_high else number < high
    if not ok:
        bounds = []
        if low is not None:
            bounds.append(f"{'at least' if include_low else 'greater than'} {low:g}")
        if high is not None:
            bounds.append(f"{'at most' if include_high else 'less than'} {high:g}")
        wanted = " ".join(["Use a number", " and ".join(bounds)]).strip()
        raise ValueError(message(func, f"{setting(param, value)} is not valid", wanted))


def warn_no_effect(
    func: str, param: str, value: object, when: str, fix: str = "Remove it"
) -> None:
    """Warn that an option is ignored in the current mode.

    Parameters
    ----------
    func, param : str
        Public function and parameter names, for the message.
    value : object
        The value received.
    when : str
        The mode, completing "has no effect ...", e.g. ``"without color"``.
    fix : str, default "Remove it"
        How to make the warning go away.
    """
    warn(message(func, f"{setting(param, value)} has no effect {when}", fix))
