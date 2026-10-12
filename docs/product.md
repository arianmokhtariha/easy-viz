# Product

## Vision
**easy-viz is the Metabase / Power BI of Python, at the code level.**

In Metabase or Power BI you run a query, drop columns into a chart's slots, pick
options, and get a finished chart. easy-viz does the same in code:
- a query result goes straight into one function call
- the chart's slots and options are typed, documented parameters
- out comes a finished, interactive Plotly figure

Being code, it goes further than BI tools: full statistical options, reproducibility,
version control, and the complete power of Plotly on the returned figure.

## The problem
Plotting in Python starts simple and turns into a software-engineering side quest.
The first chart takes three lines. The chart an analysis actually needs takes:
- sorting, top-N with "Other"
- per-group colours and trendlines with statistics
- reference lines, confidence intervals, label formatting
- subplot layout and a consistent theme

That's 20–60 lines of custom code, repeated in every notebook. The notebook stops
being about the data. easy-viz removes the side quest: every one of those features is
a parameter.

## Who it's for
Data analysts and data scientists working in notebooks on tabular data: SQL query
results first, dataframes in general.

## Product principles
Every feature is judged against these.

1. **SQL result in, chart out.** Any shape a query naturally returns is plottable
   without a reshaping step (see "Query-result shapes").
2. **Flexible, never ambiguous.**
   - easy-viz accepts every reasonable data shape, but it never guesses silently
   - when the shape is ambiguous, it raises an error that names the parameter to set
   - explicit parameters always override inference
   - automatic behaviour (type detection, dropping nulls, folding categories into
     "Other") is documented and announced with a warning when it changes the data
3. **Simple by default, professional by option.**
   - the bare call returns a finished chart
   - every useful option of the plot concept is a typed, documented parameter
   - complexity comes from adding options, never from writing code
4. **The field-well model.** Every function uses the same slots as a BI tool, with
   the same names:

   | Slot | Power BI equivalent | Meaning |
   |---|---|---|
   | `x` | Axis | category or independent column |
   | `y` (+ `agg`) | Values | measure column(s), and how to aggregate them |
   | `color` | Legend | column that splits the data into series |
   | `facet_col`, `facet_row` | Small multiples | columns that split the data into panels |
   | `hover` | Tooltips | extra columns shown on hover |

5. **Analysis built in.** The statistics that answer the analytical question are
   options, not homework: trendlines with r² and p, confidence intervals, Pareto
   cutoffs, significance.
6. **Never a dead end.** Every function returns a plain Plotly figure, with traces
   tagged by role. Whatever the parameters don't cover is one Plotly call away.
7. **Consistency is a feature.** Same slot names, option names, defaults logic and
   error style everywhere. Learning one function teaches all of them.

## Query-result shapes
These are the shapes SQL queries return, and how each one plots. The exact parameter
rules are in [conventions](conventions.md#query-result-shapes).

| Query shape | Example | How easy-viz plots it |
|---|---|---|
| Pre-aggregated: one row per category | `GROUP BY region` | as-is (`agg=None`, the default) |
| Raw rows: many rows per category | `SELECT * FROM orders` | `agg="sum"` / `"mean"` / `"count"` / ... aggregates |
| Long: series stacked in a column | `GROUP BY month, region` | `color="region"` gives one series per region |
| Wide: several measure columns | `SELECT month, revenue, cost, profit` | `y=["revenue", "cost", "profit"]` gives one series per column |
| Time buckets | `date_trunc('week', ...)` | dates, timestamps and date strings normalised automatically |
| SQL types | `numeric`, `NULL`, nullable ints | decimals become floats; NULLs dropped with a warning |

## Non-goals
- **A BI application or dashboard server.** easy-viz figures plug into Dash,
  Streamlit or Vizro instead.
- **A data-cleaning or ETL library.** easy-viz normalises types; business logic stays
  in the query.
- **A rendering engine.** Plotly draws (decision 0001).
- **A drag-and-drop GUI.** The interface is the function signature.
