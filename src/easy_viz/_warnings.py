"""The warning class for every non-fatal issue easy-viz reports."""

import os
import warnings
from pathlib import Path

# Frames from files under the package directory are skipped when Python picks the
# line a warning points at, so it always points at the user's own call. The prefix
# is compared as plain text with each frame's file name, so it is built from
# __file__ the same way (never resolved: a symlinked or mapped install would no
# longer match), and ends in a separator so a sibling like easy_viz_x.py isn't
# skipped.
_PACKAGE_DIR = str(Path(__file__).parent) + os.sep


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
