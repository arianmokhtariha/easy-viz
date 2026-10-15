import math
import re
import warnings

import pandas as pd
import plotly.graph_objects as go
import pytest
from conftest import MakeFrame

import easy_viz as ev
from easy_viz._warnings import EasyVizWarning
from easy_viz.stats.intervals import interval
from easy_viz.theme import get_theme

SALES = {
    "region": ["North", "South", "East"],
    "revenue": [300.0, 100.0, 200.0],
    "cost": [120.0, 80.0, 90.0],
}


def bars(fig: go.Figure) -> list[go.Bar]:
    return [t for t in fig.data if t.meta["role"] == "data"]


def by_role(fig: go.Figure, group: str) -> list[go.Scatter]:
    return [t for t in fig.data if t.meta == {"role": "reference", "group": group}]


# --- query-result shapes --------------------------------------------------------------


def test_pre_aggregated_rows_are_plotted_as_is_in_query_order(
    make_frame: MakeFrame,
) -> None:
    fig = ev.bar_plot(make_frame(SALES), "region", "revenue")
    (trace,) = bars(fig)
    assert list(trace.x) == ["North", "South", "East"]
    assert list(trace.y) == [300.0, 100.0, 200.0]
    assert fig.layout.xaxis.categoryarray == ("North", "South", "East")


def test_raw_rows_long_and_wide_shapes(make_frame: MakeFrame) -> None:
    raw = make_frame(
        {
            "region": ["N", "S", "N", "S", "N"],
            "device": ["a", "a", "b", "a", "a"],
            "revenue": [1.0, 2.0, 3.0, 4.0, 5.0],
            "cost": [1.0, 1.0, 1.0, 1.0, 1.0],
        }
    )
    long = ev.bar_plot(raw, "region", "revenue", color="device", agg="sum")
    assert [(t.name, list(t.y)) for t in bars(long)] == [
        ("a", [6.0, 6.0]),
        ("b", [3.0, None]),  # no S/b rows: no bar, not a zero
    ]
    wide = ev.bar_plot(raw, "region", ["revenue", "cost"], agg="sum")
    assert [(t.name, list(t.y)) for t in bars(wide)] == [
        ("revenue", [9.0, 6.0]),
        ("cost", [3.0, 2.0]),
    ]
    counted = ev.bar_plot(raw, "region", agg="count")
    assert list(bars(counted)[0].y) == [3.0, 2.0]


def test_repeated_categories_without_agg_raise_naming_agg(
    make_frame: MakeFrame,
) -> None:
    with pytest.raises(ValueError, match="agg"):
        ev.bar_plot(make_frame({"r": ["N", "N"], "v": [1.0, 2.0]}), "r", "v")


def test_a_time_x_keeps_its_dates_and_refuses_reordering() -> None:
    df = pd.DataFrame({"month": ["2025-02-01", "2025-01-01"], "orders": [5, 3]})
    fig = ev.bar_plot(df, "month", "orders")
    assert fig.layout.xaxis.type is None  # a date axis, not forced to categories
    assert not any(isinstance(value, str) for value in bars(fig)[0].x)
    with pytest.raises(ValueError, match=r"sort_by='value'.*time column"):
        ev.bar_plot(df, "month", "orders", sort_by="value")


# --- ordering and "Other" -------------------------------------------------------------

# Category A: device x has many low values and device y one high one, so A's
# overall mean (28) is below B's (50) while the sum of its bar means (110) is above.
SPLIT = {
    "cat": ["A"] * 5 + ["B", "B"],
    "device": ["x", "x", "x", "x", "y", "x", "y"],
    "value": [10.0, 10.0, 10.0, 10.0, 100.0, 50.0, 50.0],
}


def test_sorting_with_several_series_uses_each_categorys_own_aggregate(
    make_frame: MakeFrame,
) -> None:
    fig = ev.bar_plot(
        make_frame(SPLIT), "cat", "value", color="device", agg="mean", sort_by="value"
    )
    assert list(bars(fig)[0].x) == ["B", "A"]


