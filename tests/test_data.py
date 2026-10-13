import datetime as dt
import warnings
from decimal import Decimal

import narwhals as nw
import numpy as np
import pandas as pd
import polars as pl
import pyarrow as pa
import pytest
from conftest import MakeFrame

from easy_viz._data import (
    aggregate,
    column_kind,
    drop_nulls,
    load,
    parse_time,
    require_numeric,
    to_float_array,
)
from easy_viz._warnings import EasyVizWarning

SALES = {
    "region": ["North", "South", "North", "East", "South", "North"],
    "quarter": ["Q1", "Q1", "Q2", "Q1", "Q1", "Q1"],
    "revenue": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
}


# --- intake -----------------------------------------------------------------


def test_load_keeps_used_columns_in_slot_order(make_frame: MakeFrame) -> None:
    frame = load(
        make_frame(SALES),
        "bar_plot",
        {"x": "revenue", "y": ["region", "revenue"], "color": None},
    )
    assert frame.columns == ["revenue", "region"]


def test_load_collects_a_lazy_frame() -> None:
    lazy = pl.LazyFrame(SALES)
    frame = load(lazy, "bar_plot", {"x": "region"})
    assert isinstance(frame, nw.DataFrame)
    assert frame["region"].to_list() == SALES["region"]


@pytest.mark.parametrize(
    ("df", "shown"), [([1, 2], "list"), (pd.Series([1, 2]), "Series")]
)
def test_load_rejects_a_non_table(df: object, shown: str) -> None:
    with pytest.raises(TypeError, match=f"^bar_plot: df is a {shown}, not a table"):
        load(df, "bar_plot", {"x": "a"})  # type: ignore[arg-type]


def test_load_never_mutates_the_users_table() -> None:
    native = pd.DataFrame(
        {"amount": [Decimal("1.5"), None], "day": [dt.date(2026, 1, 1), None]},
        dtype=object,
    )
    before = native.copy()
    load(native, "bar_plot", {"x": "day", "y": "amount"})
    pd.testing.assert_frame_equal(native, before)
    assert native["amount"].dtype == object


def test_missing_column_suggests_a_close_match(make_frame: MakeFrame) -> None:
    with pytest.raises(ValueError) as error:
        load(make_frame(SALES), "bar_plot", {"x": "quarter", "color": "regoin"})
    assert str(error.value) == (
        "bar_plot: color='regoin' is not a column of df. Did you mean 'region'? "
        "Available columns: 'region', 'quarter', 'revenue'."
    )


def test_missing_column_in_a_list_slot_and_long_listing() -> None:
    wide = pd.DataFrame({f"col{i}": [1] for i in range(25)})
    with pytest.raises(ValueError) as error:
        load(wide, "line_plot", {"y": ["col1", "zzz"]})
    text = str(error.value)
    assert text.startswith(
        "line_plot: 'zzz' in y=['col1', 'zzz'] is not a column of df. "
        "Available columns: 'col0'"
    )
    assert "Did you mean" not in text
    assert text.endswith("'col19' and 5 more.")


def test_malformed_slots() -> None:
    native = pd.DataFrame(SALES)
    with pytest.raises(TypeError, match=r"^bar_plot: y=5 is not a column name\."):
        load(native, "bar_plot", {"y": 5})  # type: ignore[dict-item]
    with pytest.raises(ValueError, match=r"^bar_plot: y=\[\] names no columns\."):
        load(native, "bar_plot", {"y": []})


def test_load_rejects_an_empty_table(make_frame: MakeFrame) -> None:
    with pytest.raises(ValueError, match=r"^bar_plot: df has no rows"):
        load(make_frame({"a": []}), "bar_plot", {"x": "a"})


# --- SQL type normalisation ---------------------------------------------------


def test_pandas_object_decimals_and_dates_are_normalised() -> None:
    # What pd.read_sql returns for NUMERIC and DATE columns.
    native = pd.DataFrame(
        {
            "amount": [Decimal("1.25"), Decimal("2.5"), None],
            "day": [dt.date(2026, 1, 31), dt.date(2026, 2, 1), None],
            "mixed": ["a", Decimal("1"), None],
        },
        dtype=object,
    )
    frame = load(native, "f", {"x": "day", "y": "amount", "color": "mixed"})
    assert frame.schema["amount"] == nw.Float64
    assert frame.schema["day"] == nw.Datetime
    assert to_float_array(frame, "amount").tolist()[:2] == [1.25, 2.5]
    assert frame["day"].to_list()[0] == dt.datetime(2026, 1, 31)
    # A column that isn't all numbers or all dates is left alone.
    assert column_kind(frame, "mixed") == "categorical"


