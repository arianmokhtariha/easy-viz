"""Static image export: one figure with ``save``, many with ``save_many``."""

import importlib.util
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal, get_args

import plotly.graph_objects as go
import plotly.io as pio

from easy_viz._validate import (
    check_choice,
    check_positive_int,
    check_range,
    message,
)
from easy_viz.config import get_config

ImageFormat = Literal["png", "jpg", "jpeg", "webp", "svg", "pdf"]
_FORMATS: tuple[str, ...] = get_args(ImageFormat)
_FORMAT_LIST = ", ".join(_FORMATS)

# Characters that would move a file out of the target directory, or that Windows
# refuses in a file name: checked up front so a batch never fails half-written.
_FORBIDDEN_NAME_CHARS = frozenset('<>:"/\\|?*')
# Device names Windows reserves, with or without an extension.
_RESERVED_NAMES = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + [f"{device}{n}" for device in ("COM", "LPT") for n in range(1, 10)]
)


def save(
    fig: go.Figure,
    path: str | os.PathLike[str],
    *,
    scale: float | None = None,
    width: int | None = None,
    height: int | None = None,
) -> Path:
    """Write one figure as a static image; the file extension picks the format.

    Needs the optional export dependencies (``pip install "easy-viz[export]"``)
    and Chrome. To write several figures, use :func:`save_many`: it starts Chrome
    once instead of once per figure.

    Parameters
    ----------
    fig : go.Figure
        The figure to write. It is not modified.
    path : str or os.PathLike
        Target file. The extension must be one of ``.png``, ``.jpg``, ``.jpeg``,
        ``.webp``, ``.svg``, ``.pdf`` (case-insensitive). Missing parent
        directories are created.
    scale : float or None, default None
        Resolution multiplier: 2 writes a 1400 px wide figure as a 2800 px wide
        image. ``None`` uses ``export_scale`` from :func:`set_config`. It also
        scales the page size of ``svg`` and ``pdf`` (2 writes a 1400 px figure
        as a 2800 px wide SVG), so pass ``scale=1`` for true-size vector files.
    width, height : int or None, default None
        Size in px, overriding the figure's own. ``None`` keeps the figure's size.

    Returns
    -------
    pathlib.Path
        The absolute path of the written file.

    Raises
    ------
    ValueError
        If the extension is missing or unsupported, or ``scale``, ``width`` or
        ``height`` is not positive.
    ImportError
        If kaleido is not installed.

    Examples
    --------
    >>> import easy_viz as ev
    >>> import plotly.graph_objects as go
    >>> fig = go.Figure(go.Bar(x=["a", "b"], y=[1, 2]))
    >>> ev.save(fig, "report/revenue.png")  # doctest: +SKIP
    PosixPath('/home/me/report/revenue.png')
    """
    image_format = _format_of(path)
    target = Path(path).expanduser().resolve()
    resolved_scale = _resolve_scale("save", scale)
    _check_pixels("save", "width", width)
    _check_pixels("save", "height", height)
    _require_kaleido("save")

    target.parent.mkdir(parents=True, exist_ok=True)
    pio.write_image(
        fig,
        target,
        format=image_format,
        scale=resolved_scale,
        width=width,
        height=height,
    )
    return target