def test_other_combines_cut_rows_with_the_same_aggregate(
    make_frame: MakeFrame,
) -> None:
    raw = make_frame(
        {
            "cat": ["a", "a", "b", "c", "c", "c"],
            "v": [10.0, 10.0, 1.0, 2.0, 2.0, 8.0],
        }
    )
    fig = ev.bar_plot(raw, "cat", "v", agg="mean", top_n=1, other=True)
    (trace,) = bars(fig)
    assert list(trace.x) == ["a", "Other"]
    # Mean of the four cut rows (13 / 4), not the mean of the cut means.
    assert trace.y[1] == pytest.approx(3.25)
    assert trace.marker.color[1] == get_theme().other
    assert (
        "first 1 of 3 cat values, the rest in Other" in fig.layout.title.subtitle.text
    )


def test_other_sums_pre_aggregated_values_and_never_collides_with_a_category() -> None:
    df = pd.DataFrame({"cat": ["Other", "b", "c"], "v": [5.0, 2.0, 3.0]})
    (trace,) = bars(ev.bar_plot(df, "cat", "v", top_n=1, other=True))
    assert list(trace.x) == ["Other", "Other (2 categories)"]
    assert list(trace.y) == [5.0, 5.0]


# --- statistics -----------------------------------------------------------------------


def test_error_bars_are_the_stats_interval_and_a_single_row_gets_none(
    make_frame: MakeFrame,
) -> None:
    values = [3.0, 9.0, 4.0, 12.0, 7.0]
    df = make_frame({"g": ["a"] * 5 + ["b"], "v": [*values, 6.0]})
    fig = ev.bar_plot(df, "g", "v", agg="median", ci="bootstrap", n_boot=500)
    expected = interval(
        values,
        statistic="median",
        method="bootstrap",
        level=0.95,
        n_boot=500,
        random_state=0,
    )
    error = bars(fig)[0].error_y
    assert error.array[0] == pytest.approx(expected.high - 7.0)
    assert error.arrayminus[0] == pytest.approx(7.0 - expected.low)
    assert error.array[1] is None


def test_small_groups_are_hatched_marked_and_explained(make_frame: MakeFrame) -> None:
    df = make_frame({"g": ["a", "a", "a", "b"], "v": [1.0, 2.0, 3.0, 4.0]})
    fig = ev.bar_plot(df, "g", "v", agg="mean", min_n=2, show_n=True)
    (trace,) = bars(fig)
    assert list(trace.marker.pattern.shape) == ["", "/"]
    assert trace.text == ("2<br>n=3", "4<br>n=1 ⚠")
    assert "fewer than 2 rows" in fig.layout.title.subtitle.text


# --- stacking, labels, reference lines ------------------------------------------------


def test_stack_totals_sit_beyond_the_end_the_net_value_points_to() -> None:
    df = pd.DataFrame(
        {
            "m": ["Jan", "Jan", "Feb", "Feb"],
            "kind": ["gain", "loss", "gain", "loss"],
            "v": [5.0, -2.0, 1.0, -4.0],
        }
    )
    fig = ev.bar_plot(df, "m", "v", color="kind", barmode="stack")
    (totals,) = by_role(fig, "total")
    assert list(totals.y) == [5.0, -4.0]  # top of the gains, bottom of the losses
    assert totals.text == ("<b>3</b>", "<b>-3</b>")
    assert fig.layout.barmode == "relative"


def test_labels_show_on_every_bar_or_on_none() -> None:
    few = pd.DataFrame({"c": list("abc"), "v": [1234.0, 5678.0, 91011.0]})
    assert all(bars(ev.bar_plot(few, "c", "v"))[0].text)
    many = pd.DataFrame({"c": [f"c{i}" for i in range(80)], "v": [123456.7] * 80})
    labels = bars(ev.bar_plot(many, "c", "v", value_format=",.2f"))[0].text
    assert set(labels) == {""}


