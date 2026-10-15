"""Fixtures shared by every test module."""

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Literal

import pandas as pd
import plotly.graph_objects as go
import polars as pl
import pyarrow as pa
import pytest

import easy_viz

ROOT = Path(__file__).resolve().parents[1]

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


def public_plot_functions() -> dict[str, Callable[..., go.Figure]]:
    """Callables in ``easy_viz.__all__`` that are defined under ``easy_viz.plots``."""
    functions = {}
    for name in easy_viz.__all__:
        obj = getattr(easy_viz, name)
        module = getattr(obj, "__module__", "") or ""
        if callable(obj) and (module + ".").startswith("easy_viz.plots."):
            functions[name] = obj
    return functions


def load_script(name: str) -> ModuleType:
    """Import ``scripts/<name>.py`` as a module (``scripts/`` is not a package)."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered before running, so dataclasses can resolve the module's names.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
