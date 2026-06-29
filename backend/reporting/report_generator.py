"""报告生成引擎"""
from __future__ import annotations

from pathlib import Path


class ReportGenerator:
    """自动化监测报告生成器"""

    SUPPORTED_FORMATS = ["pdf", "docx", "html"]

    async def generate(self, data: dict, template: str = "default",
                       output_format: str = "pdf") -> str:
        return "/path/to/report"

    def list_templates(self) -> list:
        return ["default", "daily", "weekly", "monthly", "special"]
