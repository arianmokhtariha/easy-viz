"""Global output defaults: figure width and export resolution."""

from dataclasses import dataclass

from easy_viz._validate import check_positive_int, check_range


@dataclass(frozen=True, slots=True)
class Config:
    """Output defaults used when a call doesn't set them.

    Parameters
    ----------
    width : int, default 1400
        Figure width in px for plots called with ``width=None``.
    export_scale : float, default 2.0
        Resolution multiplier for static export (``save``, ``save_many``):
        2.0 writes a 1400 px wide figure as a 2800 px wide image.
    """

    width: int = 1400
    export_scale: float = 2.0

    def __post_init__(self) -> None:
        """Reject values no figure can use."""
        check_positive_int("set_config", "width", self.width)
        check_range(
            "set_config", "export_scale", self.export_scale, low=0, include_low=False
        )


_current = Config()


def get_config() -> Config:
    """Return the global output defaults.

    Returns
    -------
    Config
        The active defaults. It is immutable; change it with :func:`set_config`.
    """
    return _current


def set_config(
    *, width: int | None = None, export_scale: float | None = None
) -> Config:
    """Change the global output defaults for every later call.

    Parameters
    ----------
    width : int or None, default None
        New default figure width in px. ``None`` keeps the current value.
    export_scale : float or None, default None
        New default export resolution multiplier. ``None`` keeps the current
        value.

    Returns
    -------
    Config
        The new active defaults.

    Examples
    --------
    >>> import easy_viz as ev
    >>> ev.set_config(width=1100).width
    1100
    >>> ev.set_config(width=1400).width
    1400
    """
    global _current
    _current = Config(
        width=_current.width if width is None else width,
        export_scale=_current.export_scale if export_scale is None else export_scale,
    )
    return _current
