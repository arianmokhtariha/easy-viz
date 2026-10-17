# Time-series plots

Covers: src/easy_viz/plots/timeseries.py

## Responsibilities
`line_plot`: how a measure moves along an ordered axis, usually time, from any
query-result shape. It merges the legacy `line_plot` (draws rows as given) and
`time_series_plot` (buckets raw rows into a calendar)
([decision 0012](../../../decisions/0012-one-line-plot-continuous-time.md)). The
public API is its docstring, not restated here.

The product rule that shapes it: **a time axis is always continuous.** A SQL
`GROUP BY` returns no row for an empty period, and a line that silently bridges it
is the most common way a line chart misleads. Every calendar period between the first
and the last is therefore on the axis, and an empty one is drawn as the user chose
(`missing_periods`), or as a gap with a warning.

## How it works
The same staged pipeline as [`bar_plot`](comparison.md), with `_Options` (frozen)
carrying every option between the stages. Checks and drawing that both functions need
come from [`_shared`](_shared.md).

1. **`_check_options`**: everything that needs no data. Choices, the query-shape
   rules (`_shared.check_shape`), the interval options
   (`_shared.check_interval_options`), then one helper per group: `_check_drawing`
   (booleans, `show_markers`, `show_values`, `value_format`, `fill_area`/`log_y` and
   `missing_periods="zero"`/`log_y`), `_check_colour` (`highlight` needs several
   series, `color_map`), `_check_lines_options` (`overall_line` needs `color` and
   refuses a list `y`, `target` (above 0 with `log_y`), the shape of `events`).
2. **`_data` intake**: `load` (hover not loaded with `agg`, as in `bar_plot`),
   `require_numeric`, `parse_time`, then `column_kind` gives the x kind.
   `_check_x_kind` checks what depends on it: `log_x` needs numbers, `rangeslider` a
   time or numeric x, an explicit `time_grain` a time x; `missing_periods` without a
   calendar warns that it has no effect. Then `drop_nulls`.
3. **The calendar.** For a time x with `time_grain` not `None`: the grain is the given
   one, or `_data.infer_grain` for `"auto"` (it raises naming `time_grain` when the
   dates sit on no grid). With `"auto"` and a single distinct date there is no
   calendar at all, as with `None`: one date shows no step, and `infer_grain` would
   answer its coarsest grain ("yearly" for one month start), a claim the data can't
   back. `_check_daylight_saving` then refuses a time-zone-aware x placed finer than a
   day (an hourly grain, or no grain with times other than midnight) whose values lie
   on both sides of a daylight-saving change (`_data.utc_offset_changes`; see
   Pitfalls). `_data.truncate_time` always runs when there is a grain: idempotent on
   dates already on the grain, it buckets raw timestamps.
