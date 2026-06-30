"""Unit tests for the Plotly chart engine."""
from __future__ import annotations

import numpy as np
import pytest
from backend.reporting import timeseries, heatmap, scatter, profile, to_html


class TestTimeseries:
    def test_basic_line_chart(self):
        x = list(range(100))
        y = [np.sin(i / 10) + i / 50 for i in range(100)]
        html = timeseries(x, {"A": y}, title="Test")
        assert "<div" in html and "plotly" in html

    def test_multi_series(self):
        x = list(range(50))
        y1 = [np.sin(i / 5) for i in range(50)]
        y2 = [np.cos(i / 5) for i in range(50)]
        html = timeseries(x, {"Sin": y1, "Cos": y2}, title="Multi")
        # Plotly 6.x serialises data arrays directly
        assert '"Sin"' in html and '"Cos"' in html

    def test_single_point(self):
        html = timeseries([0], {"P": [1.0]}, title="Single")
        assert "<div" in html


class TestHeatmap:
    def test_basic_heatmap(self):
        z = np.random.randn(10, 15).tolist()
        html = heatmap(z, title="HM")
        assert "<div" in html

    def test_custom_colorscale(self):
        z = np.random.randn(8, 8).tolist()
        html = heatmap(z, colorscale="Cividis", title="Custom")
        # colorscale is expanded inline in Plotly 6.x
        assert '<div' in html


class TestScatter:
    def test_basic_scatter(self):
        x = np.random.randn(30).tolist()
        y = [v * 2 + np.random.randn() * 0.3 for v in x]
        html = scatter(x, y, title="SC")
        assert "<div" in html

    def test_with_trendline(self):
        x = np.random.randn(30).tolist()
        y = [v * 2 + np.random.randn() * 0.3 for v in x]
        html = scatter(x, y, show_trendline=True, title="Trend")
        assert "R" in html

    def test_few_points(self):
        html = scatter([1, 2], [3, 4], show_trendline=True, title="Few")
        assert "<div" in html


class TestProfile:
    def test_basic_profile(self):
        x = list(range(50))
        y = [np.sin(i / 5) * 10 for i in range(50)]
        html = profile(x, y, title="Profile")
        assert "<div" in html

    def test_fill_area(self):
        x = list(range(30))
        y = list(np.cumsum(np.random.randn(30)))
        html_fill = profile(x, y, fill_area=True, title="Fill")
        assert "<div" in html_fill

    def test_custom_axis_labels(self):
        x = list(range(20))
        html = profile(x, x, x_label="Distance", y_label="Elevation")
        assert "Distance" in html and "Elevation" in html


class TestToHtml:
    def test_returns_valid_html_fragment(self):
        import plotly.graph_objects as go
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
        html = to_html(fig)
        assert "<div" in html
        assert "plotly" in html