def save_many(
    figs: Mapping[str, go.Figure],
    directory: str | os.PathLike[str],
    *,
    format: ImageFormat = "png",
    scale: float | None = None,
) -> list[Path]:
    """Write several figures as static images in one Chrome session.

    Each figure becomes ``<directory>/<name>.<format>``. This is much faster than
    calling :func:`save` in a loop, because Chrome starts once for the whole batch.
    Needs the optional export dependencies (``pip install "easy-viz[export]"``)
    and Chrome.

    Parameters
    ----------
    figs : mapping of str to go.Figure
        File name (without extension) to figure. A name must not be empty,
        ``.`` or ``..``, nor contain a slash, backslash or colon. Names must
        differ ignoring case, so no two files can overwrite each other.
    directory : str or os.PathLike
        Target directory. It is created if missing.
    format : {"png", "jpg", "jpeg", "webp", "svg", "pdf"}, default "png"
        Image format of every file.
    scale : float or None, default None
        Resolution multiplier, as in :func:`save`. ``None`` uses ``export_scale``
        from :func:`set_config`.

    Returns
    -------
    list of pathlib.Path
        The absolute paths of the written files, in the order of ``figs``.

    Raises
    ------
    ValueError
        If ``figs`` is empty, a name is invalid or repeated, ``format`` is
        unsupported, or ``scale`` is not positive.
    ImportError
        If kaleido is not installed.

    Examples
    --------
    >>> import easy_viz as ev
    >>> import plotly.graph_objects as go
    >>> figs = {
    ...     "revenue": go.Figure(go.Bar(x=["a", "b"], y=[1, 2])),
    ...     "cost": go.Figure(go.Bar(x=["a", "b"], y=[2, 1])),
    ... }
    >>> ev.save_many(figs, "report", format="svg")  # doctest: +SKIP
    [PosixPath('/home/me/report/revenue.svg'), PosixPath('/home/me/report/cost.svg')]
    """
    # Case-insensitive, like the extension save() reads: "PNG" works in both.
    image_format = format.lower() if isinstance(format, str) else format
    if image_format not in _FORMATS:
        # The message shows the value as the user passed it.
        check_choice("save_many", "format", format, ImageFormat)
    if not figs:
        raise ValueError(
            message(
                "save_many",
                "figs is empty, so there is nothing to write",
                "Pass a mapping such as {'revenue': fig}",
            )
        )
    _check_names(figs)
    resolved_scale = _resolve_scale("save_many", scale)
    _require_kaleido("save_many")

    folder = Path(directory).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    targets = [folder / f"{name}.{image_format}" for name in figs]
    figures = list(figs.values())
    # write_images ignores each figure's own layout size (it falls back to
    # Plotly's 700x500 default), unlike write_image. Pass the sizes explicitly so
    # a batch matches what save() would write.
    pio.write_images(
        figures,
        targets,
        format=image_format,
        scale=resolved_scale,
        width=[_layout_size(fig, "width") for fig in figures],
        height=[_layout_size(fig, "height") for fig in figures],
    )
    return targets


def _format_of(path: str | os.PathLike[str]) -> str:
    """Return the image format named by the extension of ``path``, as given."""
    suffix = Path(path).suffix
    extension = suffix.lstrip(".").lower()
    if extension in _FORMATS:
        return extension
    shown = f"{suffix!r}" if suffix else "no extension"
    raise ValueError(
        message(
            "save",
            f"path={os.fspath(path)!r} has {shown}, which is not a supported image "
            "format",
            f"End the path with one of: {_FORMAT_LIST} (for example "
            "'report/revenue.png')",
        )
    )


def _check_names(figs: Mapping[str, go.Figure]) -> None:
    """Raise if a key of ``figs`` cannot be used as a file name."""
    seen: dict[str, str] = {}
    for name in figs:
        if (
            not isinstance(name, str)
            or not name
            or name in {".", ".."}
            or _FORBIDDEN_NAME_CHARS.intersection(name)
            or any(ord(char) < 32 for char in name)
            or name.endswith((".", " "))
            or name.split(".")[0].upper() in _RESERVED_NAMES
        ):
            raise ValueError(
                message(
                    "save_many",
                    f"figs has the invalid file name {name!r}",
                    "Use a name such as 'revenue': not a reserved device name "
                    "(CON, NUL, ...), not ending in a dot or space, and without "
                    'any of < > : " / \\ | ? *',
                )
            )
        # Case-insensitive file systems (Windows, macOS) treat these as one file.
        if (other := seen.setdefault(name.lower(), name)) != name:
            raise ValueError(
                message(
                    "save_many",
                    f"figs has the names {other!r} and {name!r}, which are the "
                    "same file on case-insensitive file systems",
                    "Rename one",
                )
            )


def _resolve_scale(function: str, scale: float | None) -> float:
    """Return ``scale``, or the configured export scale when it is ``None``."""
    if scale is None:
        return get_config().export_scale
    # Plotly treats a falsy scale as "use the default", which would hide a 0.
    check_range(function, "scale", scale, low=0, include_low=False)
    return scale


def _check_pixels(function: str, name: str, value: int | None) -> None:
    """Raise if a size override is not a positive whole number of px."""
    if value is not None:
        check_positive_int(function, name, value)


def _layout_size(fig: go.Figure, attribute: Literal["width", "height"]) -> int | None:
    """Return the figure's own width or height, falling back to its template's."""
    size: int | None = fig.layout[attribute]
    if size is None:
        size = fig.layout.template.layout[attribute]
    return size


def _require_kaleido(function: str) -> None:
    """Raise an install hint if kaleido (the optional export engine) is missing."""
    # find_spec checks without importing: kaleido is optional and slow to import.
    if importlib.util.find_spec("kaleido") is None:
        raise ImportError(
            message(
                function,
                "static image export needs kaleido, which is not installed",
                'Run pip install "easy-viz[export]", then plotly_get_chrome if you '
                "have no Chrome",
            )
        )