def test_pandas_object_aware_datetimes_are_left_alone() -> None:
    # Casting them would fail inside pandas (zones can differ per value).
    aware = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    native = pd.DataFrame({"t": pd.Series([aware, aware], dtype=object)})
    frame = load(native, "f", {"x": "t"})
    assert column_kind(frame, "t") == "categorical"


@pytest.mark.parametrize(
    "native",
    [
        pl.DataFrame(
            {"amount": [Decimal("1.25"), None], "day": [dt.date(2026, 1, 31), None]}
        ),
        pa.table(
            {
                "amount": pa.array([Decimal("1.25"), None], pa.decimal128(10, 2)),
                "day": pa.array([dt.date(2026, 1, 31), None], pa.date32()),
            }
        ),
        pd.DataFrame(
            {
                "amount": pd.Series(
                    [Decimal("1.25"), None], dtype=pd.ArrowDtype(pa.decimal128(10, 2))
                ),
                "day": pd.Series(
                    [dt.date(2026, 1, 31), None], dtype=pd.ArrowDtype(pa.date32())
                ),
            }
        ),
    ],
    ids=["polars", "pyarrow", "pandas-arrow"],
)
def test_native_decimal_and_date_types_are_normalised(native: object) -> None:
    frame = load(native, "f", {"x": "day", "y": "amount"})  # type: ignore[arg-type]
    assert frame.schema["amount"] == nw.Float64
    assert frame.schema["day"] == nw.Datetime
    assert to_float_array(frame, "amount")[0] == 1.25


def test_pandas_nullable_int_with_na() -> None:
    native = pd.DataFrame({"n": pd.array([1, None, 3], dtype="Int64")})
    frame = load(native, "f", {"y": "n"})
    require_numeric(frame, "f", {"y": "n"})
    np.testing.assert_array_equal(to_float_array(frame, "n"), [1.0, np.nan, 3.0])
    with pytest.warns(EasyVizWarning, match=r"dropped 1 of 3 rows .*1 in 'n'"):
        kept = drop_nulls(frame, "f")
    assert kept["n"].to_numpy().tolist() == [1, 3]


# --- classification and dtype checks --------------------------------------------


@pytest.mark.parametrize(
    ("native", "kind"),
    [
        (pd.DataFrame({"c": pd.Categorical(["a"])}), "categorical"),
        (pd.DataFrame({"c": pd.array(["a"], dtype="string[pyarrow]")}), "categorical"),
        (pd.DataFrame({"c": pd.Series(["a"], dtype=object)}), "categorical"),
        (pl.DataFrame({"c": ["a"]}, schema={"c": pl.Categorical}), "categorical"),
        (pl.DataFrame({"c": ["a"]}, schema={"c": pl.Enum(["a"])}), "categorical"),
        (pa.table({"c": pa.array(["a"]).dictionary_encode()}), "categorical"),
        (pl.DataFrame({"c": [True]}), "categorical"),
        (pa.table({"c": pa.array([dt.date(2026, 1, 1)])}), "temporal"),
        (pd.DataFrame({"c": pd.to_datetime(["2026-01-01"])}), "temporal"),
        (pa.table({"c": pa.array([1], pa.int8())}), "numeric"),
    ],
)
def test_column_kind(native: object, kind: str) -> None:
    frame = load(native, "f", {"x": "c"})  # type: ignore[arg-type]
    assert column_kind(frame, "c") == kind


def test_require_numeric_names_parameter_column_and_dtype(
    make_frame: MakeFrame,
) -> None:
    frame = load(make_frame(SALES), "bar_plot", {"x": "quarter", "y": "revenue"})
    require_numeric(frame, "bar_plot", {"y": "revenue"})
    with pytest.raises(TypeError) as error:
        require_numeric(frame, "bar_plot", {"y": ["revenue", "quarter"]})
    assert str(error.value) == (
        "bar_plot: 'quarter' in y=['revenue', 'quarter'] has dtype String, but y "
        "must be numeric. Pass a numeric column, or cast it in the query."
    )


# --- time columns -------------------------------------------------------------


