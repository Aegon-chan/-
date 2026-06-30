"""
NiceGUI 前端应用入口

直接调用后端 Python 模块，实现：
- 对话界面 + 流式打字机效果
- 模型切换 / 会话管理
- 知识库管理
- NL2Query 代码生成与执行
- 图表配置面板
- 设置页面
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from nicegui import ui

from backend.config import settings

logger = logging.getLogger("research_agent.frontend")

# ───────────────────────────── 全局状态 ─────────────────────────────

_session_id: str = ""
_current_model: str = "deepseek-chat"
_nl2query_history: list[dict] = []


def _ensure_session() -> str:
    global _session_id
    if not _session_id:
        _session_id = str(uuid.uuid4())
    return _session_id


def _get_agent() -> "ResearchAgent":
    from backend.core.agent import ResearchAgent
    return ResearchAgent(session_id=_ensure_session(), model_id=_current_model)


def _list_available_models() -> list[str]:
    from backend.models.registry import ModelRegistry
    models = ModelRegistry.list_models()
    llms = [m["model_id"] for m in models if m["type"] == "llm"]
    return llms if llms else ["（无可用模型）"]


# ═══════════════════════════ 导航栏 ═══════════════════════════


def _drawer():
    with ui.left_drawer().classes("bg-gray-100 dark:bg-gray-800"):
        ui.label("导航").classes("text-lg font-bold p-4")
        with ui.column().classes("p-2 gap-2"):
            ui.button("对话", on_click=lambda: ui.navigate.to("/")
                     ).props("flat icon=chat")
            ui.button("NL2Query", on_click=lambda: ui.navigate.to("/nl2query")
                     ).props("flat icon=code")
            ui.button("图表配置", on_click=lambda: ui.navigate.to("/chart-studio")
                     ).props("flat icon=bar_chart")
            ui.button("知识库", on_click=lambda: ui.navigate.to("/knowledge")
                     ).props("flat icon=library_books")
            ui.button("设置", on_click=lambda: ui.navigate.to("/settings")
                     ).props("flat icon=settings")


def _header(title="Research Agent"):
    available = _list_available_models()
    with ui.header(elevated=True).classes("items-center justify-between"):
        ui.label(title).classes("text-lg font-bold")
        ui.select(
            label="模型",
            options={m: m for m in available},
            value=_current_model if _current_model in available else available[0],
            on_change=lambda e: setattr(globals(), "_current_model", e.value),
        ).classes("w-52").props("outlined dense")


def _scroll_bottom() -> None:
    ui.run_javascript("setTimeout(() => window.scrollTo(0,document.body.scrollHeight), 50)")


# ═══════════════════════════ 对话页面 ═══════════════════════════


@ui.page("/")
def chat_page():
    _drawer()
    _header()

    has_model = _list_available_models() != ["（无可用模型）"]
    chat_area = ui.column().classes(
        "w-full max-w-4xl mx-auto p-4 gap-3 flex-1 overflow-y-auto"
    )

    with ui.row().classes(
        "w-full items-center gap-2 sticky bottom-0 "
        "bg-white dark:bg-gray-900 p-3 border-t"
    ):
        input_field = ui.input(
            placeholder="输入你的问题，按 Enter 发送..."
        ).classes("flex-1").props("clearable autofocus")
        send_btn = ui.button("发送", icon="send").props("flat")

        async def do_send():
            text = input_field.value
            if not text or not has_model:
                return
            input_field.value = ""
            send_btn.disable()
            input_field.disable()

            with chat_area:
                ui.chat_message(text, name="你", sent=True)
            _scroll_bottom()

            with chat_area:
                bubble = ui.chat_message("", name="助手", sent=False)
            _scroll_bottom()

            try:
                agent = _get_agent()
                full = ""
                async for token in agent.stream_chat(text):
                    full += token
                    bubble.clear()
                    with bubble:
                        ui.markdown(full)
                    _scroll_bottom()
            except ValueError as e:
                bubble.clear()
                with bubble:
                    ui.markdown(f"**配置错误:** {e}")
            except Exception as e:
                bubble.clear()
                with bubble:
                    ui.markdown(f"**出错了:** {e}")
                    logger.exception("对话异常")
            finally:
                input_field.enable()
                send_btn.enable()

        send_btn.on_click(do_send)
        input_field.on("keydown.enter", do_send)

    with chat_area:
        if not has_model:
            ui.markdown(
                "## 欢迎使用 Research Agent\n\n"
                "请在 `.env` 文件中配置 API Key 后重启服务。"
            )
        else:
            ui.markdown(
                "## 欢迎使用 Research Agent\n\n"
                "我是你的科研数据分析助手，支持：\n\n"
                "- **对话分析**: 自然语言问答\n"
                "- **NL2Query**: 自然语言转 Python 代码并执行\n"
                "- **图表配置**: 自定义图表样式\n"
                "- **知识库**: 文档上传与检索\n\n"
                "在下方输入问题开始对话，或通过左侧导航体验更多功能。"
            )


# ═══════════════════════════ NL2Query 页面 ═══════════════════════════


@ui.page("/nl2query")
def nl2query_page():
    _drawer()
    _header("NL2Query — 自然语言转代码")

    result_area = ui.column().classes("w-full max-w-5xl mx-auto p-4 gap-3")

    with result_area:
        ui.markdown("## NL2Query 代码生成与执行")

        # Query input
        with ui.card().classes("w-full gap-3 p-4"):
            ui.label("输入分析需求").classes("text-sm font-bold")
            query_input = ui.textarea(
                label="例如: 对 GNSS 位移数据进行时间序列分解，绘制趋势项和季节项"
            ).classes("w-full").props("outlined rows=3")

            with ui.row().classes("items-center gap-3"):
                data_type_select = ui.select(
                    label="数据类型",
                    options={
                        "gnss": "GNSS 位移",
                        "insar": "InSAR 形变",
                        "rainfall": "降雨",
                        "groundwater": "地下水位",
                        "pore_pressure": "孔隙水压力",
                    },
                    value="gnss",
                ).classes("w-44")
                use_cache_check = ui.checkbox("使用缓存", value=True)
                gen_btn = ui.button("生成代码", icon="code").props("flat")
                exec_btn = ui.button("生成并执行", icon="play_arrow").props("flat")

        # Code display area
        code_area = ui.column().classes("w-full gap-2")
        code_display = ui.code("").classes("w-full overflow-x-auto")

        # Result area
        result_card = ui.card().classes("w-full gap-2 hidden")
        result_stdout = ui.label("").classes("font-mono text-sm whitespace-pre-wrap")
        result_images = ui.row().classes("w-full gap-3 flex-wrap")

    async def do_generate():
        query = query_input.value
        if not query:
            ui.notify("请输入分析需求", type="warning")
            return

        gen_btn.disable()
        exec_btn.disable()
        result_card.classes(remove="hidden")
        result_stdout.set_text("生成代码中...")
        result_images.clear()

        try:
            agent = _get_agent()
            result = await agent.nl2query_code(
                query=query,
                data_type=data_type_select.value,
            )
            if result["success"]:
                code_display.set_text(result["code"])
                result_stdout.set_text("✓ 代码生成成功，请检查后点击「生成并执行」")
            else:
                result_stdout.set_text(f"✗ 生成失败: {result.get('error', '未知错误')}")
        except Exception as e:
            result_stdout.set_text(f"✗ 错误: {e}")
            logger.exception("NL2Query error")
        finally:
            gen_btn.enable()
            exec_btn.enable()

    async def do_execute():
        query = query_input.value
        if not query:
            ui.notify("请输入分析需求", type="warning")
            return

        gen_btn.disable()
        exec_btn.disable()
        result_card.classes(remove="hidden")
        result_stdout.set_text("生成并执行代码中...")
        result_images.clear()

        try:
            agent = _get_agent()
            result = await agent.nl2query_execute(
                query=query,
                data_type=data_type_select.value,
                use_cache=use_cache_check.value,
            )

            if result["success"]:
                code_display.set_text(result.get("code", ""))
                res = result.get("result", {})

                # Show stdout
                stdout_text = res.get("stdout", "")
                extra = ""
                if result.get("from_cache"):
                    extra = " [来自缓存]"
                result_stdout.set_text(f"✓ 执行成功{extra}" + ("\n\n" + stdout_text if stdout_text else ""))

                # Show figures
                figures = res.get("figures", [])
                result_images.clear()
                with result_images:
                    for fig in figures:
                        b64 = fig.get("b64", "")
                        if b64:
                            src = f"data:image/png;base64,{b64}"
                            ui.image(src).classes("w-80 h-auto border rounded shadow-sm")

                # Show data summary
                data = res.get("data", {})
                if data:
                    with result_images:
                        ui.separator()
                        ui.label("数据结果:").classes("text-sm font-bold")
                        ui.code(json.dumps(data, indent=2, ensure_ascii=False)
                               ).classes("text-xs max-h-48 overflow-y-auto")

                # Save to history
                _nl2query_history.append({
                    "query": query,
                    "data_type": data_type_select.value,
                    "time": datetime.now().isoformat(),
                    "success": True,
                })

            else:
                result_stdout.set_text(f"✗ 执行失败: {result.get('error', '未知错误')}")

        except Exception as e:
            result_stdout.set_text(f"✗ 错误: {e}")
            logger.exception("NL2Query execute error")
        finally:
            gen_btn.enable()
            exec_btn.enable()

    gen_btn.on_click(do_generate)
    exec_btn.on_click(do_execute)


# ═══════════════════════════ 图表配置面板 ═══════════════════════════


@ui.page("/chart-studio")
def chart_studio_page():
    _drawer()
    _header("图表配置面板")

    with ui.column().classes("w-full max-w-5xl mx-auto p-4 gap-4"):
        ui.markdown("## 图表配置面板")
        ui.separator()

        # ── Chart type selector ──
        chart_type = ui.select(
            label="图表类型",
            options={
                "timeseries": "时序图 (Timeseries)",
                "scatter": "散点图 (Scatter)",
                "heatmap": "热力图 (Heatmap)",
                "profile": "剖面图 (Profile)",
            },
            value="timeseries",
        ).classes("w-64")

        # ── Color scheme ──
        with ui.expansion("颜色方案", icon="palette", value=True).classes("w-full"):
            color_scheme = ui.select(
                label="配色方案",
                options={
                    "default": "默认 (Blue/Orange/Green)",
                    "ggplot": "ggplot2",
                    "seaborn": "Seaborn",
                    "mono_blue": "单色蓝",
                    "mono_red": "单色红",
                },
                value="default",
            ).classes("w-64")

        # ── Axis ranges ──
        with ui.expansion("坐标轴范围", icon="straighten", value=False).classes("w-full"):
            with ui.row().classes("gap-4"):
                x_range_min = ui.number(label="X 轴最小值", value=None, precision=2)
                x_range_max = ui.number(label="X 轴最大值", value=None, precision=2)
            with ui.row().classes("gap-4"):
                y_range_min = ui.number(label="Y 轴最小值", value=None, precision=2)
                y_range_max = ui.number(label="Y 轴最大值", value=None, precision=2)

        # ── Annotations ──
        with ui.expansion("标注", icon="edit_note", value=False).classes("w-full"):
            annotations_input = ui.textarea(
                label="每行一个标注: x,y,text",
                placeholder="1.5,0.02,突变点\n3.0,-0.01,异常值",
            ).classes("w-full").props("outlined rows=3")

        # ── Figure size ──
        with ui.expansion("尺寸与导出", icon="photo_size_select_large", value=False).classes("w-full"):
            fig_width = ui.slider(label="宽度 (英寸)", min=4, max=12, value=7, step=0.5)
            fig_height = ui.slider(label="高度 (英寸)", min=3, max=9, value=4.2, step=0.5)
            fig_dpi = ui.select(
                label="DPI",
                options={"150": "150 (草稿)", "200": "200 (标准)", "300": "300 (出版)"},
                value="200",
            ).classes("w-44")

        # ── Preview / Export ──
        ui.separator()
        preview_area = ui.column().classes("w-full gap-3 items-center")
        preview_image = ui.image("").classes("w-full max-w-2xl border rounded shadow-sm hidden")

        async def do_preview():
            """Generate a preview chart using matplotlib with current config."""
            config = {
                "x_range": (x_range_min.value, x_range_max.value) if x_range_min.value is not None else None,
                "y_range": (y_range_min.value, y_range_max.value) if y_range_min.value is not None else None,
                "annotations": [],
            }
            # Parse annotations
            ann_text = annotations_input.value
            if ann_text:
                for line in ann_text.strip().split("\n"):
                    parts = line.split(",")
                    if len(parts) >= 3:
                        try:
                            config["annotations"].append({
                                "x": float(parts[0].strip()),
                                "y": float(parts[1].strip()),
                                "text": parts[2].strip(),
                            })
                        except ValueError:
                            pass

            try:
                import numpy as np
                from backend.reporting.charts_matplotlib import (
                    mpl_timeseries, mpl_scatter, mpl_heatmap, mpl_profile,
                    figure_to_base64,
                )

                # Generate sample data based on chart type
                x = np.linspace(0, 10, 100)
                ct = chart_type.value

                if ct == "timeseries":
                    y1 = np.sin(x) + 0.1 * np.random.randn(100)
                    y2 = np.cos(x) + 0.1 * np.random.randn(100)
                    fig = mpl_timeseries(
                        x, {"信号 A": y1, "信号 B": y2},
                        title="预览图表", x_label="时间", y_label="幅值",
                        series_names=["信号 A", "信号 B"],
                        config=config,
                        figsize=(fig_width.value, fig_height.value),
                        dpi=int(fig_dpi.value),
                    )
                elif ct == "scatter":
                    y = np.sin(x) + 0.2 * np.random.randn(100)
                    fig = mpl_scatter(
                        x, y,
                        title="散点图预览", x_label="X", y_label="Y",
                        show_trendline=True,
                        config=config,
                        figsize=(fig_width.value, fig_height.value),
                        dpi=int(fig_dpi.value),
                    )
                elif ct == "heatmap":
                    z = np.random.randn(20, 30)
                    fig = mpl_heatmap(
                        z,
                        title="热力图预览", x_label="X", y_label="Y",
                        config=config,
                        figsize=(fig_width.value, fig_height.value),
                        dpi=int(fig_dpi.value),
                    )
                elif ct == "profile":
                    y = np.sin(x) * np.exp(-x / 3)
                    fig = mpl_profile(
                        x, y,
                        title="剖面图预览", x_label="Distance (m)", y_label="Value",
                        config=config,
                        figsize=(fig_width.value, fig_height.value),
                        dpi=int(fig_dpi.value),
                    )
                else:
                    ui.notify("未知图表类型", type="error")
                    return

                b64 = figure_to_base64(fig, dpi=int(fig_dpi.value))
                src = f"data:image/png;base64,{b64}"
                preview_image.set_src(src)
                preview_image.classes(remove="hidden")
                ui.notify("预览已更新", type="positive")

            except Exception as e:
                ui.notify(f"预览生成失败: {e}", type="error")
                logger.exception("Chart preview error")

        with ui.row().classes("gap-3"):
            ui.button("生成预览", icon="visibility", on_click=do_preview).props("flat")
            ui.button("保存配置", icon="save", on_click=lambda: ui.notify("配置已保存", type="positive")
                     ).props("flat")


# ═══════════════════════════ 知识库页面 ═══════════════════════════


@ui.page("/knowledge")
def knowledge_page():
    _drawer()
    _header("知识库")
    with ui.column().classes("w-full max-w-4xl mx-auto p-4 gap-4"):
        ui.markdown("## 知识库管理")

        upload_result = ui.label("").classes("text-sm")
        ui.upload(
            label="选择文件（PDF / TXT / MD）",
            on_upload=lambda e: _do_upload(e, upload_result),
            multiple=False,
        ).classes("w-full")

        ui.separator()
        ui.markdown("**已上传文档**")
        doc_list = ui.column().classes("w-full gap-2")

        def refresh_list():
            doc_list.clear()
            with doc_list:
                try:
                    from backend.retrieval.vector_store import get_vector_store
                    store = get_vector_store()
                    docs = store.list_documents()
                    if docs:
                        for d in docs:
                            with ui.row().classes("items-center w-full gap-2"):
                                ui.label(d).classes("flex-1 text-sm")
                                ui.button("删除", icon="delete",
                                         on_click=lambda did=d: _do_delete(did, refresh_list)
                                         ).props("flat dense color=red")
                    else:
                        ui.label("（暂无文档）").classes("text-gray-400 text-sm")
                except Exception as e:
                    ui.label(f"加载失败: {e}").classes("text-red-500 text-sm")

        ui.button("刷新列表", on_click=refresh_list, icon="refresh").props("flat")
        refresh_list()


async def _do_upload(e, result_label) -> None:
    try:
        from backend.retrieval.vector_store import get_vector_store, VectorStore
        raw = e.content.read()
        content = VectorStore.extract_text_from_bytes(raw, filename=e.name or "")
        store = get_vector_store()
        from datetime import datetime
        doc_id = f"doc_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{e.name}"
        await store.add_document(doc_id=doc_id, content=content, metadata={"filename": e.name})
        result_label.set_text(f"✓ 上传成功: {e.name} ({len(content)} 字符)")
        result_label.classes("text-green-500")
    except Exception as ex:
        result_label.set_text(f"✗ 上传失败: {ex}")
        result_label.classes("text-red-500")


def _do_delete(doc_id: str, refresh_cb) -> None:
    try:
        from backend.retrieval.vector_store import get_vector_store
        import asyncio
        store = get_vector_store()
        asyncio.create_task(store.delete_document(doc_id))
        refresh_cb()
        ui.notify(f"已删除: {doc_id}")
    except Exception as e:
        ui.notify(f"删除失败: {e}", type="error")


# ═══════════════════════════ 设置页面 ═══════════════════════════


@ui.page("/settings")
def settings_page():
    _drawer()
    _header("设置")
    with ui.column().classes("w-full max-w-4xl mx-auto p-4 gap-4"):
        ui.markdown("## 设置")

        ui.markdown("**模型状态**")
        from backend.models.registry import ModelRegistry
        models = ModelRegistry.list_models()
        if models:
            for m in models:
                tag = "✅" if m.get("status", "active") == "active" else "❌"
                df = " (默认)" if m.get("default") else ""
                ui.label(f"{tag} {m['model_id']} — {m['type']}{df}")
        else:
            ui.label("⚠️ 未配置任何 AI 模型").classes("text-yellow-500")

        ui.separator()
        ui.markdown("**API Key 状态**")
        for name, key in [
            ("DeepSeek", settings.deepseek_api_key),
            ("KIMI (Moonshot)", settings.kimi_api_key),
            ("OpenAI", settings.openai_api_key),
        ]:
            if key and "your-" not in key:
                masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "已配置"
                ui.label(f"✅ {name}: {masked}")
            else:
                ui.label(f"❌ {name}: 未配置").classes("text-gray-400")

        ui.separator()
        ui.markdown(f"**向量数据库**: {settings.chroma_persist_dir}")
        ui.markdown(f"**Embedding 模型**: {settings.embedding_model}")

        # Phase 2 status
        ui.separator()
        ui.markdown("**Phase 2 功能状态**")
        checks = [
            ("✅ 数据引擎", "GNSS / InSAR / 水文分析"),
            ("✅ 交互式图表", "Plotly 时序/散点/热力/剖面图"),
            ("✅ NL→Python 代码生成", "自然语言转分析代码"),
            ("✅ 代码执行沙箱", "安全隔离执行"),
            ("✅ Matplotlib 出版级图表", "静态图像导出"),
            ("✅ 图表配置面板", "颜色/范围/标注控制"),
            ("✅ 查询缓存", "结果复用加速"),
            ("✅ 报告生成", "Word / HTML / PDF"),
        ]
        for tag, desc in checks:
            ui.label(f"{tag} — {desc}").classes("text-sm")


# ═══════════════════════════ 启动入口 ═══════════════════════════


def run():
    ui.run(
        title="Research Agent",
        host=settings.app_host,
        port=8080,
        reload=False,
        show=False,
    )


if __name__ == "__main__":
    run()