def test_reference_lines_span_the_plot_and_the_average_leaves_out_other() -> None:
    df = pd.DataFrame({"c": list("abcd"), "v": [4.0, 2.0, 1.0, 1.0]})
    fig = ev.bar_plot(df, "c", "v", top_n=2, other=True, avg_line=True, target=5)
    (average,) = by_role(fig, "average")
    (target,) = by_role(fig, "target")
    assert list(average.y) == [3.0, 3.0]  # mean of a and b, not of the Other bar
    assert list(average.x) == [0, 1] and average.xaxis == "x2"
    assert fig.layout.xaxis2.overlaying == "x" and not fig.layout.xaxis2.visible
    assert target.text[1] == "Target: 5"


def test_titles_are_built_and_dollar_signs_escaped() -> None:
    df = pd.DataFrame({"c": ["$1 to $2"], "v": [1.0]})
    fig = ev.bar_plot(df, "c", "v", y_title="Revenue in $ and $")
    assert fig.layout.title.text == "<b>v by c</b>"
    assert "$" not in fig.layout.yaxis.title.text
    assert "$" not in bars(fig)[0].x[0]


# --- colour ---------------------------------------------------------------------------


def test_highlight_dims_every_other_category() -> None:
    theme = get_theme()
    fig = ev.bar_plot(pd.DataFrame(SALES), "region", "revenue", highlight="South")
    assert list(bars(fig)[0].marker.color) == [
        theme.dimmed,
        theme.colorway[0],
        theme.dimmed,
    ]


def test_color_map_fixes_series_colours_and_must_cover_every_series() -> None:
    df = pd.DataFrame(SALES)
    fig = ev.bar_plot(
        df, "region", ["revenue", "cost"], color_map={"cost": "#111111",
                                                       "revenue": "#222222"}
    )  # fmt: skip
    assert [t.marker.color for t in bars(fig)] == ["#222222", "#111111"]
    with pytest.raises(ValueError, match="no colour for 'cost'"):
        ev.bar_plot(df, "region", ["revenue", "cost"], color_map={"revenue": "#222"})


def test_value_colouring_modes() -> None:
    theme = get_theme()
    df = pd.DataFrame({"c": list("abc"), "v": [-1.0, 0.5, 2.0]})
    diverging = bars(ev.bar_plot(df, "c", "v", color_by_value="diverging"))[0]
    assert diverging.marker.cmid == 0 and diverging.marker.showscale
    sign = bars(ev.bar_plot(df, "c", "v", color_by_value="sign", color_midpoint=0.5))[0]
    assert list(sign.marker.color) == [theme.negative, theme.neutral, theme.positive]


# --- conflicts and no-effect options --------------------------------------------------

CONFLICTS = [
    ({"y": ["revenue", "cost"], "color": "region"}, ["y=", "color="]),
    ({"ci": "bootstrap"}, ["ci='bootstrap'", "agg"]),
    ({"agg": "median", "ci": "sem"}, ["ci='sem'", "agg='median'"]),
    ({"agg": "mean", "ci": "sem", "barmode": "stack", "color": "region"},
     ["ci='sem'", "barmode='stack'"]),
    ({"barmode": "percent", "avg_line": True, "color": "region"},
     ["avg_line=True", "barmode='percent'"]),
    ({"barmode": "percent", "target": 1.0, "color": "region"},
     ["target=1.0", "barmode='percent'"]),
    ({"barmode": "percent", "show_pct_of_total": True, "color": "region"},
     ["show_pct_of_total", "barmode='percent'"]),
    ({"other": True}, ["other=True", "top_n"]),
    ({"show_n": True}, ["show_n=True", "agg"]),
    ({"highlight": "North", "color": "region"}, ["highlight='North'", "color="]),
    ({"highlight": "North", "y": ["revenue", "cost"]}, ["highlight='North'", "y="]),
    ({"highlight": "North", "color_by_value": "sign"},
     ["highlight='North'", "color_by_value='sign'"]),
    ({"color_by_value": "sign", "color": "region"},
     ["color_by_value='sign'", "color="]),
    ({"color_by_value": "sign", "color_map": {"a": "#000000"}},
     ["color_by_value='sign'", "color_map"]),
    ({"colorscale": "Viridis"}, ["colorscale='Viridis'", "color_by_value"]),
    ({"color_midpoint": 1.0}, ["color_midpoint=1.0", "color_by_value"]),
    ({"color_map": {"a": "#000000"}}, ["color_map", "several series"]),
]  # fmt: skip


