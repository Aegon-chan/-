"""Unit tests for the ReportGenerator."""
from __future__ import annotations

import pathlib
import pytest
from backend.reporting import ReportGenerator


@pytest.fixture
def report_data():
    return {
        "title": "Test Report",
        "date": "2026-06-30",
        "summary": "Test summary with ASCII text.",
        "sections": [
            {
                "title": "Section 1",
                "content": "Content here.",
                "tables": [{"headers": ["ID", "Value"], "rows": [["A", 1.5], ["B", 2.3]]}],
            }
        ],
        "conclusion": "Normal range.",
        "metadata": {"site": "Test", "period": "2026-06"},
    }


class TestReportGenerator:
    def test_list_templates(self):
        rg = ReportGenerator()
        tpls = rg.list_templates()
        assert len(tpls) == 5
        for t in ["default", "daily", "weekly", "monthly", "special"]:
            assert t in tpls

    def test_generate_html(self, report_data):
        rg = ReportGenerator()
        out = rg.generate(report_data, template="default", output_format="html")
        assert out.endswith(".html")
        assert pathlib.Path(out).exists()
        content = pathlib.Path(out).read_text(encoding="utf-8")
        assert "Test Report" in content

    def test_generate_pdf(self, report_data):
        rg = ReportGenerator()
        out = rg.generate(report_data, template="default", output_format="pdf")
        assert out.endswith(".pdf")
        assert pathlib.Path(out).exists()

    def test_generate_docx(self, report_data):
        rg = ReportGenerator()
        out = rg.generate(report_data, template="default", output_format="docx")
        assert out.endswith(".docx")
        assert pathlib.Path(out).exists()

    @pytest.mark.parametrize("tpl", ["daily", "weekly", "monthly", "special"])
    def test_all_templates(self, report_data, tpl):
        rg = ReportGenerator()
        out = rg.generate(report_data, template=tpl, output_format="html")
        assert pathlib.Path(out).exists()

    def test_custom_output_dir(self, tmp_path):
        rg = ReportGenerator(output_dir=tmp_path)
        out = rg.generate({"title": "T", "sections": []}, template="default", output_format="html")
        assert str(tmp_path) in out

    def test_empty_data(self):
        rg = ReportGenerator()
        out = rg.generate({}, template="default", output_format="html")
        assert pathlib.Path(out).exists()
