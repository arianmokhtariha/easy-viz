import datetime as dt
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

# Monthly orders per region; March has no row for either region.
MONTHLY = {
    "month": ["2025-01-01", "2025-02-01", "2025-04-01"] * 2,
    "region": ["N"] * 3 + ["S"] * 3,
    "orders": [10.0, 12.0, 15.0, 4.0, 5.0, 7.0],
}


def by_role(fig: go.Figure, role: str) -> list[go.Scatter]:
    return [t for t in fig.data if t.meta["role"] == role]


def line(fig: go.Figure, group: str | None = None) -> go.Scatter:
    (trace,) = [t for t in by_role(fig, "data") if t.meta["group"] == group]
    return trace


def quiet_plot(*args: object, **kwargs: object) -> go.Figure:
    """Call line_plot, failing on any warning."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        return ev.line_plot(*args, **kwargs)  # type: ignore[arg-type]


# --- query-result shapes and the x axis -----------------------------------------------


def test_a_repeated_x_without_agg_raises_naming_agg(make_frame: MakeFrame) -> None:
    df = make_frame({"day": ["2025-01-01", "2025-01-01"], "v": [1.0, 2.0]})
    with pytest.raises(ValueError, match="agg"):
        ev.line_plot(df, "day", "v")


def test_numbers_are_drawn_sorted_and_text_keeps_the_query_order(
    make_frame: MakeFrame,
) -> None:
    numeric = quiet_plot(
        make_frame({"x": [3, 1, 2], "y": [30.0, 10.0, 20.0]}), "x", "y"
    )
    assert list(line(numeric).x) == [1.0, 2.0, 3.0]
    assert list(line(numeric).y) == [10.0, 20.0, 30.0]
    steps = make_frame({"step": ["visit", "cart", "paid"], "users": [9.0, 4.0, 2.0]})
    fig = quiet_plot(steps, "step", "users")
    assert list(line(fig).x) == ["visit", "cart", "paid"]
    assert fig.layout.xaxis.categoryarray == ("visit", "cart", "paid")


def test_series_without_a_calendar_join_only_their_own_points() -> None:
    # The two series share no x: on a shared axis each has holes at the other's
    # points, which must be bridged, or neither line would be drawn at all.
    df = pd.DataFrame({"x": [1, 3, 2, 4], "k": ["a", "a", "b", "b"],
                       "y": [1.0, 3.0, 2.0, 4.0]})  # fmt: skip
    fig = quiet_plot(df, "x", "y", color="k")
    assert list(line(fig, "a").y) == [1.0, None, 3.0, None]
    assert line(fig, "a").connectgaps is True


# --- the calendar (decision 0012) ---------------------------------------------


def test_an_empty_period_is_a_gap_and_the_default_warns_how_many(
    make_frame: MakeFrame,
) -> None:
    df = make_frame(MONTHLY)
    with pytest.warns(EasyVizWarning, match=r"1 of 4 months have no row"):
        fig = ev.line_plot(df, "month", "orders", color="region")
    north = line(fig, "N")
    assert [x.month for x in north.x] == [1, 2, 3, 4]
    assert list(north.y) == [10.0, 12.0, None, 15.0]
    assert north.connectgaps is False
    assert "1 empty month left as gaps" in fig.layout.title.subtitle.text
    # Asked for explicitly, the gap needs no warning.
    quiet_plot(df, "month", "orders", color="region", missing_periods="gap")


@pytest.mark.parametrize(
    ("mode", "march", "bridged"), [("zero", 0.0, False), ("connect", None, True)]
)
def test_an_empty_period_can_be_zero_or_bridged(
    make_frame: MakeFrame, mode: str, march: float | None, bridged: bool
) -> None:
    fig = quiet_plot(
        make_frame(MONTHLY), "month", "orders", color="region", missing_periods=mode
    )
    assert line(fig, "S").y[2] == march
    assert line(fig, "S").connectgaps is bridged


def test_raw_timestamps_need_a_grain_and_are_bucketed_into_it(
    make_frame: MakeFrame,
) -> None:
    df = make_frame(
        {
            "at": ["2025-01-01 09:13", "2025-01-01 17:40", "2025-01-02 08:05"],
            "v": [1.0, 2.0, 4.0],
        }
    )
    with pytest.raises(ValueError, match="time_grain"):
        ev.line_plot(df, "at", "v", agg="sum")
    fig = quiet_plot(df, "at", "v", agg="sum", time_grain="day")
    assert [x.day for x in line(fig).x] == [1, 2]
    assert list(line(fig).y) == [3.0, 4.0]
    assert fig.layout.xaxis.unifiedhovertitle.text == "%{x|%a %Y-%m-%d}"


def test_a_single_date_claims_no_grain_unless_one_is_given(
    make_frame: MakeFrame,
) -> None:
    df = make_frame({"m": ["2025-03-01", "2025-03-01"], "k": ["a", "b"],
                     "v": [1.0, 2.0]})  # fmt: skip
    fig = quiet_plot(df, "m", "v", color="k")
    assert fig.layout.xaxis.unifiedhovertitle.text is None
    assert not fig.layout.title.subtitle.text  # "auto" alone would say "yearly"
    given = quiet_plot(df, "m", "v", color="k", time_grain="month")
    assert given.layout.xaxis.unifiedhovertitle.text == "%{x|%b %Y}"
    assert given.layout.title.subtitle.text == "monthly"


def test_the_x_axis_ends_at_the_data_not_at_plotlys_padding() -> None:
    # Markers make Plotly pad the autorange by 5 % (five weeks on two years);
    # the axis runs from the first to the last month, with a small margin only.
    months = pd.date_range("2024-01-01", "2025-12-01", freq="MS")
    df = pd.DataFrame({"m": months, "v": range(len(months))})
    low, high = quiet_plot(df, "m", "v").layout.xaxis.range
    first, last = months[0].to_pydatetime(), months[-1].to_pydatetime()
    assert first - dt.timedelta(days=4) < low < first
    assert last < high < last + dt.timedelta(days=4)
    numeric = quiet_plot(pd.DataFrame({"x": [10, 1000], "y": [1.0, 2.0]}), "x", "y",
                         log_x=True)  # fmt: skip
    assert numeric.layout.xaxis.range == pytest.approx((0.99, 3.01))
    slider = quiet_plot(df, "m", "v", rangeslider=True).layout.xaxis
    assert slider.rangeslider.range == slider.range


def test_a_grain_needs_a_time_x() -> None:
    df = pd.DataFrame({"x": [1, 2], "y": [1.0, 2.0]})
    with pytest.raises(ValueError, match=r"time_grain='week' needs a time x"):
        ev.line_plot(df, "x", "y", time_grain="week")


def test_rolling_counts_calendar_periods_not_rows(make_frame: MakeFrame) -> None:
    # Jan 3 is missing: the 2-day window on Jan 4 holds Jan 3 and 4, so it is
    # 5 alone; counting rows would average Jan 2 and 4 to 4. No line point is
    # drawn where the series itself has none.
    df = make_frame({"day": ["2025-01-01", "2025-01-02", "2025-01-04"],
                     "v": [1.0, 3.0, 5.0]})  # fmt: skip
    fig = quiet_plot(df, "day", "v", rolling=2, missing_periods="gap")
    (trend,) = by_role(fig, "trendline")
    assert list(trend.y) == [1.0, 2.0, None, 5.0]
    assert trend.name == "v, 2-day mean"
    raw = line(fig)
    assert raw.opacity < 1 and raw.showlegend is False
    # The raw line is background: only the point after the gap keeps a marker.
    assert list(raw.marker.size) == [0, 0, 0, get_theme().marker_size]
    assert "markers" in trend.mode


# --- statistics -----------------------------------------------------------------------


def test_the_overall_line_with_agg_is_the_mean_of_all_rows(
    make_frame: MakeFrame,
) -> None:
    # On day 1, series a has three rows of 10 and series b one row of 100: the
    # mean of the four rows is 32.5, the mean of the two series means 55.
    df = make_frame(
        {
            "day": ["2025-01-01"] * 4 + ["2025-01-02"] * 2,
            "k": ["a", "a", "a", "b", "a", "b"],
            "v": [10.0, 10.0, 10.0, 100.0, 1.0, 3.0],
        }
    )
    fig = quiet_plot(df, "day", "v", color="k", agg="mean", overall_line=True)
    (overall,) = by_role(fig, "reference")
    assert overall.name == "Overall"
    assert list(overall.y) == [pytest.approx(32.5), pytest.approx(2.0)]
    # Pre-aggregated rows can only give the mean of the series, named so.
    means = pd.DataFrame({"day": ["2025-01-01"] * 2, "k": ["a", "b"],
                          "v": [10.0, 100.0]})  # fmt: skip
    fig = quiet_plot(means, "day", "v", color="k", overall_line=True)
    (overall,) = by_role(fig, "reference")
    assert (overall.name, list(overall.y)) == ("Mean of series", [55.0])


def test_the_band_is_the_stats_interval_of_each_points_rows(
    make_frame: MakeFrame,
) -> None:
    values = [3.0, 9.0, 4.0, 12.0, 7.0]
    df = make_frame({"m": ["2025-01-01"] * 5 + ["2025-02-01"], "v": [*values, 6.0]})
    fig = quiet_plot(df, "m", "v", agg="mean", ci="bootstrap", n_boot=500,
                     random_state=7)  # fmt: skip
    expected = interval(values, statistic="mean", method="bootstrap", level=0.95,
                        n_boot=500, random_state=7)  # fmt: skip
    upper, lower = by_role(fig, "ci")
    assert upper.y[0] == pytest.approx(expected.high)
    assert lower.y[0] == pytest.approx(expected.low)
    assert lower.fill == "tonexty"
    assert upper.y[1] is None  # one row: no interval, the band breaks


# --- drawing --------------------------------------------------------------------------


def test_highlight_dims_the_other_series_and_draws_them_underneath() -> None:
    theme = get_theme()
    fig = quiet_plot(pd.DataFrame(MONTHLY), "month", "orders", color="region",
                     missing_periods="gap", highlight="S")  # fmt: skip
    first, second = by_role(fig, "data")
    assert (first.name, first.line.color) == ("N", theme.dimmed)
    assert (second.name, second.line.color) == ("S", theme.colorway[0])
    assert second.line.width > first.line.width
    # Markers only on the highlighted line, and on the dimmed one's lone point.
    assert list(first.marker.size) == [0, 0, 0, theme.marker_size]
    assert "markers" in second.mode and second.marker.size == theme.marker_size
    with pytest.raises(ValueError, match=r"'W', which is not a series. Use one of 'N'"):
        ev.line_plot(pd.DataFrame(MONTHLY), "month", "orders", color="region",
                     highlight="W")  # fmt: skip


def test_dimmed_series_share_one_legend_entry() -> None:
    # 17 dimmed categories once listed 17 grey entries: the legend should name
    # what the chart is about, and the rest as one group that toggles together.
    df = pd.DataFrame({"x": [1, 2] * 4, "k": list("aabbccdd"), "y": [1.0] * 8})
    fig = quiet_plot(df, "x", "y", color="k", highlight="c")
    shown = [t.name for t in fig.data if t.showlegend is not False]
    assert shown == ["3 others", "c"]
    dimmed = [t for t in by_role(fig, "data") if t.meta["group"] != "c"]
    assert {t.legendgroup for t in dimmed} == {"dimmed"}
    assert [t.meta["group"] for t in dimmed] == ["a", "b", "d"]  # roles keep names
    # One dimmed series keeps its own entry: there is no group to name.
    pair = quiet_plot(df[df["k"] <= "b"], "x", "y", color="k", highlight="a")
    assert [t.name for t in pair.data if t.showlegend is not False] == ["b", "a"]


def test_value_labels_sit_away_from_their_line_and_from_other_lines() -> None:
    peaks = pd.DataFrame({"x": [1, 2, 3, 4], "y": [5.0, 1.0, 6.0, 9.0]})
    trace = line(quiet_plot(peaks, "x", "y", show_values=True))
    # A valley's label goes below, a point above its neighbours' mean above;
    # the ends lean inward, away from the axis line.
    assert trace.textposition == (
        "top right", "bottom center", "top center", "top left",
    )  # fmt: skip
    # Two lines ending 1 apart on a range of 100: both labels would sit above
    # their points and overlap, so the lower one moves below.
    close = pd.DataFrame({"x": [1, 2] * 2, "k": ["a", "a", "b", "b"],
                          "y": [0.0, 50.0, 100.0, 51.0]})  # fmt: skip
    fig = quiet_plot(close, "x", "y", color="k", show_values="last")
    assert line(fig, "b").textposition[1] == "top left"
    assert line(fig, "a").textposition[1] == "bottom left"


def test_log_axes_label_only_some_digits_of_each_power_of_ten() -> None:
    # Plotly labels every digit of a range spanning a few powers of ten,
    # crowding the axis; the tick spacing follows the range instead.
    def y_axis(top: float) -> go.layout.YAxis:
        df = pd.DataFrame({"x": [1, 2], "y": [10.0, top]})
        return quiet_plot(df, "x", "y", log_y=True).layout.yaxis

    assert y_axis(50.0).dtick is None  # within one power of ten: Plotly's own
    assert y_axis(5_000.0).dtick == "D2"
    assert y_axis(1e7).dtick == 1


def test_a_single_date_gets_a_day_either_side_and_one_tick() -> None:
    # Plotly's own range around one date is a millisecond either side, with
    # ticks in fractions of a second.
    df = pd.DataFrame({"day": ["2025-04-01"], "orders": [42.0]})
    axis = quiet_plot(df, "day", "orders").layout.xaxis
    assert list(axis.range) == [dt.datetime(2025, 3, 31), dt.datetime(2025, 4, 2)]
    assert axis.ticktext == ("2025-04-01",)


def test_a_one_period_rolling_mean_is_dropped_after_its_warning() -> None:
    df = pd.DataFrame({"x": [1, 2, 3], "y": [1.0, 2.0, 3.0]})
    with pytest.warns(EasyVizWarning, match="rolling=1 has no effect"):
        fig = ev.line_plot(df, "x", "y", rolling=1)
    assert by_role(fig, "trendline") == []
    assert "rolling" not in (fig.layout.title.subtitle.text or "")


def test_more_coloured_series_than_the_theme_has_raise_unless_highlighted() -> None:
    n = len(get_theme().colorway) + 1
    df = pd.DataFrame({"x": [1] * n, "k": [f"s{i}" for i in range(n)], "y": [1.0] * n})
    with pytest.raises(ValueError, match=rf"{n} series need {n} colours.*highlight"):
        ev.line_plot(df, "x", "y", color="k")
    quiet_plot(df, "x", "y", color="k", highlight="s3")  # dimmed need no colour


def test_markers_show_on_short_lines_and_on_points_between_gaps() -> None:
    short = pd.DataFrame({"x": range(30), "y": [1.0] * 30})
    assert "markers" in line(quiet_plot(short, "x", "y")).mode
    long = pd.DataFrame({"x": range(31), "y": [1.0] * 31})
    assert line(quiet_plot(long, "x", "y")).mode == "lines"
    # Weeks 1, 3 and 4 of 4: week 1 sits between the start and a gap, so a
    # line alone would never show it.
    weeks = pd.DataFrame({"w": ["2025-01-06", "2025-01-20", "2025-01-27"],
                          "y": [1.0, 2.0, 3.0]})  # fmt: skip
    trace = line(quiet_plot(weeks, "w", "y", show_markers=False,
                            missing_periods="gap"))  # fmt: skip
    assert trace.mode == "lines+markers"
    assert list(trace.marker.size) == [get_theme().marker_size, 0, 0, 0]


def test_extremes_are_labelled_max_above_and_min_below() -> None:
    df = pd.DataFrame({"x": [1, 2, 3, 4], "y": [5.0, 9.0, 2.0, 6.0]})
    trace = line(quiet_plot(df, "x", "y", show_values="extremes"))
    assert trace.text == ("", "9", "2", "")
    assert trace.textposition[1:3] == ("top center", "bottom center")
    ends = line(quiet_plot(df, "x", "y", show_values="ends"))
    assert ends.text == ("5", "", "", "6")


def test_events_are_placed_on_the_time_axis_and_must_lie_within_it() -> None:
    df = pd.DataFrame({"m": ["2025-01-01", "2025-02-01", "2025-03-01"],
                       "v": [1.0, 2.0, 3.0]})  # fmt: skip
    fig = quiet_plot(df, "m", "v", events={"2025-03-15": "Launch"})
    (event,) = [t for t in by_role(fig, "reference") if t.meta["group"] == "event"]
    assert list(event.x) == [dt.datetime(2025, 3, 15)] * 2  # within March
    assert event.yaxis == "y2" and event.text[1] == "Launch"
    assert fig.layout.xaxis.range[1] > dt.datetime(2025, 3, 15)  # still on the axis
    with pytest.raises(ValueError, match=r"events.*outside the x range"):
        ev.line_plot(df, "m", "v", events={"2025-04-01": "Too late"})
    with pytest.raises(ValueError, match=r"events has the key 3"):
        ev.line_plot(df, "m", "v", events={3: "Not a date"})


def test_log_y_refuses_values_of_zero_or_less_and_counts_them() -> None:
    df = pd.DataFrame({"x": [1, 2, 3], "y": [0.0, -1.0, 2.0]})
    with pytest.raises(ValueError, match="2 drawn values are 0 or less"):
        ev.line_plot(df, "x", "y", log_y=True)


def test_titles_and_hover_name_the_measure_and_escape_dollars() -> None:
    df = pd.DataFrame({"m": ["2025-01-01", "2025-02-01"], "$rev": [1.0, 2.0]})
    fig = quiet_plot(df, "m", "$rev", agg="sum", y_title="in $ and $")
    assert fig.layout.title.text == "<b>Total &#36;rev over m</b>"
    assert fig.layout.hovermode == "x unified"
    assert fig.layout.xaxis.unifiedhovertitle.text == "%{x|%b %Y}"
    assert "$" not in fig.layout.yaxis.title.text
    assert line(fig).hovertext[0].startswith("Total &#36;rev: <b>1</b>")


# --- conflicts and no-effect options --------------------------------------------------

FRAME = pd.DataFrame(
    {"m": ["2025-01-01", "2025-02-01"], "k": ["a", "b"], "v": [1.0, 2.0],
     "w": [3.0, 4.0]}
)  # fmt: skip

CONFLICTS = [
    ({"y": ["v", "w"], "color": "k"}, ["y=", "color="]),
    ({"color": "m"}, ["color='m'", "same column as x"]),
    ({"ci": "bootstrap"}, ["ci='bootstrap'", "agg"]),
    ({"agg": "median", "ci": "sem"}, ["ci='sem'", "agg='median'"]),
    ({"agg": "mean", "ci": "sem", "rolling": 3}, ["ci='sem'", "rolling=3"]),
    ({"fill_area": True, "log_y": True}, ["fill_area=True", "log_y=True"]),
    ({"missing_periods": "zero", "log_y": True},
     ["missing_periods='zero'", "log_y=True"]),
    ({"overall_line": True}, ["overall_line=True", "color"]),
    ({"overall_line": True, "y": ["v", "w"]}, ["overall_line=True", "y="]),
    ({"highlight": "a"}, ["highlight='a'", "several series"]),
    ({"color_map": {"a": "#000000"}}, ["color_map", "several series"]),
    ({"log_x": True}, ["log_x=True", "x='m' is a time column"]),
    ({"x": "k", "rangeslider": True}, ["rangeslider=True", "x='k' is a text column"]),
    ({"show_values": "first"}, ["show_values='first'", "not valid"]),
]  # fmt: skip


@pytest.mark.parametrize(("options", "named"), CONFLICTS)
def test_conflicting_options_raise_naming_both(
    options: dict[str, object], named: list[str]
) -> None:
    options = {"x": "m", "y": "v", **options}
    with pytest.raises(ValueError) as error:
        ev.line_plot(FRAME, **options)  # type: ignore[arg-type]
    text = str(error.value)
    assert text.startswith("line_plot: ")
    for part in named:
        assert part in text, (part, text)


@pytest.mark.parametrize(
    ("options", "param"),
    [
        ({"x": "w", "missing_periods": "zero"}, "missing_periods"),
        ({"time_grain": None, "missing_periods": "gap"}, "missing_periods"),
        ({"rolling": 1}, "rolling"),
        ({"ci_level": 0.9}, "ci_level"),
        ({"agg": "sum", "hover": "w"}, "hover"),
    ],
)
def test_options_without_effect_warn(options: dict[str, object], param: str) -> None:
    options = {"x": "m", "y": "v", **options}
    with pytest.warns(EasyVizWarning, match=rf"{param}=.* has no effect"):
        ev.line_plot(FRAME, **options)  # type: ignore[arg-type]


def test_the_default_call_warns_nothing() -> None:
    quiet_plot(FRAME, "m", "v")


def test_invalid_values_are_rejected() -> None:
    with pytest.raises(ValueError, match=re.escape("rolling=0 is not valid")):
        ev.line_plot(FRAME, "m", "v", rolling=0)
    with pytest.raises(ValueError, match=re.escape("time_grain='weekly'")):
        ev.line_plot(FRAME, "m", "v", time_grain="weekly")  # type: ignore[arg-type]
