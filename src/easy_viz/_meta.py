"""Trace roles: tags that let users target parts of a figure after the fact."""

from typing import Literal, get_args

from plotly.basedatatypes import BaseTraceType

# The vocabulary is documented in docs/conventions.md (Trace roles); a new role
# is added there and here in the same change.
Role = Literal[
    "data",
    "trendline",
    "ci",
    "reference",
    "marginal",
    "density",
    "cumulative",
    "highlight",
]
ROLES: frozenset[str] = frozenset(get_args(Role))


def tag[T: BaseTraceType](trace: T, role: Role, group: str | None = None) -> T:
    """Set ``trace.meta`` to ``{"role": role, "group": group}`` and return it.

    Parameters
    ----------
    trace : plotly trace
        Trace to tag; modified in place.
    role : Role
        What the trace is (see ``ROLES``).
    group : str or None, default None
        The series the trace belongs to (e.g. the ``color`` category), so users
        can target one series' trendline. ``None`` when the plot has one series.

    Returns
    -------
    plotly trace
        The same trace, so the call can wrap a constructor.

    Raises
    ------
    ValueError
        If ``role`` is not a known role (a programming error inside easy-viz).
    """
    if role not in ROLES:
        raise ValueError(
            f"tag: unknown trace role {role!r}. Use one of {sorted(ROLES)}."
        )
    trace.meta = {"role": role, "group": group}
    return trace
