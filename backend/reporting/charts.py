"""图表生成模块"""
from __future__ import annotations


class ChartGenerator:
    """专业图表生成器"""

    def timeseries(self, data, title: str = "") -> str:
        return "/path/to/timeseries.html"

    def heatmap(self, data, title: str = "") -> str:
        return "/path/to/heatmap.html"

    def scatter(self, x, y, title: str = "") -> str:
        return "/path/to/scatter.html"

    def profile(self, data, title: str = "") -> str:
        return "/path/to/profile.html"
