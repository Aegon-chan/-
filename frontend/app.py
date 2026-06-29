"""
NiceGUI 前端应用入口

直接调用后端 Python 模块，实现：
- 对话界面 + 流式打字机效果
- 模型切换
- 会话管理
- 知识库 / 设置页面
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Optional

from nicegui import ui

from backend.config import settings

logger = logging.getLogger("research_agent.frontend")

# ───────────────────────────── 页面级状态 ─────────────────────────────

_session_id: str = ""
_current_model: str = "deepseek-chat"


def _ensure_session() -> str:
    """确保有会话 ID"""
    global _session_id
    if not _session_id:
        _session_id = str(uuid.uuid4())
    return _session_id


def _get_agent() -> "ResearchAgent":
    """惰性创建 ResearchAgent（延迟导入避免启动循环）"""
    from backend.core.agent import ResearchAgent
    return ResearchAgent(session_id=_ensure_session(), model_id=_current_model)


def _list_available_models() -> list[str]:
    """获取已注册的模型列表"""
    from backend.models.registry import ModelRegistry
    models = ModelRegistry.list_models()
    llms = [m["model_id"] for m in models if m["type"] == "llm"]
    return llms if llms else ["（无可用模型）"]


# ═══════════════════════════ 对话页面 ═══════════════════════════


@ui.page("/")
def chat_page():
    """主页面：对话界面"""
    global _current_model

    # ── 左导航抽屉 ──────────────────────────────────────────
    with ui.left_drawer().classes("bg-gray-100 dark:bg-gray-800"):
        ui.label("导航").classes("text-lg font-bold p-4")
        with ui.column().classes("p-2 gap-2"):
            ui.button("对话", on_click=lambda: ui.navigate.to("/")
                     ).props("flat icon=chat")
            ui.button("知识库", on_click=lambda: ui.navigate.to("/knowledge")
                     ).props("flat icon=library_books")
            ui.button("设置", on_click=lambda: ui.navigate.to("/settings")
                     ).props("flat icon=settings")

    # ── 顶栏 ────────────────────────────────────────────────
    available = _list_available_models()
    has_model = available != ["（无可用模型）"]

    with ui.header(elevated=True).classes("items-center justify-between"):
        ui.label("Research Agent").classes("text-lg font-bold")
        ui.select(
            label="模型",
            options={m: m for m in available},
            value=_current_model if _current_model in available else available[0],
            on_change=lambda e: setattr(globals(), "_current_model", e.value),
        ).classes("w-52").props("outlined dense")

    # ── 对话区域 ────────────────────────────────────────────
    chat_area = ui.column().classes(
        "w-full max-w-4xl mx-auto p-4 gap-2 flex-1 overflow-y-auto"
    )

    # ── 输入栏（底部固定） ──────────────────────────────────
    with ui.row().classes(
        "w-full items-center gap-2 sticky bottom-0 "
        "bg-white dark:bg-gray-900 p-3 border-t"
    ):
        input_field = ui.input(
            placeholder="输入你的问题，按 Enter 发送..."
        ).classes("flex-1").props("clearable autofocus")
        send_btn = ui.button("发送", icon="send").props("flat")

        # ── 发送逻辑 ────────────────────────────────────────────
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

    # ── 欢迎消息 ────────────────────────────────────────────
    with chat_area:
        if not has_model:
            ui.markdown(
                "## 欢迎使用 Research Agent\n\n"
                "⚠️ **未检测到已配置的 AI 模型**\n\n"
                "请在 `.env` 文件中配置至少一个 API Key（DeepSeek / KIMI / OpenAI），"
                "然后重启服务。\n\n"
                "或前往「设置」页面查看当前配置。"
            )
        else:
            ui.markdown(
                "## 欢迎使用 Research Agent 🧪\n\n"
                "我是你的科研数据分析助手，支持：\n\n"
                "- 📡 **GNSS / InSAR / 水文监测** 数据分析\n"
                "- 📚 **知识库检索** 增强回答\n"
                "- 🤖 **多模型切换**（DeepSeek / KIMI）\n\n"
                "在下方输入问题开始对话。"
            )


def _scroll_bottom() -> None:
    """滚动到页面底部"""
    ui.run_javascript("setTimeout(() => window.scrollTo(0,document.body.scrollHeight), 50)")


# ═══════════════════════════ 知识库页面 ═══════════════════════════


@ui.page("/knowledge")
def knowledge_page():
    """知识库管理页面"""
    with ui.header(elevated=True).classes("items-center justify-between"):
        ui.label("知识库").classes("text-lg font-bold")
        ui.button("返回对话", on_click=lambda: ui.navigate.to("/")).props("flat")

    with ui.column().classes("w-full max-w-4xl mx-auto p-4 gap-4"):
        ui.markdown("## 知识库管理")

        # 上传区域
        ui.markdown("**上传文档**（PDF / TXT / MD）")
        upload_result = ui.label("").classes("text-sm")
        ui.upload(
            label="选择文件",
            on_upload=lambda e: _do_upload(e, upload_result),
            multiple=False,
        ).classes("w-full")

        # 文档列表
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
    """处理文件上传"""
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
    """删除文档"""
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
    """设置页面"""
    with ui.header(elevated=True).classes("items-center justify-between"):
        ui.label("设置").classes("text-lg font-bold")
        ui.button("返回对话", on_click=lambda: ui.navigate.to("/")).props("flat")

    with ui.column().classes("w-full max-w-4xl mx-auto p-4 gap-4"):
        ui.markdown("## 设置")

        # 模型状态
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

        # 环境变量预览（不显示完整 key）
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
        ui.markdown(f"**版本**: 0.1.0-dev")


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