4. **`_shape`** builds `_Lines`: a series × position grid of values (NaN = no point)
   on one x axis shared by every series.
   - `_data.aggregate` gives one value per (x, series), or raises naming `agg` when an
     x repeats with `agg=None` (also after bucketing).
   - `_axis` gives the positions: on a calendar, `_data.period_grid` from the overall
     first to last period; a time x without one, and numbers, the sorted distinct
     values; text, the first-appearance order. A dict from each Python x value (as
     `to_dict` returns it) to its position places every other table built from the
     same frame: counts, interval groups, the overall line.
   - `observed` remembers which cells had a row. `_empty_periods` counts the periods
     missing *inside* some series' own first-to-last span: before a series starts or
     after it ends nothing is drawn, so nothing can be misread. With
     `missing_periods="zero"` the empty cells become 0 (over the whole grid: no
     orders is zero orders, also before a series' first sale).
   - `n` (rows per point, whenever `agg` is set) and the interval bounds (`ci`), from
     `_data.group_arrays` and `stats.intervals.interval`, exactly as `bar_plot`.
   - **The overall line** (`_overall`): with `agg`, the same `agg` over every row
     at each x, ignoring `color` (a true total, mean, median or count); with
     `agg=None`, the `nanmean` of the series' drawn values at each x, named
     "Mean of series" so it is never read as the overall value. Same fill and
     rolling as the series.
   - **Rolling** (`_roll`): `stats.smoothing.rolling_mean` over the full grid, so the
     window counts periods (7 on daily data is 7 days, also across an empty day),
     then masked to NaN wherever the line itself has no value. Without a calendar the
     window counts the series' own points. With `"zero"`, the zeros count.
5. **`_check_lines`**: `highlight` names a series, colours (`_shared.check_series_colours`:
   only the series drawn in colour count, so dimmed ones need none), and with `log_y`
   every drawn value above 0, then every lower band end above 0 (each counted in the
   message). A band is refused, never clipped: a clipped band would misstate the
   interval.
6. The **empty-period warning** (only when `missing_periods` was left at `None`), and
   **`_event_positions`**: each `events` key read as the x kind (ISO strings and
   dates as naive datetimes, numbers, or a category's text) and checked against the
   drawn range; on a calendar a moment inside the last period still counts
   (`_data.floor_time`).
7. **`_draw`**, per series, dimmed series first so the highlighted ones lie on top
   (`legendrank` keeps the legend in series order): the band (two `ci` traces), the
   data line, then the rolling line. Then the overall line, the reference lines and
   the axes; `apply_base_layout` and `auto_height` finish it.
   - **Value labels** are placed for all lines at once first (`_place_labels`):
     `_label_points` picks the labelled points and a side for each, away from the
     label's own line (above a point at or above the mean of its neighbours, below
     otherwise; `"extremes"` puts the max above and the min below). Then, position by
     position, higher points first, a label whose side holds another line's point or
     an already placed label within `_LABEL_ROOM` of the value range (in powers of
     ten on a log axis) moves to the other side, if that side is clear. `_lean` makes
     labels at the first and last position of a time or numeric axis lean inward
     (`"top right"`, `"bottom left"`, ...): the axis ends at those points.
   - **Two or more dimmed series share one legend entry**, `"N others"`, shown on
     the first one drawn: they share the legend group `"dimmed"`, so one click shows
     or hides them all, while each keeps its series name as role group. One dimmed
     series keeps its own entry.
   - `rolling=1` is warned as having no effect and then dropped from the options, so
     neither a second line nor the subtitle claims a rolling mean.

**Plotly choices**
- *Native*: `Scatter` lines with `line.shape`, `connectgaps`, `fill="tozeroy"` for
  `fill_area`, text on points for `show_values` (`cliponaxis=False`), the date axis
  with Plotly's own zoom-aware ticks, `rangeslider`, `hovermode="x unified"`.
- *Unified hover title*: on a calendar, `xaxis.unifiedhovertitle.text` names the
  period (`"%{x|%b %Y}"`, `"Week of %{x|%Y-%m-%d}"`, `"%{x|Q%q %Y}"`; `_PERIOD_HOVER`),
  since a point sits at its period's start and a bare date would misname a month or a
  week.
- *Hover text*: built in Python (`_hovers`), so `value_format` is a Python spec; each
  data point lists its value, `n`, the interval and the hover columns. A zero drawn
  for an empty period says "(no rows)".
- *Confidence band* (custom): an upper-bound trace, then the lower bound with
  `fill="tonexty"` (fills up to the previous trace), both `hoverinfo="skip"`, in the
  series colour at `_BAND_ALPHA` (`theme._color.with_alpha`). Plotly's `error_y`
  whiskers read as noise on a line.
- *Reference lines* (`avg_line`, `target`, `events`): `_shared.add_reference_lines`,
  the overlay-axis traces `bar_plot` uses: horizontal lines for values, vertical
  lines (label above the plot) for events.
- *Log axes* (`_log_ticks`): Plotly's own tick choice labels every digit of each
  power of ten (`dtick="D1"`) on a range of up to about three of them, which crowds
  the axis. From one power of ten to `_LOG_DIGIT_DECADES` the axis gets
  `dtick="D2"` (1, 2 and 5 labelled), beyond that `dtick=1` (powers of ten only);
  under one power of ten Plotly's own ticks stay.
- *A single date*: Plotly's autorange around one date is a millisecond either side,
  ticked in fractions of a second. The axis gets `_SINGLE_DATE_PAD` (a day) either
  side and one tick naming the date.

## Invariants
- A time axis with a grain has every period from the first to the last; an empty one
  is a gap, a zero or a bridge, never silently skipped (`missing_periods=None` warns).
- All series share one x axis. On a calendar a NaN is an empty period; without one it
  only means "this series has no point here", and lines bridge it (`connectgaps`), so
  series measured at different x values are still drawn.
- `show_markers=None` shows markers when no series has more than `MARKER_LIMIT` (30)
  points. Without markers, a point with no neighbour on either side still gets one
  (a per-point `marker.size`), so no value is invisible.
- Dimmed series, and the raw line under a rolling mean, are background: no markers
  (except lone points), no labels, drawn first.
- Labels (`show_values`) and `fill_area` go on the line the reader follows: the
  rolling line when `rolling` is set.
- Every trace has a role; every message names its option(s) in the conventions
  format; no styling literals (ratios such as `_FADED`, `_EMPHASIS` are named module
  constants with their reason).

## Pitfalls
- **Python x values are the join key** between the aggregated table, the raw frame's
  interval groups and the overall table. They all come from `to_dict` on the same
  backend, so they hash alike; never mix them with values converted another way.
- **`connectgaps` is the only switch between a gap and a bridge**, and it applies to
  the whole trace. That is why a calendar fills the grid with NaN (gaps) while a
  non-calendar axis bridges every NaN: there, NaN means "not measured here", not
  "empty period".
- **The range slider repeats every trace**, value labels included; Plotly has no
  option to leave text out of it.
- **Label placement only compares labels at the same x.** Plotly has no collision
  check for text, and the pixel size of the plot is unknown when traces are built,
  so `_LABEL_ROOM` estimates a label's height as a share of the value range. Three
  or more lines within one label height at the same x can't all be separated with
  two sides, and another line's *segment* (not its point) can still cross a label,
  e.g. a line rising steeply into the last x next to another line's `"last"` label.
  Labels can't move sideways or off their point (no offsets on trace text), and
  using annotations instead would take them out of the trace roles.
- **Event labels sit above the plot area**, at the top of the overlay axis; events
  closer together than their labels' width overlap.
- **Reference lines are drawn over the data.** They live on overlay axes, which
  Plotly draws above the main axes whatever the trace order, so an event line
  crosses a spike at that date, and an average or target label at the right end can
  sit on a line that ends near its value. A layout shape could go below the data
  (`layer="below"`) but carries no role.
- **The legend group of a dimmed series is `"dimmed"`, not its name.** Code that
  finds a series' traces should use the role group (`meta["group"]`), which is
  always the series name.
- **Hours of a time-zone-aware x are wall-clock hours.** Positions come from the
  local time (`_data.time_array`), so across a daylight-saving change two autumn rows
  at 02:00 share one position (one value silently lost, or summed into one point by
  an hourly grain) and the skipped spring hour would show as an empty period. That is
  why such data raises unless the positions are a day or coarser, where local
  calendar days are right; the fix is UTC (or a fixed offset) in the query.
- **`color_map` is read before the colorway.** With `color_map` covering every
  coloured series, there may be more of them than the theme has colours
  (`check_series_colours` allows it), so the colorway is indexed only for a series
  the map doesn't cover (`_series_colour`; `bar_plot`'s `_marker` does the same).
- **Plotly pads the x autorange by 5 % for any scatter trace with markers or text**
  (plotly.js `scatter` calc: `padded` unless the trace is lines only or filled to
  y), so a monthly chart over two years would run past a "Jan 2026" tick with an
  empty strip. `_x_range` sets the time and numeric x range to the first and last
  position (and any event) plus `_X_MARGIN` of the span; the range slider gets the
  same range, or its window would start inset. Text axes keep Plotly's category
  range.
- **`unifiedhovertitle` and the `%q` quarter directive** exist in plotly.js of Plotly
  7.1, the lowest supported version.
