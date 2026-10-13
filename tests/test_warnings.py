import warnings

import pytest

from easy_viz._warnings import EasyVizWarning, warn


def test_warning_points_at_the_callers_file() -> None:
    # A warning blamed on an easy-viz file is useless: the user can't find which
    # of their calls triggered it.
    with pytest.warns(EasyVizWarning, match="f: dropped 2 rows") as record:
        warn("f: dropped 2 rows. Fill them in the query.")
    assert record[0].filename == __file__


def test_users_can_silence_easy_viz_warnings_only() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warnings.filterwarnings("ignore", category=EasyVizWarning)
        warn("f: silenced.")
        warnings.warn("other library", UserWarning, stacklevel=1)
    assert [str(w.message) for w in caught] == ["other library"]
