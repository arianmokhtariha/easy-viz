import subprocess
import sys
import warnings
from pathlib import Path

import pytest

import easy_viz
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


def test_warning_points_at_the_caller_when_the_import_path_is_not_normalised() -> None:
    # A notebook doing sys.path.insert(0, "../src") imports easy-viz through a
    # path with ".." and mixed separators in it; the skip prefix must match that
    # raw text. The warning has to start inside another easy-viz module (here
    # _data): warn()'s own frame is skipped whatever the prefix.
    src = Path(easy_viz.__file__).parents[1]
    raw = f"{src.as_posix()}/../{src.name}"
    # Python normalises PYTHONPATH entries at startup, so the raw path has to be
    # inserted at runtime, as the notebook does.
    code = "\n".join(
        [
            f"import sys; sys.path.insert(0, {raw!r})",
            "import warnings; warnings.simplefilter('always')",
            "import pandas as pd; from easy_viz._data import drop_nulls, load",
            "drop_nulls(load(pd.DataFrame({'a': [1.0, None]}), 'f', {'x': 'a'}), 'f')",
        ]
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stderr.startswith("<string>:4: EasyVizWarning"), result.stderr