def test_iso_date_strings_become_datetime(make_frame: MakeFrame) -> None:
    frame = load(
        make_frame({"t": ["2026-01-31", "2026-02-01 12:30", "2026-02-02T08:00:00.5"]}),
        "f",
        {"x": "t"},
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        frame = parse_time(frame, "f", "x", "t")
    assert column_kind(frame, "t") == "temporal"
    assert [pd.Timestamp(v) for v in frame["t"].to_list()] == [
        pd.Timestamp("2026-01-31"),
        pd.Timestamp("2026-02-01 12:30"),
        pd.Timestamp("2026-02-02 08:00:00.5"),
    ]


@pytest.mark.parametrize(
    ("values", "bad"),
    [
        # pyarrow's own parser would silently roll this over to 2026-03-02.
        (["2026-01-31", "2026-02-30"], "'2026-02-30'"),
        (["2026-01-31", "2026-01-31", "n/a"], "'n/a'"),
        # An offset is ISO, but outside the forms easy-viz recognises.
        (["2026-01-31", "2026-01-31T10:00+02:00"], "'2026-01-31T10:00+02:00'"),
    ],
)
def test_partial_iso_dates_stay_categorical_with_a_warning(
    make_frame: MakeFrame, values: list[object], bad: str
) -> None:
    frame = load(make_frame({"t": values}), "line_plot", {"x": "t"})
    with pytest.warns(EasyVizWarning) as record:
        out = parse_time(frame, "line_plot", "x", "t")
    assert str(record[0].message) == (
        f"line_plot: x='t' looks like dates, but 1 of its 2 distinct values are "
        f"not ISO dates (e.g. {bad}), so it is drawn as categories. Fix or filter "
        "those values in the query to get a time axis."
    )
    assert column_kind(out, "t") == "categorical"


def test_plain_strings_and_other_dtypes_pass_through_silently(
    make_frame: MakeFrame,
) -> None:
    frame = load(make_frame(SALES), "f", {"x": "region", "y": "revenue"})
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert parse_time(frame, "f", "x", "region") is frame
        assert parse_time(frame, "f", "x", "revenue") is frame
        assert parse_time(frame, "f", "x", None) is frame


# --- nulls --------------------------------------------------------------------


def test_null_and_nan_both_count_as_missing(make_frame: MakeFrame) -> None:
    # pandas turns None into NaN; polars and pyarrow keep NaN and null apart.
    native = make_frame(
        {"v": [1.0, float("nan"), None, 4.0, 5.0], "c": ["a", "b", "c", None, "e"]}
    )
    frame = load(native, "bar_plot", {"x": "c", "y": "v"})
    with pytest.warns(EasyVizWarning) as record:
        kept = drop_nulls(frame, "bar_plot")
    assert len(record) == 1
    assert str(record[0].message) == (
        "bar_plot: dropped 3 of 5 rows with missing values (1 in 'c', 2 in 'v'). "
        "Filter or fill NULLs in the query to avoid this."
    )
    assert kept["c"].to_list() == ["a", "e"]


def test_no_warning_when_nothing_is_dropped(make_frame: MakeFrame) -> None:
    frame = load(make_frame(SALES), "f", {"x": "region", "y": "revenue"})
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert drop_nulls(frame, "f") is frame


def test_unused_columns_never_cause_drops(make_frame: MakeFrame) -> None:
    frame = load(make_frame({"a": [1, 2], "unused": [None, None]}), "f", {"x": "a"})
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert len(drop_nulls(frame, "f")) == 2


def test_everything_dropped_raises(make_frame: MakeFrame) -> None:
    frame = load(
        make_frame({"a": [1.0, 2.0], "b": [None, None]}), "f", {"x": "a", "y": "b"}
    )
    with pytest.raises(
        ValueError, match=r"^f: all 2 rows have a missing value \(2 in 'b'\)"
    ):
        drop_nulls(frame, "f")


# --- aggregation --------------------------------------------------------------


@pytest.mark.parametrize("agg", ["sum", "mean", "median", "min", "max", "count"])
def test_aggregation_keeps_first_appearance_order(
    make_frame: MakeFrame, agg: str
) -> None:
    # polars' group_by returns groups in arbitrary order unless told otherwise.
    native = make_frame(
        {
            "k": ["z", "a", "z", "m", "a", "q", "b", "z"],
            "v": [1.0, 2.0, 3.0, 4.0, 10.0, 5.0, 6.0, 8.0],
        }
    )
    frame = load(native, "f", {"x": "k", "y": "v"})
    out, values = aggregate(frame, "f", {"x": "k"}, ["v"], agg)  # type: ignore[arg-type]
    assert out["k"].to_list() == ["z", "a", "m", "q", "b"]
    assert values == ["v"]
    expected = {
        "sum": [12.0, 12.0, 4.0, 5.0, 6.0],
        "mean": [4.0, 6.0, 4.0, 5.0, 6.0],
        # Exact medians: pyarrow's approximate median gives 1.0 and 2.0 here.
        "median": [3.0, 6.0, 4.0, 5.0, 6.0],
        "min": [1.0, 2.0, 4.0, 5.0, 6.0],
        "max": [8.0, 10.0, 4.0, 5.0, 6.0],
        "count": [3, 2, 1, 1, 1],
    }[agg]
    assert out["v"].to_list() == expected


def test_median_with_two_keys_and_wide_y(make_frame: MakeFrame) -> None:
    native = make_frame(
        {
            "x": ["b", "a", "b", "a", "b"],
            "c": ["p", "p", "p", "p", "q"],
            "y1": [1.0, 2.0, 3.0, 10.0, 7.0],
            "y2": [5.0, 1.0, 1.0, 1.0, 0.0],
        }
    )
    frame = load(native, "f", {"x": "x", "y": ["y1", "y2"], "color": "c"})
    out, _ = aggregate(frame, "f", {"x": "x", "color": "c"}, ["y1", "y2"], "median")
    assert out.columns == ["x", "c", "y1", "y2"]
    assert out.rows() == [
        ("b", "p", 2.0, 3.0),
        ("a", "p", 6.0, 1.0),
        ("b", "q", 7.0, 0.0),
    ]


def test_count_without_y(make_frame: MakeFrame) -> None:
    native = make_frame({"count": ["x", "y", "x"], "hover": [1, 2, 3]})
    frame = load(native, "f", {"x": "count", "hover": "hover"})
    out, values = aggregate(frame, "f", {"x": "count"}, [], "count")
    # The key is already called "count", so the result column gets a new name;
    # hover columns are dropped (a group has no single hover value).
    assert values == ["count_"]
    assert out.columns == ["count", "count_"]
    assert out["count_"].to_list() == [2, 1]


def test_agg_other_than_count_needs_y(make_frame: MakeFrame) -> None:
    frame = load(make_frame(SALES), "bar_plot", {"x": "region"})
    with pytest.raises(ValueError, match=r"^bar_plot: agg='sum' needs y\. Set y"):
        aggregate(frame, "bar_plot", {"x": "region"}, [], "sum")


def test_repeated_keys_without_agg_raise(make_frame: MakeFrame) -> None:
    frame = load(make_frame(SALES), "bar_plot", {"x": "region", "y": "revenue"})
    with pytest.raises(ValueError) as error:
        aggregate(frame, "bar_plot", {"x": "region", "color": None}, ["revenue"], None)
    assert str(error.value) == (
        "bar_plot: 2 values of x appear in more than one row (e.g. region='North'), "
        "but agg=None plots each row as-is. Set agg (e.g. agg='sum') to combine "
        "them, or return one row per x from the query."
    )
    frame = load(make_frame(SALES), "bar_plot", {"x": "region", "color": "quarter"})
    with pytest.raises(ValueError) as error:
        aggregate(frame, "bar_plot", {"x": "region", "color": "quarter"}, [], None)
    assert str(error.value).startswith(
        "bar_plot: 2 combinations of x and color appear in more than one row "
        "(e.g. region='North', quarter='Q1')"
    )
    frame = load(make_frame({"d": ["b", "a", "a"]}), "line_plot", {"x": "d"})
    with pytest.raises(ValueError, match=r"^line_plot: 1 value of x appears in more"):
        aggregate(frame, "line_plot", {"x": "d"}, [], None)


def test_unique_keys_without_agg_keep_rows_as_is(make_frame: MakeFrame) -> None:
    native = make_frame({"x": ["c", "a", "b"], "y": [1, 2, 3], "h": ["p", "q", "r"]})
    frame = load(native, "f", {"x": "x", "y": "y", "hover": "h"})
    out, values = aggregate(frame, "f", {"x": "x"}, ["y"], None)
    assert out is frame
    assert values == ["y"]


def test_to_float_array_turns_nulls_into_nan(make_frame: MakeFrame) -> None:
    frame = load(make_frame({"v": [1, None, 3]}), "f", {"y": "v"})
    result = to_float_array(frame, "v")
    assert result.dtype == np.float64
    np.testing.assert_array_equal(result, [1.0, np.nan, 3.0])


def test_filtered_pandas_frame_with_gaps_in_its_index() -> None:
    # A filtered DataFrame keeps its old row labels; results must follow
    # row positions, not labels.
    native = pd.DataFrame(
        {"k": ["z", "a", "z", "a"], "v": [1.0, 2.0, 3.0, 10.0]}, index=[50, 3, 9, 1]
    )
    frame = load(native, "f", {"x": "k", "y": "v"})
    out, _ = aggregate(frame, "f", {"x": "k"}, ["v"], "median")
    assert out.rows() == [("z", 2.0), ("a", 6.0)]
