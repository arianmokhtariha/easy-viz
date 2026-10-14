"""Render one sample sheet per built-in theme to ``.review/theme/<name>.png``.

Every theme role appears on the sheet, so a single look shows whether a theme
works: title and subtitle (with ``$`` signs), the colorway, legend, reference
lines, the "Other" and dimmed colours, both label-carrying heatmap scales, the
marker colour bar, the severity ramp, positive/negative, overlay boxes and a polar
panel. Plot functions don't exist yet, so the sheet is built from raw Plotly plus
the shared layout helpers, the same ones every plot uses.

Run with ``uv run python scripts/render_theme_samples.py``.
"""

import math
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio
from plotly.colors import sample_colorscale
from plotly.subplots import make_subplots

from easy_viz._layout import apply_base_layout, grid_geometry
from easy_viz.theme._color import with_alpha
from easy_viz.theme.registry import BUILTIN_THEMES
from easy_viz.theme.theme import Theme

OUT_DIR = Path(__file__).resolve().parents[1] / ".review" / "theme"
N_COLS = 3
PANELS = (
    "Colorway, 'Other' and a reference line",
    "Series with a legend",
    "Highlight: one series, the rest dimmed",
    "Diverging scale with cell labels",
    "Sequential scale with cell labels",
    "Marker diverging scale",
    "Severity ramp",
    "Positive and negative",
    "Polar grid with translucent fills",
)
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct")


def _wave(n: int, phase: float, level: float) -> list[float]:
    """Return ``n`` smooth, deterministic sample values (no randomness)."""
    return [level + 8 * math.sin(i / 1.6 + phase) + i for i in range(n)]


def _add_bars(fig: go.Figure, theme: Theme) -> None:
    """Panel 1: every colorway colour, the 'Other' bucket and a mean line."""
    names = [f"S{i + 1}" for i in range(len(theme.colorway))] + ["Other"]
    values = [40 - 2.5 * i for i in range(len(theme.colorway))] + [30.0]
    fig.add_trace(
        go.Bar(
            x=names,
            y=values,
            marker={
                "color": [*theme.colorway, theme.other],
                "line": {"color": theme.mark_outline, "width": 1},
            },
            showlegend=False,
        ),
        row=1,
        col=1,
    )
    mean = sum(values) / len(values)
    fig.add_hline(y=mean, line={"dash": "dash", "width": 2}, row=1, col=1)
    fig.add_annotation(
        x=names[-2],
        y=mean,
        text=f"mean {mean:.1f}",
        yshift=14,
        showarrow=False,
        font={"color": theme.reference, "size": theme.label_font_size},
        bgcolor=theme.overlay_background,
        bordercolor=theme.reference,
        borderwidth=1,
        row=1,
        col=1,
    )


