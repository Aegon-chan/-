"""NL to Python code generation.

Uses LLM to translate natural language analysis queries into executable
Python code that leverages the existing analysis modules.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from backend.models.registry import ModelRegistry
from backend.models.base import Message

logger = logging.getLogger("research_agent.codegen")


# ── Prompt template ──────────────────────────────────────────────────

CODEGEN_SYSTEM_PROMPT = """你是一位专业的地质灾害监测数据分析专家。你的任务是将用户的自然语言查询转换成可执行的 Python 代码。

## 可用的分析模块

```python
# GNSS 位移分析 (backend.analysis.gnss)
from backend.analysis.gnss import (
    decompose_timeseries,     # 时间序列分解: 趋势 + 季节 + 残差
    detect_step,              # 阶跃突变检测: 滑动窗口 t 检验
    estimate_velocity,        # 形变速率估计: 线性回归
    outlier_detection,        # 异常值检测: IQR / Z-Score
    signal_filter,            # 信号滤波: 移动平均 / Savitzky-Golay
)

# InSAR 形变分析 (backend.analysis.insar)
from backend.analysis.insar import (
    interpolate_deformation,   # 形变场插值: Kriging / IDW
    cumulative_displacement,   # 累积形变计算
    deformation_velocity,      # 形变速率图
)

# 降雨分析 (backend.analysis.rainfall)
from backend.analysis.rainfall import (
    cumulative_rainfall,       # 累计降雨量
    rainfall_intensity,        # 降雨强度分析
    return_period,             # 重现期估算: Gumbel / P-III
)

# 地下水位分析 (backend.analysis.groundwater)
from backend.analysis.groundwater import (
    water_level_dynamics,      # 水位动态曲线
    rainfall_correlation,      # 降雨相关性分析
)

# 孔压分析 (backend.analysis.pore_pressure)
from backend.analysis.pore_pressure import (
    pore_pressure_trend,       # 孔压变化趋势
    excess_pore_pressure,      # 超静孔压消散分析
)
```

## 代码生成规则

1. **始终先生成示例数据**（如果未提供数据），使用 numpy/pandas 构造合理的模拟数据。
2. **使用 matplotlib 绘图**，调用 `_save_fig()` 保存每个图表。
3. **将结果存入 `_results["_data"]`** 字典，key 为可读的描述性名称。
4. **打印关键结果**到 stdout（print）。
5. **只使用白名单中的库**: numpy, pandas, scipy, statsmodels, matplotlib, sklearn。
6. **不要执行文件 I/O 或网络请求**。
7. **添加足够的中文注释**解释每步操作。
8. **生成的代码应该是自包含的**，可以直接执行。

## 输出格式
只输出纯 Python 代码，用 ```python 标记包围。代码中不要包含任何解释性文字。
"""


def build_generation_prompt(query: str, data_type: str = "gnss",
                            data_description: str = "") -> list[Message]:
    """Build the message list for code generation.

    Parameters
    ----------
    query : str
        Natural language analysis query.
    data_type : str
        Type of monitoring data (gnss, insar, rainfall, groundwater, pore_pressure).
    data_description : str
        Optional description of available data columns and formats.

    Returns
    -------
    list[Message]
    """
    user_content = f"数据类型: {data_type}\n"
    if data_description:
        user_content += f"数据描述: {data_description}\n"
    user_content += f"分析需求: {query}\n"
    user_content += (
        "\n请生成完整的 Python 代码来完成上述分析。"
        "使用 matplotlib 绘图并通过 _save_fig() 保存。"
        "将数值结果存入 _results[\"_data\"]。"
    )

    return [
        Message(role="system", content=CODEGEN_SYSTEM_PROMPT),
        Message(role="user", content=user_content),
    ]


def extract_code_from_response(response: str) -> Optional[str]:
    """Extract Python code from LLM response.

    Looks for code blocks marked with ```python ... ``` or ``` ... ```.
    """
    pattern = r"```(?:python)?\n(.*?)```"
    match = re.search(pattern, response, re.DOTALL)
    if match:
        code = match.group(1).strip()
        return code
    if response.strip().startswith(("import ", "def ", "class ", "#", "from ")):
        return response.strip()
    return None


def validate_generated_code(code: str) -> tuple[bool, str]:
    """Basic validation of generated code.

    Returns (is_valid, error_message).
    """
    dangerous = [
        "import os", "from os import",
        "import subprocess", "from subprocess import",
        "__import__",
        "eval(", "exec(",
        "open(", "shutil", "socket",
        "requests", "urllib",
        "__builtins__", "compile(",
    ]
    for pattern in dangerous:
        if pattern in code:
            return False, f"检测到危险操作: {pattern}"
    return True, ""


async def generate_code(query: str, data_type: str = "gnss",
                        data_description: str = "",
                        model_id: Optional[str] = None) -> dict:
    """Generate Python code from natural language query.

    Parameters
    ----------
    query : str
    data_type : str
    data_description : str
    model_id : str, optional

    Returns
    -------
    dict with keys: code, success, error
    """
    llm = ModelRegistry.get_llm(model_id)
    if llm is None:
        llm = ModelRegistry.get_llm_with_fallback()
    if llm is None:
        return {"code": "", "success": False,
                "error": "没有可用的 AI 模型，请配置 API Key"}

    messages = build_generation_prompt(query, data_type, data_description)
    try:
        response = await llm.chat(messages)
        code = extract_code_from_response(response.content)
        if not code:
            return {"code": "", "success": False,
                    "error": "无法从 LLM 响应中提取代码"}

        valid, err_msg = validate_generated_code(code)
        if not valid:
            return {"code": "", "success": False, "error": err_msg}

        return {"code": code, "success": True, "error": ""}
    except Exception as e:
        logger.exception("Code generation failed")
        return {"code": "", "success": False, "error": str(e)}


def make_context_from_data(df_dict: dict) -> dict:
    """Convert DataFrames to dict for sandbox context injection."""
    context = {}
    for name, df in df_dict.items():
        if hasattr(df, "to_dict"):
            context[name] = df.to_dict(orient="records")
        else:
            context[name] = df
    return context
