# Table handling (`_data`)

Covers: src/easy_viz/_data.py

## Responsibilities
Turn whatever table the user passed into a validated, normalised narwhals `DataFrame`
that a plot function can draw from. It is the only module that converts, checks or
normalises user tables
([decision 0004](../../decisions/0004-narwhals-dataframe-agnostic.md)), and it applies
the query-result shape rules of [the conventions](../../conventions.md#query-result-shapes):
- intake of any table narwhals accepts, eager or lazy
- column existence and dtype checks, with messages that name the parameter
- SQL type normalisation (rule 6)
- ISO-date strings as time (rule 5)
- dropping missing values with a warning (rule 7)
- the pre-aggregated check and aggregation with `agg` (rules 1, 2, 4)
- the exit to numpy for statistics

It replaces `_is_categorical_col` and the column checks that every function of the
legacy module repeated.

## How it works
A plot function calls, in order (each step is a plain function; `func` is the public
function name used in messages):

1. **`load(df, func, slots)`** takes a mapping of parameter name to what the user
   passed (`{"x": x, "y": y, "color": color, "hover": hover}`; a value is a column
   name, a list of names, or `None` for an unused slot).
   - `nw.from_native` wraps the table. Its `TypeError` for non-tables is re-raised
     with the conventions format, naming `df` and the type received.
   - Columns are checked against the schema *before* collecting, so a lazy frame
     fetches only the used columns. A missing column's message suggests the closest
     name (`difflib`) and lists up to `MAX_LISTED_COLUMNS` available columns.
   - The used columns are selected (slot order, no repeats), a lazy frame is
     collected, an empty table is rejected, and types are normalised:

     | narwhals reports | Becomes | Typical source |
     |---|---|---|
     | `Decimal` | `Float64` | SQL `numeric` in polars, pyarrow, pandas-Arrow |
     | `Date` | `Datetime` | SQL `DATE` |
     | `Object`, all values `Decimal` or real numbers | `Float64` | `pd.read_sql` of `numeric` |
     | `Object`, all values `datetime.date` / naive `datetime` | `Datetime` | drivers returning `DATE` into pandas |
     | anything else | unchanged | |

     Nullable and Arrow-backed pandas dtypes need no cast: narwhals already reports
     them as the standard dtypes (`Int64`, `Float64`, `String`, ...), `to_numpy()`
     returns plain numpy types for them, and their missing values are handled by
     `drop_nulls` and `to_float_array`.
2. **`require_numeric(frame, func, slots)`** raises `TypeError` naming the parameter,
   column and narwhals dtype. It runs after `load`, so decimals already count.
   `column_kind(frame, column)` classifies a column as `"numeric"`, `"temporal"`
   (`Date`/`Datetime`) or `"categorical"` (everything else: every backend's string
   types, `Categorical`, `Enum`, `Boolean`, leftover `Object`).
3. **`parse_time(frame, func, param, column)`** converts a `String` column whose
   distinct non-null values are *all* ISO dates (`YYYY-MM-DD`, optionally with
   ` HH:MM`, `:SS` and up to 6 fraction digits, space or `T` separated) and real
   calendar dates. Parsing runs in Python (`datetime.fromisoformat`) on the distinct
   values only, then `replace_strict` maps them back on the user's backend. If only
   some values parse, the column stays categorical and an `EasyVizWarning` says how
   many distinct values are not dates, with an example. If none parse, it stays
   categorical silently (it is just a text column).
4. **`drop_nulls(frame, func)`** drops rows with a missing value in any column of the
   frame (which holds only the used columns). Missing means null, or NaN in a float
   column. One warning gives rows dropped out of the total and the count per column;
   nothing dropped means no warning; everything dropped raises `ValueError`.
5. **`aggregate(frame, func, keys, values, agg)`** with `keys` mapping parameter to
   grouping column (`x`, `color`, facets) and `values` the `y` column(s):
   - First, in every mode: an invalid `agg` raises the standard `check_choice`
     message (so a plot that forgot to validate still fails clearly), repeated
     `values` are de-duplicated, and a `values` column that is also a key raises
     `ValueError`.
   - `agg=None`: raises `ValueError` if a key combination repeats, saying how many
     repeat, showing the first one and naming `agg`. Otherwise returns the frame
     unchanged.
   - `agg` set: one row per key combination with the `values` aggregated. `"count"`
     counts rows per `values` column, or into one column named `count` (suffixed with
     `_` if a key already has that name) when there is no `y`. Other columns (hover)
     are dropped, with an `EasyVizWarning` naming them: a group has no single value
     for them, and an option is never silently ignored. Any other `agg` without `y`
     raises `ValueError`.
   - Returns the frame and the list of value column names to draw.

`to_float_array(frame, column)` returns a numeric column as a `float64` numpy array
with missing values as NaN: the point where narwhals stops and `stats/` starts.

## Invariants
- The user's table is never modified: every step returns a new narwhals frame
  (`with_columns`, `filter`, `select` never write to the native object).
- Group order is first-appearance order on every backend: `aggregate` adds a
  temporary row index (`nw.generate_temporary_column_name`), keeps its minimum per
  group and sorts by it. The query's `ORDER BY` therefore controls the chart.
- `_data` never sorts rows by value, not even by time. A datetime axis is drawn
  chronologically by Plotly regardless of row order; a plot that *connects* points
  (lines, areas) sorts its rows by a temporal `x` itself, because only it knows
  whether order matters.
- Only used columns are ever checked for nulls or converted: an unrelated broken
  column in a wide query result never affects a chart.
- Every message goes through `_validate.message` and names the parameter and value.

## Pitfalls
- **Group order differs by backend.** polars' `group_by` returns groups in arbitrary
  order; pandas and pyarrow happen to keep appearance order. Never rely on the
  backend: keep the row-index sort.
- **narwhals' pyarrow `median` in `group_by` is approximate** (pyarrow's
  `approximate_median`, a t-digest): the median of 1 and 3 comes out as 1. Medians
  are therefore computed in numpy for every backend (`_group_medians`: group ids
  from `min(row index).over(keys)`, then one `lexsort` and the two middle values).
- **NaN versus null depends on the backend.** pandas turns a SQL NULL in a float
  column into NaN and counts NaN as null; polars and pyarrow keep NaN as a value and
  `drop_nulls()` keeps it. Counting `is_null() | is_nan()` on float columns gives the
  same result everywhere.
- **pandas `object` columns are opaque to narwhals.** Decimals and dates there are
  reported as `Object`, so their values are inspected; a column mixing text and
  numbers stays `Object` (categorical). Time-zone-aware datetimes in an `object`
  column also stay `Object`: pandas refuses to cast them to a naive dtype, and the
  values may carry different zones.
- **pyarrow parses `2026-02-30` as 2026-03-02** with `str.to_datetime`, and every
  backend wants a different format code for fractional seconds. That is why ISO
  strings are parsed in Python, where invalid dates fail.
- **A filtered pandas frame keeps its old index labels.** narwhals aligns by
  position, and a test with a gapped index guards the median path, where a numpy
  result is attached with `nw.new_series`.
- **ISO strings with a time-zone offset are not recognised** (they stay categorical
  with a warning): mixing offsets on one axis has no single correct reading.
- **pandas `Period` columns** are reported as `Unknown` and classed as categorical;
  they are not a SQL type, so no conversion exists.
