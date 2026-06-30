"""
Report generation engine.

Produces monitoring reports in HTML, DOCX, and PDF formats
using Jinja2 templates (+ Plotly charts), python-docx, and fpdf2.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from backend.reporting.charts import save_image, timeseries

logger = logging.getLogger("research_agent.reporting")

# ── 路径 ─────────────────────────────────────────────────────
_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_DEFAULT_OUTPUT_DIR = Path.cwd() / "reports" / "output"


class ReportGenerator:
    """Automated monitoring report generator."""

    SUPPORTED_FORMATS = ["html", "docx", "pdf"]

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        templates_dir: Optional[Path] = None,
    ):
        self.output_dir = Path(output_dir or _DEFAULT_OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        templates_path = templates_dir or _TEMPLATES_DIR
        self._env = Environment(
            loader=FileSystemLoader(str(templates_path)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    # ── 公开 API ─────────────────────────────────────────────

    def generate(
        self,
        data: dict,
        template: str = "default",
        output_format: str = "html",
    ) -> str:
        """Generate a report and return the output file path.

        Parameters
        ----------
        data : dict
            Report data. Expected keys:
                title, date, report_type, summary, sections (list of dict),
                conclusion, metadata (dict with site, period, etc.)
        template : str
            Template name (without extension) — one of ``list_templates()``.
        output_format : str
            ``"html"``, ``"docx"``, or ``"pdf"``.

        Returns
        -------
        str
            Absolute path to the generated report file.
        """
        data.setdefault("date", datetime.now().strftime("%Y-%m-%d %H:%M"))
        data.setdefault("report_type", template)
        data.setdefault("sections", [])
        data.setdefault("metadata", {})

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = f"report_{template}_{ts}"
        out_path = self.output_dir / f"{stem}.{output_format}"

        if output_format == "docx":
            return self._render_docx(data, out_path)
        elif output_format == "pdf":
            return self._render_pdf(data, out_path)
        else:
            html = self._render_html(template, data)
            out_path.write_text(html, encoding="utf-8")
            logger.info("Report saved: %s", out_path)
            return str(out_path.resolve())

    def list_templates(self) -> list[str]:
        """Return available template names."""
        return ["default", "daily", "weekly", "monthly", "special"]

    # ── HTML ─────────────────────────────────────────────────

    def _render_html(self, template_name: str, data: dict) -> str:
        """Render a Jinja2 template to an HTML string."""
        tpl = self._env.get_template(f"{template_name}.html.j2")
        # Render chart placeholders inline
        return tpl.render(**data)

    # ── DOCX ─────────────────────────────────────────────────

    def _render_docx(self, data: dict, out_path: Path) -> str:
        """Build a .docx report from data using python-docx."""
        from docx import Document
        from docx.shared import Inches, Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = Document()

        # ── 标题页 ──
        title_p = doc.add_heading(data.get("title", "Report"), level=0)
        title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        meta = doc.add_paragraph()
        meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = meta.add_run(f'{data.get("date", "")}  |  {data.get("report_type", "")}')
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

        if data.get("summary"):
            doc.add_heading("摘要", level=1)
            doc.add_paragraph(data["summary"])

        # ── 各章节 ──
        for section in data.get("sections", []):
            doc.add_heading(section.get("title", ""), level=1)
            doc.add_paragraph(section.get("content", ""))

            # 嵌入图表（静态图）
            for chart_html in section.get("charts", []):
                img_path = self._chart_html_to_temp_png(chart_html, out_path.stem)
                if img_path:
                    doc.add_picture(str(img_path), width=Inches(5.5))
                    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

            # 表格
            for table_data in section.get("tables", []):
                headers = table_data.get("headers", [])
                rows = table_data.get("rows", [])
                if not headers:
                    continue
                tbl = doc.add_table(rows=1 + len(rows), cols=len(headers))
                tbl.style = "Light Grid Accent 1"
                for j, h in enumerate(headers):
                    tbl.rows[0].cells[j].text = str(h)
                for i, row in enumerate(rows):
                    for j, val in enumerate(row):
                        tbl.rows[i + 1].cells[j].text = str(val)

        if data.get("conclusion"):
            doc.add_heading("结论与建议", level=1)
            doc.add_paragraph(data["conclusion"])

        doc.save(str(out_path))
        logger.info("DOCX report saved: %s", out_path)
        return str(out_path.resolve())

    # ── PDF ──────────────────────────────────────────────────

    
    @staticmethod
    def _sanitize_text(text: str, max_len: int = 200) -> str:
        """Strip characters that cannot be rendered by the core PDF font."""
        sanitized = text.encode("latin-1", errors="replace").decode("latin-1")
        if len(sanitized) > max_len:
            sanitized = sanitized[:max_len] + "..."
        return sanitized


    def _render_pdf(self, data: dict, out_path: Path) -> str:
        """Build a PDF report using fpdf2."""
        from fpdf import FPDF

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=20)

        # Safely render text, stripping non-Latin-1 characters
        def s(text: str) -> str:
            return self._sanitize_text(text)

        # Title
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(0, 12, s(data.get("title", "Report")), new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 8, s(f'{data.get("date", "")} | {data.get("report_type", "")}'),
                 new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(6)

        # Summary
        if data.get("summary"):
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(0, 10, "Summary", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 6, s(data["summary"]))
            pdf.ln(4)

        # Sections
        for section in data.get("sections", []):
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(0, 10, s(section.get("title", "")), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 6, s(section.get("content", "")))
            pdf.ln(3)

            for table_data in section.get("tables", []):
                headers = table_data.get("headers", [])
                rows = table_data.get("rows", [])
                if not headers:
                    continue
                col_w = 180 // max(len(headers), 1)
                pdf.set_font("Helvetica", "B", 9)
                for h in headers:
                    pdf.cell(col_w, 8, s(str(h)), border=1, align="C")
                pdf.ln()
                pdf.set_font("Helvetica", "", 9)
                for row in rows:
                    for val in row:
                        pdf.cell(col_w, 7, s(str(val))[:20], border=1, align="C")
                    pdf.ln()
                pdf.ln(4)

        # Conclusion
        if data.get("conclusion"):
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(0, 10, "Conclusion", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 6, s(data["conclusion"]))

        pdf.output(str(out_path))
        logger.info("PDF report saved: %s", out_path)
        return str(out_path.resolve())

    def _chart_html_to_temp_png(self, chart_html: str, stem: str) -> Optional[Path]:
        """Attempt to render an inline Plotly chart to a temp PNG for DOCX embedding."""
        import re

        match = re.search(r"data:\[(.*?)\];", chart_html, re.DOTALL)
        if not match:
            return None
        try:
            import plotly.io as pio
            from plotly.graph_objects import Figure

            fig = Figure()
            data_json = f"[{match.group(1)}]"
            fig.add_trace(eval(data_json))
            img_dir = self.output_dir / "_chart_imgs"
            img_dir.mkdir(parents=True, exist_ok=True)
            img_path = img_dir / f"{stem}_chart.png"
            save_image(fig, img_path, scale=1)
            return img_path
        except Exception:
            logger.warning("Could not export chart to PNG for DOCX", exc_info=True)
            return None

    def _html_to_pdf(self, html: str, out_path: Path) -> str:
        """Convert HTML to PDF via weasyprint (if available), otherwise fpdf2."""
        try:
            import weasyprint
            weasyprint.HTML(string=html).write_pdf(str(out_path))
            logger.info("PDF report saved (weasyprint): %s", out_path)
        except Exception:
            logger.warning("weasyprint unavailable; HTML report saved instead.")
            out_path = out_path.with_suffix(".html")
            out_path.write_text(html, encoding="utf-8")
        return str(out_path.resolve())