def _add_series(fig: go.Figure, theme: Theme) -> None:
    """Panel 2: four series with a legend, a neutral 'overall' line, a median."""
    series = [
        _wave(len(MONTHS), phase, 20 + 6 * k) for k, phase in enumerate((0, 1, 2, 3))
    ]
    for k, values in enumerate(series):
        fig.add_trace(
            go.Scatter(
                x=MONTHS,
                y=values,
                name=f"Region {k + 1}",
                mode="lines+markers",
                line={"color": theme.colorway[k], "width": 2},
                marker={"size": 6, "line": {"color": theme.mark_outline, "width": 1}},
            ),
            row=1,
            col=2,
        )
    overall = [sum(v) / len(v) for v in zip(*series, strict=True)]
    fig.add_trace(
        go.Scatter(
            x=MONTHS,
            y=overall,
            name="Overall",
            mode="lines",
            line={"color": theme.neutral, "width": 3, "dash": "longdash"},
        ),
        row=1,
        col=2,
    )
    median = sorted(overall)[len(overall) // 2]
    fig.add_hline(
        y=median,
        line={"color": theme.reference_secondary, "dash": "dot", "width": 2},
        row=1,
        col=2,
    )


def _add_highlight(fig: go.Figure, theme: Theme) -> None:
    """Panel 3: one emphasised series against dimmed ones."""
    for k in range(5):
        fig.add_trace(
            go.Scatter(
                x=MONTHS,
                y=_wave(len(MONTHS), k * 0.9, 18 + 5 * k),
                mode="lines",
                line={
                    "color": theme.colorway[0] if k == 2 else theme.dimmed,
                    "width": 3 if k == 2 else 2,
                },
                showlegend=False,
            ),
            row=1,
            col=3,
        )


def _add_heatmaps(fig: go.Figure, theme: Theme) -> None:
    """Panels 4-5: label-carrying heatmaps on the diverging and sequential scales."""
    labels = ["price", "units", "margin", "returns", "visits", "rating"]
    n = len(labels)
    # Values cover the whole -1..1 range, so every stop of the scale is drawn.
    corr = [
        [1.0 if i == j else round(1 - 2 * ((i * n + j) % 11) / 10, 2) for j in range(n)]
        for i in range(n)
    ]
    fig.add_trace(
        go.Heatmap(
            z=corr,
            x=labels,
            y=labels,
            zmin=-1,
            zmax=1,
            colorscale=[list(stop) for stop in theme.diverging_scale],
            text=[[f"{v:.2f}" for v in row] for row in corr],
            texttemplate="%{text}",
            textfont={"size": theme.label_font_size},
            showscale=False,
        ),
        row=2,
        col=1,
    )
    classes = ["low", "mid", "high", "top"]
    counts = [[50, 12, 3, 0], [9, 41, 14, 2], [2, 11, 38, 7], [0, 3, 9, 27]]
    fig.add_trace(
        go.Heatmap(
            z=counts,
            x=classes,
            y=classes,
            colorscale=[list(stop) for stop in theme.sequential_scale],
            texttemplate="%{z}",
            textfont={"size": theme.label_font_size},
            showscale=False,
        ),
        row=2,
        col=2,
    )
    fig.update_yaxes(autorange="reversed", row=2, col=1)
    fig.update_yaxes(autorange="reversed", row=2, col=2)


def _add_markers(fig: go.Figure, theme: Theme) -> None:
    """Panel 6: markers on the diverging marker scale, with its colour bar."""
    xs = [i / 4 for i in range(40)]
    ys = [math.sin(x) * 10 + x for x in xs]
    change = [math.cos(x * 1.3) for x in xs]
    xaxis = fig.layout.xaxis6.domain
    yaxis = fig.layout.yaxis6.domain
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="markers",
            marker={
                "size": 11,
                "color": change,
                "cmin": -1,
                "cmax": 1,
                "colorscale": [list(stop) for stop in theme.marker_diverging_scale],
                "line": {"color": theme.mark_outline, "width": 1},
                "colorbar": {
                    "x": xaxis[1] + 0.01,
                    "xanchor": "left",
                    "y": (yaxis[0] + yaxis[1]) / 2,
                    "len": yaxis[1] - yaxis[0],
                    "thickness": 12,
                },
            },
            showlegend=False,
        ),
        row=2,
        col=3,
    )


def _add_severity(fig: go.Figure, theme: Theme) -> None:
    """Panel 7: share of missing values, coloured along the severity ramp."""
    columns = ["income", "age", "region", "email", "phone", "score"]
    shares = [0.92, 0.61, 0.38, 0.17, 0.05, 0.0]
    colors = sample_colorscale([list(s) for s in theme.severity_scale], shares)
    fig.add_trace(
        go.Bar(
            x=[s * 100 for s in shares],
            y=columns,
            orientation="h",
            marker={"color": colors, "line": {"color": theme.mark_outline, "width": 1}},
            text=[f"{s:.0%}" for s in shares],
            textposition="outside",
            textfont={"size": theme.label_font_size},
            cliponaxis=False,
            showlegend=False,
        ),
        row=3,
        col=1,
    )
    fig.update_yaxes(autorange="reversed", row=3, col=1)
    fig.update_xaxes(title_text="% missing", range=[0, 110], row=3, col=1)


