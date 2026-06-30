
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?# Matplotlib publication-grade static charts
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
from matplotlib.ticker import AutoMinorLocator, MaxNLocator
from pathlib import Path
import logging
import matplotlib.ticker as mticker
from backend.reporting.charts import _ols
import numpy as np

# Publication style
_PUB_FONTSIZE = 11
_PUB_LABELSIZE = 12
_PUB_TITLESIZE = 13
_PUB_LEGENDSIZE = 10
_PUB_TICK_SIZE = 9
_PUB_DPI = 200
_PUB_FIGSIZE = (7.0, 4.2)

_PUB_COLORS = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52",
    "#8172B3", "#937860", "#DA8BC3", "#8C8C8C",
]


def _apply_pub_style(ax, title="", xlabel="", ylabel=""):
    """Apply publication-grade styling to an axis."""
    ax.set_title(title, fontsize=_PUB_TITLESIZE, fontweight="bold", pad=10)
    ax.set_xlabel(xlabel, fontsize=_PUB_LABELSIZE)
    ax.set_ylabel(ylabel, fontsize=_PUB_LABELSIZE)
    ax.tick_params(axis="both", which="major", labelsize=_PUB_TICK_SIZE)
    ax.tick_params(axis="both", which="minor", labelsize=_PUB_TICK_SIZE - 1)
    ax.xaxis.set_minor_locator(AutoMinorLocator())
    ax.yaxis.set_minor_locator(AutoMinorLocator())
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.5)


def mpl_timeseries(
    x, y,
    title: str = "", x_label: str = "", y_label: str = "",
    series_names: list[str] = None,
    line_shape: str = "linear",
    show_markers: bool = False,
    fill: str = "none",
    figsize: tuple = _PUB_FIGSIZE,
    dpi: int = _PUB_DPI,
    config: dict = None,
) -> plt.Figure:
    """Publication-grade time series plot using matplotlib.

    Parameters
    ----------
    config : dict, optional
        Chart configuration overrides (color, range, annotations).
        Keys: colors (list), x_range (tuple), y_range (tuple),
              annotations (list of dict with x, y, text).
    """
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    cfg = config or {}

    colors = cfg.get("colors", _PUB_COLORS)
    x_range = cfg.get("x_range")
    y_range = cfg.get("y_range")
    annotations = cfg.get("annotations", [])

    if isinstance(y, dict):
        items = list(y.items())
    else:
        items = list(enumerate(y))
        items = [
            (
                series_names[i] if series_names and i < len(series_names)
                else f"Series {i+1}", v
            )
            for i, v in items
        ]

    for idx, (name, values) in enumerate(items):
        color = colors[idx % len(colors)]
        marker = "o" if show_markers else ""
        ax.plot(
            x, values,
            label=str(name),
            color=color,
            linestyle="-",
            linewidth=1.2,
            marker=marker,
            markersize=3,
            alpha=0.9,
        )
        if fill != "none" and idx == 0:
            ax.fill_between(x, values, alpha=0.08, color=color)

    _apply_pub_style(ax, title, x_label, y_label)

    if x_range:
        ax.set_xlim(x_range)
    if y_range:
        ax.set_ylim(y_range)

    # Date format if x is datetime
    if hasattr(x, "dtype") and "datetime" in str(x.dtype):
        ax.xaxis.set_major_formatter(DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()

    # Annotations
    for ann in annotations:
        ax.annotate(
            ann.get("text", ""),
            xy=(ann.get("x", 0), ann.get("y", 0)),
            fontsize=_PUB_FONTSIZE,
            ha="center",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.3),
        )

    ax.legend(fontsize=_PUB_LEGENDSIZE, loc="best")
    fig.tight_layout()
    return fig


def mpl_heatmap(
    z, x=None, y=None,
    title: str = "", x_label: str = "", y_label: str = "",
    cmap: str = "viridis",
    figsize: tuple = (7.0, 5.0),
    dpi: int = _PUB_DPI,
    config: dict = None,
) -> plt.Figure:
    """Publication-grade heatmap using matplotlib."""
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    z = np.asarray(z)
    if x is None:
        x = np.arange(z.shape[1])
    if y is None:
        y = np.arange(z.shape[0])

    im = ax.pcolormesh(x, y, z, shading="auto", cmap=cmap)
    cbar = fig.colorbar(im, ax=ax, shrink=0.75)
    cbar.set_label(y_label if y_label else "Value", fontsize=_PUB_LABELSIZE)
    cbar.ax.tick_params(labelsize=_PUB_TICK_SIZE)

    _apply_pub_style(ax, title, x_label, y_label)
    ax.invert_yaxis()
    fig.tight_layout()
    return fig


def mpl_scatter(
    x, y,
    title: str = "", x_label: str = "", y_label: str = "",
    show_trendline: bool = False,
    trendline_color: str = "#C44E52",
    figsize: tuple = _PUB_FIGSIZE,
    dpi: int = _PUB_DPI,
    config: dict = None,
) -> plt.Figure:
    """Publication-grade scatter plot with optional trendline."""
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    cfg = config or {}

    ax.scatter(x, y, c=_PUB_COLORS[0], s=20, alpha=0.7, edgecolors="none")

    if show_trendline and len(x) > 2:
        slope, intercept, r_val, *_ = _ols(list(x), list(y))
        trend_x = [min(x), max(x)]
        trend_y = [slope * v + intercept for v in trend_x]
        ax.plot(
            trend_x, trend_y,
            color=trendline_color, linestyle="--", linewidth=1.5,
            label=f"Trend (R\u00b2={r_val * r_val:.3f})",
        )
        ax.legend(fontsize=_PUB_LEGENDSIZE)

    _apply_pub_style(ax, title, x_label, y_label)

    if cfg.get("x_range"):
        ax.set_xlim(cfg["x_range"])
    if cfg.get("y_range"):
        ax.set_ylim(cfg["y_range"])

    fig.tight_layout()
    return fig


def mpl_profile(
    x, y,
    title: str = "", x_label: str = "Distance (m)", y_label: str = "Value",
    fill_area: bool = True,
    figsize: tuple = _PUB_FIGSIZE,
    dpi: int = _PUB_DPI,
    config: dict = None,
) -> plt.Figure:
    """Publication-grade profile / cross-section view."""
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    ax.plot(x, y, color=_PUB_COLORS[0], linewidth=1.5, marker="o", markersize=3)
    if fill_area:
        ax.fill_between(x, y, alpha=0.08, color=_PUB_COLORS[0])

    _apply_pub_style(ax, title, x_label, y_label)

    if config:
        if config.get("x_range"):
            ax.set_xlim(config["x_range"])
        if config.get("y_range"):
            ax.set_ylim(config["y_range"])

    fig.tight_layout()
    return fig


def figure_to_base64(fig: plt.Figure, dpi: int = _PUB_DPI) -> str:
    """Convert a matplotlib figure to a base64 PNG string."""
    import base64 as _b64, io as _io
    buf = _io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    buf.seek(0)
    return _b64.b64encode(buf.read()).decode("utf-8")


def save_pub_figure(fig: plt.Figure, path: str, dpi: int = _PUB_DPI):
    """Save a publication-grade figure to disk (PNG or PDF)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
    logger = logging.getLogger("research_agent.reporting")
    logger.info("Publication figure saved: %s", path)

