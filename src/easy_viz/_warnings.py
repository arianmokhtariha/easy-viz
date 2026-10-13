"""The warning class for every non-fatal issue easy-viz reports."""

import warnings
from pathlib import Path

# Frames from files under the package directory are skipped when Python picks the
# line a warning points at, so it always points at the user's own call.
_PACKAGE_DIR = str(Path(__file__).resolve().parent)


class EasyVizWarning(UserWarning):
    """Non-fatal issue reported by easy-viz.

    Raised for automatic changes to the data (nulls dropped, categories folded
    into "Other") and for options that have no effect in the current mode. Filter
    it like any warning class::

        warnings.filterwarnings("ignore", category=ev.EasyVizWarning)
    """


def warn(message: str) -> None:
    """Issue ``message`` as an :class:`EasyVizWarning` at the user's call site.

    Parameters
    ----------
    message : str
        Text in the format ``"<function>: <what happened>. <how to change it>."``.
    """
    warnings.warn(message, EasyVizWarning, skip_file_prefixes=(_PACKAGE_DIR,))