def _add_change(fig: go.Figure, theme: Theme) -> None:
    """Panel 8: month-on-month change; overlay call-outs for the extremes."""
    change = [4.0, -2.5, 6.1, 1.2, -5.3, 3.3, -1.1, 7.4, -3.8, 2.0]
    fig.add_trace(
        go.Bar(
            x=MONTHS,
            y=change,
            marker={
                "color": [theme.positive if c >= 0 else theme.negative for c in change],
                "line": {"color": theme.mark_outline, "width": 1},
            },
            showlegend=False,
        ),
        row=3,
        col=2,
    )
    for value, color in ((max(change), theme.positive), (min(change), theme.negative)):
        fig.add_annotation(
            x=MONTHS[change.index(value)],
            y=value,
            text=f"{value:+.1f}%",
            yshift=16 if value > 0 else -16,
            showarrow=False,
            font={"color": color, "size": theme.label_font_size},
            bgcolor=theme.overlay_background,
            bordercolor=color,
            borderwidth=1,
            row=3,
            col=2,
        )
    fig.update_yaxes(title_text="change ($ k)", row=3, col=2)


def _add_polar(fig: go.Figure, theme: Theme) -> None:
    """Panel 9: radar profiles with translucent fills."""
    axes = ["speed", "cost", "quality", "reach", "trust", "speed"]
    for k, values in enumerate(([4, 3, 5, 2, 4, 4], [2, 5, 3, 4, 3, 2])):
        color = theme.colorway[k]
        fig.add_trace(
            go.Scatterpolar(
                r=values,
                theta=axes,
                fill="toself",
                fillcolor=with_alpha(color, 0.25),
                line={"color": color},
                showlegend=False,
            ),
            row=3,
            col=3,
        )
    # A polar chart's angle labels stick out of its domain; shrink the domain so
    # the top label clears the panel title above it.
    low, high = fig.layout.polar.domain.y
    fig.update_polars(domain_y=[low, high - 0.03])


def build_sheet(name: str, theme: Theme) -> go.Figure:
    """Return the sample sheet figure for one theme."""
    geometry = grid_geometry(
        len(PANELS), N_COLS, width=None, height=None, theme=theme, caller="samples"
    )
    specs = [[{"type": "xy"}] * geometry.n_cols for _ in range(geometry.n_rows)]
    specs[2][2] = {"type": "polar"}
    fig = make_subplots(
        rows=geometry.n_rows,
        cols=geometry.n_cols,
        specs=specs,
        subplot_titles=PANELS,
        horizontal_spacing=geometry.h_spacing,
        vertical_spacing=geometry.v_spacing,
    )
    for add in (
        _add_bars,
        _add_series,
        _add_highlight,
        _add_heatmaps,
        _add_markers,
        _add_severity,
        _add_change,
        _add_polar,
    ):
        add(fig, theme)
    fig.update_yaxes(title_text="revenue ($ k)", row=1, col=1)
    fig.update_xaxes(title_text="month", row=3, col=2)
    apply_base_layout(
        fig,
        title="Revenue grew from $1.2M to $3.4M",
        subtitle=f"easy-viz theme sample sheet: {name} · every theme role, costs in $",
        width=None,
        height=geometry.height,
        theme=theme,
    )
    return fig


def main() -> None:
    """Write one PNG per built-in theme, in a single batched export."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    figures = [build_sheet(name, theme) for name, theme in BUILTIN_THEMES.items()]
    paths = [OUT_DIR / f"{name}.png" for name in BUILTIN_THEMES]
    # write_images ignores the figures' own layout size (Plotly 7.1; to_image
    # honours it), so the sizes are passed explicitly.
    pio.write_images(
        figures,
        paths,
        width=[fig.layout.width for fig in figures],
        height=[fig.layout.height for fig in figures],
    )
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
