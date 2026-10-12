# 0003: Every plot returns a plain `go.Figure`

**Status:** accepted · **Date:** 2026-10-11

## Context
Parameters can't cover every need. Users must be able to finish a chart at full
Plotly power, and the output must work wherever Plotly figures work.

## Decision
Every public plotting function returns a plain `plotly.graph_objects.Figure`. To make
later edits targeted, every trace carries `meta={"role": ..., "group": ...}` (roles are
listed in `docs/conventions.md`).

## Alternatives
- **A wrapper class around the figure:** users would have to learn another object, and
  Dash, Streamlit and `write_image` checks could fail on it.
- **A `go.Figure` subclass carrying extra state** (e.g. computed statistics): breaks
  when Plotly copies or rebuilds the figure. Reconsider only if returning statistics
  becomes a product need.

## Consequences
- **Easier:** no new object to learn; works everywhere Plotly works.
- **Harder:** the figure carries no easy-viz state beyond trace roles. Anything users
  need afterwards must be inside the figure or recomputable from `stats/`.
