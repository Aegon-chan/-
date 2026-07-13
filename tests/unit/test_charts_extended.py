"""
Extended tests for the image generation module.

Covers:
- charts.py: to_html, save_html, save_image, helpers, edge cases
- charts_matplotlib.py: mpl_profile, figure_to_base64, save_pub_figure, edge cases
- report_generator.py: full ReportGenerator coverage (HTML, DOCX, PDF)
"""
from __future__ import annotations

import base64
from pathlib import Path

import numpy as np
import pytest


# ==============================================================
# Plotly charts — extended edge cases & uncovered functions
# ==============================================================


class TestChartsExtended:
    """Edge cases and untested functions for charts.py."""

    def test_to_html(self):
        """to_html() should return a valid embeddable HTML div string."""
        from backend.reporting.charts import to_html
        import plotly.graph_objects as go

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
        html = to_html(fig)
        assert isinstance(html, str)
        assert "plotly" in html or "Plotly" in html or "js" in html
        assert "<div" in html

    def test_save_html(self, tmp_path):
        """save_html() should write a standalone HTML file."""
        from backend.reporting.charts import save_html
        import plotly.graph_objects as go

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[1, 2], y=[3, 4]))
        out = tmp_path / "test_chart.html"
        result = save_html(fig, out)
        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "plotly" in content.lower()

    def test_save_image_fallback(self, tmp_path):
        """save_image() should fall back to .html when kaleido is missing."""
        from backend.reporting.charts import save_image
        import plotly.graph_objects as go

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[1, 2], y=[3, 4]))
        png_path = tmp_path / "test_img.png"
        result = save_image(fig, png_path)
        assert result.exists()
        if result.suffix == ".html":
            content = result.read_text(encoding="utf-8")
            assert "plotly" in content.lower()

    def test_hex_to_rgba(self):
        """_hex_to_rgba should convert hex to RGBA tuple."""
        from backend.reporting.charts import _hex_to_rgba

        result = _hex_to_rgba("#4C72B0", 0.15)
        assert result == (76, 114, 176, 0.15)

        result2 = _hex_to_rgba("#FFF", 0.5)
        assert result2[3] == 0.5
        assert result2[0] == 255

    def test_ols_regression(self):
        """_ols should return slope, intercept, r_value."""
        from backend.reporting.charts import _ols

        x = [1, 2, 3, 4, 5]
        y = [2, 4, 6, 8, 10]
        slope, intercept, r_val, *_ = _ols(x, y)
        assert slope == pytest.approx(2.0, abs=1e-10)
        assert intercept == pytest.approx(0.0, abs=1e-10)
        assert r_val == pytest.approx(1.0, abs=1e-10)

    def test_timeseries_multi_series(self):
        """timeseries() should handle multiple series."""
        from backend.reporting.charts import timeseries

        x = list(range(10))
        y = {"A": [v**2 for v in range(10)], "B": [v * 2 for v in range(10)]}
        html = timeseries(x, y, title="Multi")
        assert isinstance(html, str) and len(html) > 200

    def test_timeseries_empty_dict(self):
        """timeseries() should handle empty y dict."""
        from backend.reporting.charts import timeseries

        html = timeseries([1, 2, 3], {}, title="Empty")
        assert isinstance(html, str) and len(html) > 50

    def test_timeseries_with_fill(self):
        """timeseries() should handle fill='tozeroy'."""
        from backend.reporting.charts import timeseries

        html = timeseries([1, 2, 3], {"A": [1, 2, 3]}, fill="tozeroy")
        assert isinstance(html, str)

    def test_scatter_few_points(self):
        """scatter() with <3 points and trendline should still work."""
        from backend.reporting.charts import scatter

        html = scatter([1, 2], [3, 4], show_trendline=True)
        assert isinstance(html, str)

    def test_heatmap_custom_dimensions(self):
        """heatmap() should accept custom height/width."""
        from backend.reporting.charts import heatmap

        z = np.random.randn(10, 15)
        html = heatmap(z, title="Custom Size", width=900, height=600)
        assert isinstance(html, str) and "900" in html

    def test_profile_fill_false(self):
        """profile() with fill_area=False."""
        from backend.reporting.charts import profile

        x = list(range(10))
        y = [v**0.5 for v in x]
        html = profile(x, y, fill_area=False)
        assert isinstance(html, str)

    def test_save_html_auto_creates_dir(self, tmp_path):
        """save_html() should create parent directory if missing."""
        from backend.reporting.charts import save_html
        import plotly.graph_objects as go

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[1], y=[2]))
        out = tmp_path / "nested" / "dir" / "chart.html"
        result = save_html(fig, out)
        assert result.exists()


