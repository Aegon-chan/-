"""Report generation module (charts + reports)."""
from __future__ import annotations

from .charts import (
    to_html,
    save_html,
    save_image,
    timeseries,
    heatmap,
    scatter,
    profile,
)
from .report_generator import ReportGenerator

__all__ = [
    "timeseries", "heatmap", "scatter", "profile",
    "to_html", "save_html", "save_image",
    "ReportGenerator",
]
