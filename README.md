# easy-viz

[![CI](https://github.com/arianmokhtariha/easy-viz/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/arianmokhtariha/easy-viz/actions/workflows/ci.yml)

The Metabase / Power BI of Python, at the code level: a query result goes in, a
finished Plotly figure comes out.

Run your SQL (or anything else), pass the table straight to an easy-viz function, and
get a finished chart. Every feature of the chart is a typed, documented parameter, so a
plot goes from a one-line default to an advanced chart by changing arguments, not by
writing plotting code. Every function returns a plain Plotly figure, so anything the
parameters don't cover can still be done with Plotly.

> **Status:** pre-alpha, under active development. Not on PyPI yet.

The [gallery](https://github.com/arianmokhtariha/easy-viz/tree/main/gallery) shows
every function on a fictional retailer's data, starting from a SQL query each time.

## Development
```
uv sync --all-extras --all-groups
uv run pytest
```
What easy-viz is for: [`docs/product.md`](https://github.com/arianmokhtariha/easy-viz/blob/main/docs/product.md).
How it's organised, and why: [`docs/`](https://github.com/arianmokhtariha/easy-viz/tree/main/docs).
<!-- Links are absolute because this file is also the PyPI project page, where
relative links break. -->