# ==============================================================
# Matplotlib charts — untested functions & edge cases
# ==============================================================


class TestMatplotlibExtended:
    """Edge cases and untested functions for charts_matplotlib.py."""

    @pytest.fixture(autouse=True)
    def _agg_backend(self):
        import matplotlib
        matplotlib.use("Agg")

    def test_mpl_profile(self):
        """mpl_profile() should generate a profile figure."""
        from backend.reporting.charts_matplotlib import mpl_profile

        x = np.linspace(0, 10, 50)
        y = np.sin(x)
        fig = mpl_profile(x, y, title="MPL Profile", x_label="Dist", y_label="Val")
        assert fig is not None

    def test_mpl_profile_no_fill(self):
        """mpl_profile() with fill_area=False."""
        from backend.reporting.charts_matplotlib import mpl_profile

        fig = mpl_profile(np.linspace(0, 10, 20), np.cos(np.linspace(0, 10, 20)), fill_area=False)
        assert fig is not None

    def test_mpl_profile_with_config(self):
        """mpl_profile() with x_range / y_range in config."""
        from backend.reporting.charts_matplotlib import mpl_profile

        x = np.linspace(0, 20, 100)
        y = np.sin(x)
        config = {"x_range": (1, 10), "y_range": (-0.5, 0.5)}
        fig = mpl_profile(x, y, config=config)
        assert fig is not None
        ax = fig.axes[0]
        assert ax.get_xlim()[0] == pytest.approx(1.0, abs=0.1)
        assert ax.get_ylim()[0] == pytest.approx(-0.5, abs=0.1)

    def test_figure_to_base64(self):
        """figure_to_base64() should produce a valid base64 PNG."""
        from backend.reporting.charts_matplotlib import mpl_timeseries, figure_to_base64

        x = np.linspace(0, 5, 50)
        y = {"A": np.sin(x)}
        fig = mpl_timeseries(x, y)
        b64 = figure_to_base64(fig)
        assert isinstance(b64, str) and len(b64) > 500
        decoded = base64.b64decode(b64)
        assert decoded[:4] == b"\x89PNG"

    def test_save_pub_figure(self, tmp_path):
        """save_pub_figure() should write to disk."""
        from backend.reporting.charts_matplotlib import mpl_timeseries, save_pub_figure

        x = np.linspace(0, 5, 50)
        y = {"A": np.sin(x)}
        fig = mpl_timeseries(x, y)
        out = tmp_path / "pub_fig.png"
        save_pub_figure(fig, str(out))
        assert out.exists() and out.stat().st_size > 500

    def test_save_pub_figure_creates_dir(self, tmp_path):
        """save_pub_figure() should create parent dir."""
        from backend.reporting.charts_matplotlib import mpl_timeseries, save_pub_figure

        x = np.linspace(0, 3, 30)
        y = {"A": np.cos(x)}
        fig = mpl_timeseries(x, y)
        out = tmp_path / "nested_output" / "fig.png"
        save_pub_figure(fig, str(out))
        assert out.exists()

    def test_mpl_scatter_trendline(self):
        """mpl_scatter() with show_trendline=True."""
        from backend.reporting.charts_matplotlib import mpl_scatter

        x = np.random.randn(50)
        y = 2 * x + np.random.randn(50) * 0.1
        fig = mpl_scatter(x, y, show_trendline=True)
        assert fig is not None

    def test_mpl_timeseries_datetime_x(self):
        """mpl_timeseries() with datetime x-axis."""
        from backend.reporting.charts_matplotlib import mpl_timeseries
        import datetime

        base = datetime.datetime(2025, 1, 1)
        x = np.array([base + datetime.timedelta(days=i) for i in range(30)])
        y = {"A": np.random.randn(30).cumsum()}
        fig = mpl_timeseries(x, y, title="Date Axis")
        assert fig is not None

    def test_mpl_timeseries_with_annotations(self):
        """mpl_timeseries() with annotations in config."""
        from backend.reporting.charts_matplotlib import mpl_timeseries

        x = np.linspace(0, 10, 100)
        y = {"A": np.sin(x)}
        config = {"annotations": [{"x": 5, "y": 1, "text": "Peak"}]}
        fig = mpl_timeseries(x, y, config=config)
        assert fig is not None


