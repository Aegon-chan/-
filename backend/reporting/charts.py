"""Chart generation module.

Produces Plotly interactive charts (timeseries, heatmap, scatter, profile)
for geological-hazard monitoring data. Returns HTML div strings suitable
for embedding in NiceGUI chat bubbles or Jinja2 report templates.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import plotly.graph_objects as go
import plotly.io as pio

COLOR_CYCLE = [
    "#4C72B0",
    "#DD8452",
    "#55A868",
    "#C44E52",
    "#8172B3",
    "#937860",
    "#DA8BC3",
    "#8C8C8C",
]


def timeseries(
    x,
    y,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    series_names: Optional[list[str]] = None,
    line_shape: str = "linear",
    show_markers: bool = False,
    fill: str = "none",
    width: int = 800,
    height: int = 420,
) -> str:
    """Generate an interactive time-series / line chart."""
    fig = go.Figure()
    fig.update_layout(
        title=title,
        xaxis_title=x_label,
        yaxis_title=y_label,
        template="plotly_white",
        font=dict(family="sans-serif", size=13),
        width=width,
        height=height,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    if isinstance(y, dict):
        items = list(y.items())
    else:
        items = list(enumerate(y))
        items = [(series_names[i] if series_names and i < len(series_names) else f"Series {i+1}", v) for i, v in items]
    for idx, (name, values) in enumerate(items):
        color = COLOR_CYCLE[idx % len(COLOR_CYCLE)]
        scatter_kw = dict(
            x=x,
            y=values,
            mode="lines+markers" if show_markers else "lines",
            name=str(name),
            line=dict(color=color, shape=line_shape, width=2),
            fill=fill,
        )
        if fill != "none":
            scatter_kw["fillcolor"] = f"rgba{_hex_to_rgba(color, 0.15)}"
        fig.add_trace(go.Scatter(**scatter_kw))
    return to_html(fig)


def heatmap(
    z,
    x=None,
    y=None,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    colorscale: str = "Viridis",
    width: int = 700,
    height: int = 500,
) -> str:
    """Generate an interactive heatmap (e.g. InSAR deformation field)."""
    fig = go.Figure()
    fig.add_trace(
        go.Heatmap(
            z=z,
            x=x,
            y=y,
            colorscale=colorscale,
            colorbar=dict(title=dict(text=y_label, side="right")),
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title=x_label,
        yaxis_title=y_label,
        template="plotly_white",
        font=dict(family="sans-serif", size=13),
        width=width,
        height=height,
    )
    fig.update_xaxes(nticks=10)
    fig.update_yaxes(nticks=10, autorange="reversed")
    return to_html(fig)


def scatter(
    x: list,
    y: list,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    show_trendline: bool = False,
    trendline_color: str = "#C44E52",
    width: int = 600,
    height: int = 420,
) -> str:
    """Generate a scatter plot with optional linear trend line."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="markers",
            name="Data",
            marker=dict(color=COLOR_CYCLE[0], size=6, opacity=0.7),
        )
    )
    if show_trendline and len(x) > 2:
        slope, intercept, r_val, *_ = _ols(x, y)
        trend_x = [min(x), max(x)]
        trend_y = [slope * v + intercept for v in trend_x]
        fig.add_trace(
            go.Scatter(
                x=trend_x,
                y=trend_y,
                mode="lines",
                name=f"Trend (R\u00b2={r_val * r_val:.3f})",
                line=dict(color=trendline_color, width=2, dash="dash"),
            )
        )
    fig.update_layout(
        title=title,
        xaxis_title=x_label,
        yaxis_title=y_label,
        template="plotly_white",
        font=dict(family="sans-serif", size=13),
        width=width,
        height=height,
        hovermode="closest",
    )
    return to_html(fig)


def profile(
    x: list,
    y: list,
    title: str = "",
    x_label: str = "Distance (m)",
    y_label: str = "Value",
    fill_area: bool = True,
    width: int = 800,
    height: int = 380,
) -> str:
    """Generate a profile / cross-section view."""
    fig = go.Figure()
    fill = "tozeroy" if fill_area else "none"
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines+markers",
            name="Profile",
            line=dict(color=COLOR_CYCLE[0], width=2),
            fill=fill,
            fillcolor=f"rgba{_hex_to_rgba(COLOR_CYCLE[0], 0.12)}",
            marker=dict(size=4),
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title=x_label,
        yaxis_title=y_label,
        template="plotly_white",
        font=dict(family="sans-serif", size=13),
        width=width,
        height=height,
        hovermode="x unified",
        showlegend=False,
    )
    return to_html(fig)


def to_html(fig: go.Figure) -> str:
    """Render a Plotly figure to an embeddable HTML div string."""
    return pio.to_html(
        fig,
        include_plotlyjs="cdn",
        full_html=False,
        div_id="",
        config={"responsive": True, "displayModeBar": True},
    )


def save_html(fig: go.Figure, path: Union[str, Path]) -> Path:
    """Save a Plotly figure as a standalone HTML file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pio.write_html(fig, str(path), include_plotlyjs="cdn", full_html=True)
    return path


def save_image(fig: go.Figure, path: Union[str, Path], scale: int = 2) -> Path:
    """Save a Plotly figure as a static image (PNG by default)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fig.write_image(str(path), scale=scale)
    except Exception:
        import logging
        logging.getLogger("research_agent.reporting").warning(
            "Static image export requires kaleido; saving HTML instead."
        )
        save_html(fig, path.with_suffix(".html"))
        return path.with_suffix(".html")
    return path


def _hex_to_rgba(hex_color: str, alpha: float) -> tuple:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return r, g, b, alpha


def _ols(x: list, y: list) -> tuple:
    from scipy import stats
    return stats.linregress(x, y)
