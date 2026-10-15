"""The public-function contract, run on every registered plot function.

Every public plot function must, on pandas, polars **and** pyarrow input:

1. return a ``go.Figure``;
2. leave the input table unchanged;
3. give every trace a ``meta`` role from ``easy_viz._meta.ROLES``;
4. apply the active theme (the figure carries the theme's Plotly template);
5. show the ``title`` it was given.

How to register a function
--------------------------
Add one ``ContractCase`` to ``REGISTRY`` (below) in the same change that exports the
function in ``easy_viz.__all__``: the function, a few rows of data that make a valid
call, and the positional arguments / options of a minimal valid call. Do not pass
``title``: the title check adds it. A second test fails for every public plot function
(a callable in ``easy_viz.__all__`` defined under ``easy_viz.plots``) that is missing
from the registry, so a function cannot ship unchecked.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

import narwhals as nw
import pandas as pd
import plotly.graph_objects as go
import pytest
from conftest import MakeFrame, public_plot_functions

import easy_viz
from easy_viz._layout import apply_base_layout
from easy_viz._meta import ROLES
from easy_viz.theme import get_theme
from easy_viz.theme.theme import build_template

TITLE = "Contract title"
NO_FUNCTIONS = (
    "REGISTRY is empty: no public plot function is registered yet. Register each "
    "new one as a ContractCase, see the module docstring."
)


@dataclass(frozen=True)
class ContractCase:
    """A public plot function with the smallest valid call."""

    function: Callable[..., go.Figure]
    # Columns of the input table: ``{"x": ["a", "b"], "y": [1, 2]}``.
    data: dict[str, list[object]]
    # Required columns, passed positionally after the table: ``("x", "y")``.
    args: tuple[object, ...] = ()
    # Options of the minimal call, passed by keyword.
    kwargs: dict[str, object] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.function.__name__


# Public plot functions with a minimal valid call. Empty until the first plot lands.
REGISTRY: tuple[ContractCase, ...] = ()


@pytest.fixture(params=REGISTRY or [None], ids=lambda c: c.name if c else "empty")
def case(request: pytest.FixtureRequest) -> ContractCase:
    """Each registered case in turn; skips (with the reason) while none exist."""
    if request.param is None:
        pytest.skip(NO_FUNCTIONS)
    registered: ContractCase = request.param
    return registered


def snapshot(table: object) -> tuple[str, str]:
    """Schema and content of a native table, comparable across a function call.

    ``repr`` makes NaN equal to NaN, which ``==`` would not.
    """
    frame = nw.from_native(table, eager_only=True)
    return repr(frame.schema), repr(frame.to_dict(as_series=False))


def run(case: ContractCase, table: object, **extra: object) -> go.Figure:
    return case.function(table, *case.args, **case.kwargs, **extra)


def assert_returns_figure(case: ContractCase, table: object) -> None:
    fig = run(case, table)
    assert isinstance(fig, go.Figure), (
        f"{case.name} returned {type(fig).__name__}. Public plot functions return a "
        f"plain go.Figure."
    )


def assert_input_unchanged(case: ContractCase, table: object) -> None:
    before = snapshot(table)
    run(case, table)
    assert snapshot(table) == before, (
        f"{case.name} changed the table it was given. Work on a copy: public "
        f"functions never mutate the input."
    )


def assert_traces_have_roles(case: ContractCase, table: object) -> None:
    fig = run(case, table)
    assert fig.data, f"{case.name} returned a figure without traces."
    untagged = [
        (index, trace.type, trace.meta)
        for index, trace in enumerate(fig.data)
        if not isinstance(trace.meta, dict) or trace.meta.get("role") not in ROLES
    ]
    assert not untagged, (
        f"{case.name}: traces without a valid role in meta (index, type, meta): "
        f"{untagged}. Build traces with easy_viz._meta.tag(trace, role); roles: "
        f"{sorted(ROLES)}."
    )


def assert_title_used(case: ContractCase, table: object) -> None:
    fig = run(case, table, title=TITLE)
    assert TITLE in (fig.layout.title.text or ""), (
        f"{case.name}: title={TITLE!r} does not appear in fig.layout.title.text. "
        f"Pass the title to _layout.apply_base_layout()."
    )


def assert_theme_applied(case: ContractCase, table: object) -> None:
    expected = build_template(get_theme())
    fig = run(case, table)
    assert fig.layout.template.to_plotly_json() == expected.to_plotly_json(), (
        f"{case.name}: the figure's template differs from the active theme's. "
        f"Finish with _layout.apply_base_layout(), which applies the theme."
    )


def test_returns_figure(case: ContractCase, make_frame: MakeFrame) -> None:
    assert_returns_figure(case, make_frame(case.data))


def test_input_is_not_modified(case: ContractCase, make_frame: MakeFrame) -> None:
    assert_input_unchanged(case, make_frame(case.data))


def test_every_trace_has_a_role(case: ContractCase, make_frame: MakeFrame) -> None:
    assert_traces_have_roles(case, make_frame(case.data))


def test_theme_is_applied(case: ContractCase, make_frame: MakeFrame) -> None:
    assert_theme_applied(case, make_frame(case.data))


def test_title_is_used(case: ContractCase, make_frame: MakeFrame) -> None:
    assert_title_used(case, make_frame(case.data))


def test_every_public_plot_function_is_registered() -> None:
    registered = {case.function for case in REGISTRY}
    missing = sorted(
        name
        for name, function in public_plot_functions().items()
        if function not in registered
    )
    assert not missing, (
        f"Public plot functions missing from tests/test_contract.py REGISTRY: "
        f"{missing}. Add a ContractCase for each (see the module docstring)."
    )


def test_registry_holds_only_exported_distinct_functions() -> None:
    names = [case.name for case in REGISTRY]
    exported = {getattr(easy_viz, name, None) for name in easy_viz.__all__}
    assert len(set(names)) == len(names), f"Duplicate registry entries: {names}."
    unexported = [c.name for c in REGISTRY if c.function not in exported]
    assert not unexported, (
        f"Registered but not exported in easy_viz.__all__: {unexported}. Register "
        f"only public functions, and export the function in the same change."
    )


# --- The checks themselves: each must fail on a function that breaks the contract ---


def _good(df: object, *, title: str | None = None) -> go.Figure:
    fig = go.Figure(go.Bar(x=[1], meta={"role": "data", "group": None}))
    apply_base_layout(
        fig, title=title, subtitle=None, width=None, height=None, theme=get_theme()
    )
    return fig


def _unthemed(df: object, *, title: str | None = None) -> go.Figure:
    return go.Figure(go.Bar(x=[1], meta={"role": "data"})).update_layout(title=title)


def _untagged(df: object, *, title: str | None = None) -> go.Figure:
    return go.Figure(go.Bar(x=[1])).update_layout(title=title)


def _wrong_role(df: object, *, title: str | None = None) -> go.Figure:
    return go.Figure(go.Bar(x=[1], meta={"role": "bars"})).update_layout(title=title)


def _ignores_title(df: object, *, title: str | None = None) -> go.Figure:
    return go.Figure(go.Bar(x=[1], meta={"role": "data"}))


def _not_a_figure(df: object, *, title: str | None = None) -> go.Figure:
    return {}  # the violation under test


def _mutates(df: pd.DataFrame, *, title: str | None = None) -> go.Figure:
    df["added"] = 1
    return _good(df, title=title)


def _case(function: Callable[..., go.Figure]) -> ContractCase:
    return ContractCase(function, data={"a": [1.0, float("nan")]})


@pytest.mark.parametrize(
    ("check", "function"),
    [
        (assert_traces_have_roles, _untagged),
        (assert_traces_have_roles, _wrong_role),
        (assert_title_used, _ignores_title),
        (assert_returns_figure, _not_a_figure),
        (assert_input_unchanged, _mutates),
        (assert_theme_applied, _unthemed),
    ],
)
def test_checks_fail_on_a_function_that_breaks_the_contract(
    check: Callable[[ContractCase, object], None], function: Callable[..., go.Figure]
) -> None:
    table = pd.DataFrame({"a": [1.0, float("nan")]})
    with pytest.raises(AssertionError):
        check(_case(function), table)


@pytest.mark.parametrize(
    "check",
    [
        assert_returns_figure,
        assert_input_unchanged,
        assert_traces_have_roles,
        assert_title_used,
        assert_theme_applied,
    ],
)
def test_checks_pass_on_a_function_that_keeps_the_contract(
    check: Callable[[ContractCase, object], None],
) -> None:
    # NaN in the table: the unchanged-input check must not trip over NaN != NaN.
    check(_case(_good), pd.DataFrame({"a": [1.0, float("nan")]}))