# ==============================================================
# Report generator — full coverage
# ==============================================================


class TestReportGenerator:
    """ReportGenerator class — all output formats."""

    SAMPLE_DATA = {
        "title": "Test Report",
        "date": "2026-07-13",
        "report_type": "daily",
        "summary": "This is a test summary.",
        "sections": [
            {
                "title": "Section 1",
                "content": "Content for section 1.",
                "charts": [],
                "tables": [
                    {"headers": ["Name", "Value"], "rows": [["A", "1"], ["B", "2"]]},
                ],
            },
        ],
        "conclusion": "Test conclusion.",
        "metadata": {"site": "Test Site", "period": "2026-07"},
    }

    def test_list_templates(self):
        """list_templates() should return known template names."""
        from backend.reporting.report_generator import ReportGenerator

        gen = ReportGenerator()
        templates = gen.list_templates()
        assert all(t in templates for t in ["default", "daily", "weekly", "monthly", "special"])

    def test_generate_html(self, tmp_path):
        """generate() with format='html' should produce valid HTML."""
        from backend.reporting.report_generator import ReportGenerator

        gen = ReportGenerator(output_dir=tmp_path)
        result = gen.generate(self.SAMPLE_DATA, template="default", output_format="html")
        content = Path(result).read_text(encoding="utf-8")
        assert "Test Report" in content
        assert "Test conclusion" in content

    def test_generate_html_empty_data(self, tmp_path):
        """generate() should handle minimal data."""
        from backend.reporting.report_generator import ReportGenerator

        gen = ReportGenerator(output_dir=tmp_path)
        result = gen.generate({"title": "Minimal"}, template="default", output_format="html")
        assert "Minimal" in Path(result).read_text(encoding="utf-8")

    def test_generate_docx(self, tmp_path):
        """generate() with format='docx' should produce valid DOCX."""
        from backend.reporting.report_generator import ReportGenerator

        gen = ReportGenerator(output_dir=tmp_path)
        result = gen.generate(self.SAMPLE_DATA, template="default", output_format="docx")
        path = Path(result)
        assert path.exists() and path.suffix == ".docx" and path.stat().st_size > 500

    def test_generate_pdf(self, tmp_path):
        """generate() with format='pdf' should produce a PDF."""
        from backend.reporting.report_generator import ReportGenerator

        gen = ReportGenerator(output_dir=tmp_path)
        result = gen.generate(self.SAMPLE_DATA, template="default", output_format="pdf")
        path = Path(result)
        assert path.exists() and path.suffix == ".pdf" and path.stat().st_size > 100

    def test_generate_all_templates_html(self, tmp_path):
        """All 5 templates should render to HTML."""
        from backend.reporting.report_generator import ReportGenerator

        gen = ReportGenerator(output_dir=tmp_path)
        for tpl in ["default", "daily", "weekly", "monthly", "special"]:
            result = gen.generate(self.SAMPLE_DATA, template=tpl, output_format="html")
            assert Path(result).exists(), f"Template '{tpl}' failed"

    def test_sanitize_text(self):
        """_sanitize_text strips non-Latin-1 and truncates."""
        from backend.reporting.report_generator import ReportGenerator

        raw = "Hello 中国 World! cafe"
        sanitized = ReportGenerator._sanitize_text(raw, max_len=50)
        assert "Hello" in sanitized and "World" in sanitized

        short = ReportGenerator._sanitize_text("Hello World", max_len=5)
        assert len(short) <= 8  # "Hello..."

    def test_all_formats_consistency(self, tmp_path):
        """All three formats should produce files."""
        from backend.reporting.report_generator import ReportGenerator

        gen = ReportGenerator(output_dir=tmp_path)
        for fmt in ["html", "docx", "pdf"]:
            result = gen.generate(self.SAMPLE_DATA, template="default", output_format=fmt)
            path = Path(result)
            assert path.exists()
            assert path.suffix == f".{fmt}"
