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
   → **datetime 列已经自动转换**：沙箱已自动对 _datetime_columns 中的列执行 pd.to_datetime()，df 中的对应列可直接使用 .dt 访问器。
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
13. **子图网格尺寸必须与数据量匹配**：使用 `plt.subplots(nrows, ncols)` 时，保证网格能容纳所有子图。如果待绘制的图表数量是动态的（例如基于站点数），应基于数据动态计算 nrows/ncols，或者使用 `plt.subplots(1, N)` 扁平结构 + `axes[i]` 索引，而非硬编码固定行数后用 `axes[i, 0]` 二维索引。禁止生成可能越界的 `axes[i, 0]` 或 `axes[i, j]` 访问。
14. **使用 `plt.boxplot()` 而非 `ax.boxplot()`**：在绘制箱线图时，始终使用 `plt.boxplot(data, labels=...)` 而非 `ax.boxplot(data, labels=...)`，因为 Matplotlib 3.6+ 将 Axes 方法的 `labels` 参数重命名为 `tick_labels`，但 pyplot 版本保留了向下兼容的 `labels` 参数。

## 输出格式
只输出纯 Python 代码，用 `python 标记包围。代码中不要包含任何解释性文字。

15. **正确按年份筛选数据**：数据的时间列通常是 measurement_time。要筛选特定年份的数据，必须使用正确的条件过滤：
   - 正确写法：df_filtered = df[df["measurement_time"].dt.year == 2023]
   - 或：df_filtered = df[(df["measurement_time"] >= "2023-01-01") & (df["measurement_time"] <= "2023-12-31")]
   - 禁止使用 df.head(365)、df.iloc[:365] 等方式来获取某一年数据
   - 禁止使用 df.tail(365) 等方式
   数据可能跨越多个年份，具体时间范围会在 [Available Data Schema] 中给出。必须根据 measurement_time 列的内容来筛选，而不是通过行号截取。
16. **始终假设数据包含 measurement_time 列**（监测数据标准列名），类型为 datetime。如果需要按时间分析，先确保转换：df["measurement_time"] = pd.to_datetime(df["measurement_time"])。

17. **pandas 3.0 频率别名注意**：本环境中的 pandas 为 3.x 版本，`.resample()`, `pd.Grouper(freq=...)`, `pd.date_range(freq=...)` 等方法必须使用新版频率别名：
   - 使用 `'YE'`（替代已移除的 `'Y'`/`'A'`）— 年末
   - 使用 `'YS'`（替代已移除的 `'AS'`）— 年初
   - 使用 `'ME'`（替代已移除的 `'M'`/`'MS'`）— 月末
   - 使用 `'QE'`（替代已移除的 `'Q'`/`'QS'`）— 季度末
   - `'W'`, `'D'`, `'h'` 不变，可继续使用
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
        tr = data_schema.get("time_range")
        if tr:
            user_content += "\nData time range: " + tr["start"] + " ~ " + tr["end"] + " (column: " + tr["column"] + ")\n"

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
    """Convert DataFrames to dict for sandbox context injection.
15. **正确按年份筛选数据**：数据的时间列通常是 measurement_time。要筛选特定年份的数据，必须使用正确的条件过滤：
   - ✅ 正确写法：df_filtered = df[df['measurement_time'].dt.year == 2023]
   - ✅ 或：df_filtered = df[(df['measurement_time'] >= '2023-01-01') & (df['measurement_time'] <= '2023-12-31')]
   - ❌ 禁止使用：df.head(365)、df.iloc[:365] 等方式来获取某一年数据（数据起始日期不一定是1月1日）
   - ❌ 禁止使用：df.tail(365) 等方式
   数据可能跨越多个年份（2020-2026），具体时间范围会在 [Available Data Schema] 中给出。必须根据 measurement_time 列的内容来筛选，而不是通过行号截取。
16. **始终假设数据包含 measurement_time 列**（监测数据标准列名），类型为 datetime。如果需要按时间分析，先确保转换：df['measurement_time'] = pd.to_datetime(df['measurement_time'])。
"""
    context = {}
    for name, df in df_dict.items():
        if hasattr(df, "to_dict"):
            context[name] = df.to_dict(orient="records")
        else:
            context[name] = df
    return context
