"""Tests for chart generation with config support."""
from __future__ import annotations

import pytest
import numpy as np


class TestCharts:
    def test_timeseries(self):
        from backend.reporting.charts import timeseries
        x = np.linspace(0, 10, 100)
        y = {"A": np.sin(x), "B": np.cos(x)}
        html = timeseries(x, y, title="Test", x_label="Time", y_label="Value")
        assert isinstance(html, str)
        assert "plotly" in html.lower() or "svg" in html.lower() or "html" in html.lower()

    def test_heatmap(self):
        from backend.reporting.charts import heatmap
        z = np.random.randn(20, 30)
        html = heatmap(z, title="Test Heatmap")
        assert isinstance(html, str)

    def test_scatter(self):
        from backend.reporting.charts import scatter
        x = np.random.randn(100)
        y = 2 * x + np.random.randn(100) * 0.1
        html = scatter(x, y, title="Scatter", show_trendline=True)
        assert isinstance(html, str)

    def test_profile(self):
        from backend.reporting.charts import profile
        x = np.linspace(0, 10, 100)
        y = np.sin(x)
        html = profile(x, y, title="Profile")
        assert isinstance(html, str)

    def test_timeseries_with_config(self):
        from backend.reporting.charts import timeseries
        x = list(range(10))
        y = {"A": [v**2 for v in range(10)]}
        html = timeseries(x, y, title="Custom Title", x_label="Custom X", y_label="Custom Y")
        assert isinstance(html, str)


class TestMatplotlibCharts:
    """Test matplotlib publication-grade charts."""

    def test_mpl_timeseries(self):
        from backend.reporting.charts_matplotlib import mpl_timeseries, figure_to_base64
        import matplotlib
        matplotlib.use("Agg")
        x = np.linspace(0, 10, 100)
        y = {"A": np.sin(x)}
        fig = mpl_timeseries(x, y, title="MPL Test", x_label="X", y_label="Y")
        assert fig is not None
        b64 = figure_to_base64(fig)
        assert isinstance(b64, str)
        assert len(b64) > 100

    def test_mpl_timeseries_with_config(self):
        from backend.reporting.charts_matplotlib import mpl_timeseries
        import matplotlib
        matplotlib.use("Agg")
        x = np.linspace(0, 10, 100)
        y = {"A": np.sin(x)}
        config = {"chart_title": "Config Test", "x_label": "Time", "y_label": "Value", "line_width": 2.0, "show_markers": True}
        fig = mpl_timeseries(x, y, config=config)
        assert fig is not None

    def test_mpl_scatter(self):
        from backend.reporting.charts_matplotlib import mpl_scatter
        import matplotlib
        matplotlib.use("Agg")
        x = np.random.randn(50)
        y = 2 * x + np.random.randn(50) * 0.2
        fig = mpl_scatter(x, y, title="MPL Scatter", config={"color_scheme": "ggplot"})
        assert fig is not None

    def test_mpl_heatmap(self):
        from backend.reporting.charts_matplotlib import mpl_heatmap
        import matplotlib
        matplotlib.use("Agg")
        z = np.random.randn(15, 20)
        fig = mpl_heatmap(z, title="MPL Heatmap")
        assert fig is not None
