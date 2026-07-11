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

## 重要规则

1. **数据已预加载**: 如果有用户选择的数据文件，沙箱内已有变量 `df`（list of dicts，当做行列表处理），以及 `_col_names`（列名列表）、`_col_dtypes`（列类型字典）、`_row_count`（行数）。
   → 在代码开头将 df 转为 DataFrame: `df = pd.DataFrame(df)`
   → **不要尝试加载或读取任何文件** — 数据已在内存中。
2. **不要使用 from backend.analysis 导入** -- 这些模块在沙箱中不可用。
2. **不要重新定义 _results** -- _results 字典已由沙箱初始化，直接用 _results['_data']['key'] = value 存储结果。
3. **不要重新定义 _save_fig** -- _save_fig() 已由沙箱提供，直接调用 _save_fig('chart_name') 保存图表。
4. **只使用白名单中的库**: numpy, pandas, scipy, statsmodels, matplotlib, sklearn。
5. **不要执行文件 I/O 或网络请求**。
6. **使用 matplotlib 绘图**，调用 _save_fig() 保存每个生成的图表。
7. **将数值结果存入 _results['_data']** 字典，key 为可读的描述性名称。
8. **打印关键结果**到 stdout（print）。
9. **生成的代码应该是自包含的**，可以直接执行。
11. **添加足够的中文注释**解释每步操作。
12. **禁止引用未定义的变量**：沙箱中只定义了 _results 作为结果存储字典（见规则 2）。不允许使用 sandboxresults、results、result 或其他未在规则中声明的变量名。所有数值结果只能通过 _results["_data"]["key"] = value 存储。

## 输出格式
只输出纯 Python 代码，用 `python 标记包围。代码中不要包含任何解释性文字。
"""

def build_generation_prompt(
    query: str,
    data_type: str = "gnss",
    data_description: str = "",
    data_schema: Optional[dict] = None,
) -> list[Message]:
    """Build the message list for code generation.

    Parameters
    ----------
    query : str
        Natural language analysis query.
    data_type : str
        Type of monitoring data (gnss, insar, rainfall, groundwater, pore_pressure).
    data_description : str
        Optional description of available data columns and formats.
    data_schema : dict, optional
        Schema info extracted from actual data (column names, types, sample rows).

    Returns
    -------
    list[Message]
    """
    user_content = f"数据类型: {data_type}\n"
    if data_description:
        user_content += f"数据描述: {data_description}\n"
    if data_schema and data_schema.get("column_names"):
        user_content += "\n[Available Data Schema]\n"
        user_content += data_schema.get("data_description_text", "") + "\n"
        user_content += (
            "\nData is pre-loaded as variable ``df`` (list of dicts) in the sandbox. "
            "Convert it at the start of your code:\n"
            "  df = pd.DataFrame(df)\n"
            "Then analyze df directly. Do NOT load data from any file.\n"
        )
    else:
        user_content += (
            "\nNote: No actual data file provided. "
            "If your analysis requires real data, generate illustrative/sample code "
            "that the user can adapt with their own data.\n"
        )

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
    # Strip Python comments before checking dangerous patterns
    code_no_comments = re.sub(r'#.*$', '', code, flags=re.MULTILINE)
    for pattern in dangerous:
        if pattern in code_no_comments:
            return False, f"检测到危险操作: {pattern}"
    return True, ""


async def generate_code(
    query: str,
    data_type: str = "gnss",
    data_description: str = "",
    model_id: Optional[str] = None,
    data_schema: Optional[dict] = None,
) -> dict:
    """Generate Python code from natural language query.

    Parameters
    ----------
    query : str
    data_type : str
    data_description : str
    model_id : str, optional
    data_schema : dict, optional
        Real data schema for prompt injection.

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

    messages = build_generation_prompt(query, data_type, data_description, data_schema)
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
