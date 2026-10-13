"""Fixtures shared by every test module."""

from collections.abc import Callable
from typing import Literal

import pandas as pd
import polars as pl
import pyarrow as pa
import pytest

Backend = Literal["pandas", "polars", "pyarrow"]
BACKENDS: tuple[Backend, ...] = ("pandas", "polars", "pyarrow")

# A native table of the given backend, built from a column -> values mapping.
MakeFrame = Callable[[dict[str, list[object]]], object]


def to_native(data: dict[str, list[object]], backend: Backend) -> object:
    """Build ``data`` as a native table of ``backend`` (None becomes a null)."""
    if backend == "pandas":
        return pd.DataFrame(data)
    if backend == "polars":
        return pl.DataFrame(data, strict=False)
    return pa.table(data)


@pytest.fixture(params=BACKENDS)
def make_frame(request: pytest.FixtureRequest) -> MakeFrame:
    """Build test tables on pandas, polars and pyarrow: one test run each."""
    backend: Backend = request.param
    return lambda data: to_native(data, backend)