@pytest.mark.parametrize(("options", "named"), CONFLICTS)
def test_conflicting_options_raise_naming_both(
    options: dict[str, object], named: list[str]
) -> None:
    options = {"y": "revenue", **options}
    df = pd.DataFrame(SALES)
    with pytest.raises(ValueError) as error:
        ev.bar_plot(df, "region", **options)  # type: ignore[arg-type]
    text = str(error.value)
    assert text.startswith("bar_plot: ")
    for part in named:
        assert part in text, (part, text)


def test_percent_refuses_negative_values() -> None:
    df = pd.DataFrame({"c": ["a", "a"], "k": ["x", "y"], "v": [1.0, -1.0]})
    with pytest.raises(ValueError, match="values of 0 or more"):
        ev.bar_plot(df, "c", "v", color="k", barmode="percent")


@pytest.mark.parametrize(
    ("options", "param"),
    [
        ({"ascending": True}, "ascending"),
        ({"ci_level": 0.9}, "ci_level"),
        ({"n_boot": 100}, "n_boot"),
        ({"random_state": 3}, "random_state"),
        ({"min_n": 5}, "min_n"),
        ({"bargroupgap": 0.3}, "bargroupgap"),
        ({"barmode": "stack"}, "barmode"),
        ({"show_values": False, "text_position": "inside"}, "text_position"),
        ({"color_by_value": "sequential", "color_midpoint": 2.0}, "color_midpoint"),
        ({"color_by_value": "sign", "colorscale": "Viridis"}, "colorscale"),
    ],
)
def test_options_without_effect_warn(options: dict[str, object], param: str) -> None:
    with pytest.warns(EasyVizWarning, match=rf"{param}=.* has no effect"):
        ev.bar_plot(pd.DataFrame(SALES), "region", "revenue", **options)  # type: ignore[arg-type]


def test_the_default_call_warns_nothing() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        ev.bar_plot(pd.DataFrame(SALES), "region", "revenue")


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"value_format": ".3s"}, "not a Python format spec"),
        ({"colorscale": "NotAScale", "color_by_value": "sequential"},
         "not a colour scale"),
        ({"random_state": -1}, "random_state=-1"),
        ({"ci_level": 95}, "ci_level=95"),
        ({"color_map": {"cost": "red", "revenue": "#000"}, "y": ["revenue", "cost"]},
         "not a colour"),
    ],
)  # fmt: skip
def test_invalid_values_are_rejected(options: dict[str, object], message: str) -> None:
    options = {"y": "revenue", **options}
    with pytest.raises(ValueError, match=re.escape(message)):
        ev.bar_plot(pd.DataFrame(SALES), "region", **options)  # type: ignore[arg-type]


def test_too_many_series_for_the_theme_raise() -> None:
    n = len(get_theme().colorway) + 1
    df = pd.DataFrame({"c": ["a"] * n, "k": [str(i) for i in range(n)], "v": [1.0] * n})
    with pytest.raises(ValueError, match=f"{n} series need {n} colours"):
        ev.bar_plot(df, "c", "v", color="k")


def test_horizontal_bars_put_the_first_category_on_top_and_grow_in_height() -> None:
    df = pd.DataFrame({"c": [f"c{i}" for i in range(40)], "v": [1.0] * 40})
    fig = ev.bar_plot(df, "c", "v", orientation="horizontal")
    assert fig.layout.yaxis.autorange == "reversed"
    assert bars(fig)[0].orientation == "h"
    assert fig.layout.height > math.ceil(fig.layout.width * 0.4)


def test_the_value_axis_reads_like_the_labels() -> None:
    df = pd.DataFrame({"c": ["a", "b"], "change": [0.05, -0.02]})
    fig = ev.bar_plot(df, "c", "change", value_format="+.1%")
    assert bars(fig)[0].text == ("+5.0%", "-2.0%")
    assert fig.layout.yaxis.tickformat == "+.1%"
    # Without a spec d3 shares, Plotly keeps its own tick format.
    assert ev.bar_plot(df, "c", "change").layout.yaxis.tickformat is None
