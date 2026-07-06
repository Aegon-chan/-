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
import os
import json
import logging
import uuid
from datetime import datetime
from typing import Optional
from pathlib import Path

import requests

from nicegui import app as nicegui_app, ui

from backend.config import settings

logger = logging.getLogger("research_agent.frontend")

# ── Layout CSS injected once ──
_LAYOUT_CSS = """
<style>
.full-height-container { display: flex; flex-direction: column; height: calc(100vh - 64px); }
.chat-messages-area { flex: 1 1 auto; overflow-y: auto; min-height: 0; }
.chat-input-bar { flex: 0 0 auto; position: relative; }
.chat-messages-area::-webkit-scrollbar { width: 6px; }
.chat-messages-area::-webkit-scrollbar-thumb { background: #ccc; border-radius: 4px; }
.chat-messages-area::-webkit-scrollbar-thumb:hover { background: #aaa; }
/* Drag-and-drop overlay */
.chat-input-bar.drag-over {
    border: 2px dashed #4a9eff !important;
    background-color: rgba(74, 158, 255, 0.06) !important;
    border-radius: 10px !important;
}
.drop-indicator {
    display: none;
    text-align: center;
    padding: 10px 16px;
    color: #4a9eff;
    font-size: 14px;
    font-weight: 500;
    border: 2px dashed #4a9eff;
    border-radius: 8px;
    margin-bottom: 8px;
    background-color: rgba(74, 158, 255, 0.05);
    transition: all 0.2s ease;
}
.chat-input-bar.drag-over .drop-indicator {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
}
@media (max-width: 600px) { .q-drawer { width: 260px !important; } }
</style>
"""

_injected_css = False

def _ensure_layout_css():
    global _injected_css
    if not _injected_css:
        ui.add_head_html(_LAYOUT_CSS)
        _injected_css = True


# ───────────────────────────── 全局状态 ─────────────────────────────


# -- Local persistent store (survives page reload without backend) --
_LOCAL_STORE_PATH = os.path.join("data", "local_sessions.json")

def _load_local_store() -> dict:
    try:
        if os.path.exists(_LOCAL_STORE_PATH):
            with open(_LOCAL_STORE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning("Failed to load local store: %s", e)
    return {"sessions": {}, "messages": {}}

def _save_local_store(data: dict) -> None:
    try:
        os.makedirs(os.path.dirname(_LOCAL_STORE_PATH) or ".", exist_ok=True)
        with open(_LOCAL_STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning("Failed to save local store: %s", e)

def _load_local_messages(session_id: str) -> list:
    store = _load_local_store()
    return store.get("messages", {}).get(session_id, [])

def _save_messages_locally(session_id: str, messages: list) -> None:
    store = _load_local_store()
    existing = store["messages"].get(session_id, [])
    existing.extend(messages)
    store["messages"][session_id] = existing
    _save_local_store(store)

def _save_sessions_locally(sessions_list: list) -> None:
    offline = [s for s in sessions_list if s.get("offline")]
    if not offline:
        return
    store = _load_local_store()
    existing_ids = set(store.get("sessions", {}).keys())
    for s in offline:
        sid = s.get("id")
        if sid and sid not in existing_ids:
            store["sessions"][sid] = s
    _save_local_store(store)

def _load_local_sessions() -> list:
    store = _load_local_store()
    return list(store.get("sessions", {}).values())

def _remove_local_session(sid: str) -> None:
    store = _load_local_store()
    store["sessions"].pop(sid, None)
    store["messages"].pop(sid, None)
    _save_local_store(store)

_session_id: str = ""
_user_id: str = "default"
_current_model: str = "deepseek-chat"
_nl2query_history: list[dict] = []
# Session management globals
_sessions: list[dict] = []
_current_session_id: str = ""
_agents: dict = {}
_pending_attachments: list[dict] = []
_BACKEND_URL = "http://localhost:8000"
_session_refreshing: bool = False


def _ensure_session() -> str:
    global _session_id
    if not _session_id:
        _session_id = str(uuid.uuid4())
    return _session_id


def _get_agent():
    """Get or create the ResearchAgent for the current session, with history.

    Reuses the agent if it already exists in _agents (same session, same model),
    loads historical messages from the backend API for a new agent.
    """
    sid = _ensure_session()
    # Reuse existing agent if model hasn't changed
    if sid in _agents and _agents[sid].model_id == _current_model:
        return _agents[sid]
    # Create new agent
    from backend.core.agent import ResearchAgent
    agent = ResearchAgent(session_id=sid, model_id=_current_model, user_id=_user_id)
    # Load history from backend
    try:
        resp = requests.get(f"{_BACKEND_URL}/api/v1/sessions/{sid}", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            history = data.get("messages", [])
            agent.load_history(history)
    except Exception as e:
        logger.warning("Failed to load session history: %s", e)
    _agents[sid] = agent
    return agent


def _list_available_models() -> list[str]:
    from backend.models.registry import ModelRegistry
    models = ModelRegistry.list_models()
    llms = [m["model_id"] for m in models if m["type"] == "llm"]
    return llms if llms else ["（无可用模型）"]

# ---- Session management ----

def _refresh_sessions():
    """Fetch session list from backend API, merged with local offline sessions."""
    global _sessions, _session_refreshing
    if _session_refreshing:
        return
    _session_refreshing = True
    try:
        resp = requests.get(f"{_BACKEND_URL}/api/v1/sessions/", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            _sessions = data.get("sessions", [])
    except Exception as e:
        logger.warning("Failed to fetch sessions: %s", e)
    finally:
        # Merge in local sessions that the backend doesnt know about
        local_sessions = _load_local_sessions()
        existing_ids = {s.get("id") for s in _sessions}
        for ls in local_sessions:
            sid = ls.get("id")
            if sid and sid not in existing_ids:
                _sessions.append(ls)
        _session_refreshing = False


def _create_session() -> bool:
    """Create a new session via API (with local fallback) and switch to it."""
    global _session_id, _current_session_id, _sessions
    try:
        resp = requests.post(
            f"{_BACKEND_URL}/api/v1/sessions/",
            json={"user_id": _user_id, "title": "新对话", "model_id": _current_model},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            _session_id = data["id"]
            _current_session_id = data["id"]
            from backend.core.agent import ResearchAgent
            _agents[_session_id] = ResearchAgent(
                session_id=_session_id, model_id=_current_model, user_id=_user_id
            )
            _refresh_sessions()
            return True
    except Exception as e:
        logger.warning("Failed to create session via API: %s", e)

    # Local fallback: create offline session and persist it
    local_id = str(uuid.uuid4())
    _session_id = local_id
    _current_session_id = local_id
    from backend.core.agent import ResearchAgent
    _agents[local_id] = ResearchAgent(
        session_id=local_id, model_id=_current_model, user_id=_user_id
    )
    now_ts = datetime.now().isoformat()
    session_entry = {"id": local_id, "title": "新对话", "message_count": 0,
                     "model_id": _current_model, "offline": True,
                     "created_at": now_ts, "updated_at": now_ts}
    _sessions.insert(0, session_entry)
    _save_sessions_locally(_sessions)
    return True


_pending_chat_session: str = ""


def _load_and_display_messages(chat_area, loading_label=None):
    """Load messages for current session (backend first, then local fallback)."""
    if not _current_session_id:
        return
    msgs = []
    loaded_from = "local"
    # Try backend first
    try:
        resp = requests.get(f"{_BACKEND_URL}/api/v1/sessions/{_current_session_id}", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            msgs = data.get("messages", [])
            loaded_from = "backend"
    except Exception as e:
        logger.warning("Failed to load messages from backend: %s", e)
    # Fall back to local store if backend failed or returned empty
    if not msgs:
        msgs = _load_local_messages(_current_session_id)
        if msgs:
            loaded_from = "local"
    # Render messages
    for msg in msgs:
        role = msg.get("role", "")
        content = msg.get("content", "")
        metadata = msg.get("metadata", {}) or {}
        if role == "user":
            with chat_area:
                with ui.chat_message("", name="你", sent=True):
                    attachments = metadata.get("attachments", [])
                    for att in attachments:
                        if att.get("mime_type", "").startswith("image/"):
                            img_url = f"{_BACKEND_URL}{att['url']}" if att.get("url", "").startswith("/") else att["url"]
                            ui.image(img_url).classes("max-w-xs rounded mb-1")
                        else:
                            file_url = f"{_BACKEND_URL}{att['url']}" if att.get("url", "").startswith("/") else att["url"]
                            ui.link(att["filename"], file_url).classes("text-sm block mb-1")
                    ui.markdown(content)
        elif role == "assistant":
            with chat_area:
                ui.chat_message(content, name="助手", sent=False)
    logger.info("Loaded %d messages from %s for session %s", len(msgs), loaded_from, _current_session_id)
    if loading_label is not None:
        try:
            loading_label.set_text("")
            loading_label.classes(add="hidden")
        except Exception:
            pass


def _navigate_to_session(sid):
    """Switch session and navigate to chat page"""
    _switch_session(sid)
    ui.navigate.to("/")


def _switch_session(sid):
    """Switch to an existing session, preloading agent with stored history."""
    global _session_id, _current_session_id
    if sid == _current_session_id:
        return
    _session_id = sid
    _current_session_id = sid
    if sid not in _agents:
        from backend.core.agent import ResearchAgent
        agent = ResearchAgent(
            session_id=sid, model_id=_current_model, user_id=_user_id
        )
        # Preload local messages into agent history
        local_msgs = _load_local_messages(sid)
        if local_msgs:
            agent.load_history(local_msgs)
        _agents[sid] = agent
    _refresh_sessions()


def _delete_session(sid):
    """Delete a session (via API or local fallback) and persist the change."""
    global _session_id, _current_session_id, _sessions
    try:
        resp = requests.delete(f"{_BACKEND_URL}/api/v1/sessions/{sid}", timeout=10)
        if resp.status_code == 200:
            _agents.pop(sid, None)
            if _current_session_id == sid:
                _session_id = ""
                _current_session_id = ""
            _refresh_sessions()
            return True
    except Exception as e:
        logger.warning("Failed to delete session: %s", e)
    # Local delete
    _agents.pop(sid, None)
    _sessions = [s for s in _sessions if s.get("id") != sid]
    if _current_session_id == sid:
        _session_id = ""
        _current_session_id = ""
    # Also remove from local persistent store
    _remove_local_session(sid)
    return True


def _persist_messages(session_id, messages):
    """Save messages locally first, then try backend API as sync."""
    if not session_id or not messages:
        return
    # Always save locally first (ensures messages survive page reload)
    _save_messages_locally(session_id, messages)
    # Update message count in local store
    store = _load_local_store()
    for s in store.get("sessions", {}).values():
        if s.get("id") == session_id:
            s["message_count"] = s.get("message_count", 0) + len(messages)
            s["updated_at"] = datetime.now().isoformat()
            break
    _save_local_store(store)
    # Also update in-memory session entry
    for s in _sessions:
        if s.get("id") == session_id:
            s["message_count"] = s.get("message_count", 0) + len(messages)
            break
    # Try backend sync (best effort)
    try:
        requests.post(
            f"{_BACKEND_URL}/api/v1/sessions/{session_id}/messages",
            json={"messages": messages},
            timeout=10,
        )
    except Exception as e:
        logger.warning("Failed to sync messages to backend: %s", e)


# ---- Chat logging ----

def _log_chat(user_input, response, model, duration_ms):
    log_dir = os.path.join("data", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "chat_" + datetime.now().strftime("%Y%m%d") + ".log")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write("[" + datetime.now().isoformat() + "] model=" + model + "\n")
        f.write("  Q: " + str(user_input)[:200] + "\n")
        f.write("  A: " + str(response)[:500] + "\n")
        f.write("  duration: %.0fms\n\n" % duration_ms)

def _log_usage(event_type, detail=""):
    log_dir = os.path.join("data", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "usage.log")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write("[" + datetime.now().isoformat() + "] " + str(event_type) + " | " + str(detail) + "\n")

# ---- User config persistence ----
_USER_CONFIG_PATH = os.path.join("data", "user_config.json")

def _load_user_config():
    import json
    try:
        if os.path.exists(_USER_CONFIG_PATH):
            with open(_USER_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_user_config(config):
    import json
    os.makedirs(os.path.dirname(_USER_CONFIG_PATH), exist_ok=True)
    with open(_USER_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def _apply_user_config():
    config = _load_user_config()
    keys_map = {
        "deepseek_key": "DEEPSEEK_API_KEY",
        "kimi_key": "KIMI_API_KEY",
        "openai_key": "OPENAI_API_KEY",
    }
    changed = False
    for cfg_key, env_key in keys_map.items():
        val = config.get(cfg_key, "")
        if val and val != os.environ.get(env_key, ""):
            os.environ[env_key] = val
            changed = True
    if changed:
        from backend.config import settings
        settings.deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        settings.kimi_api_key = os.environ.get("KIMI_API_KEY", "")
        settings.openai_api_key = os.environ.get("OPENAI_API_KEY", "")

def _check_api_keys():
    from backend.models.registry import ModelRegistry
    models = ModelRegistry.list_models()
    configured = []
    for m in models:
        if m["type"] == "llm" and m.get("status", "active") == "active":
            configured.append(m["model_id"])
    if not configured:
        from backend.config import settings
        if settings.deepseek_api_key and "your-" not in settings.deepseek_api_key:
            configured.append("deepseek-chat")
        if settings.kimi_api_key and "your-" not in settings.kimi_api_key:
            configured.append("moonshot-v1")
        if settings.openai_api_key and "your-" not in settings.openai_api_key:
            configured.append("gpt-4o")
    return configured

# Apply user config on startup (overrides .env)
_apply_user_config()
from backend.models import init_models
init_models()



# ═══════════════════════════ 反馈助手 ═══════════════════════════


def _submit_feedback(rating, label, up_btn, down_btn, status_label):
    """提交对话消息反馈（点赞/点踩）"""
    import requests
    try:
        resp = requests.post(
            "http://localhost:8000/api/v1/feedback/collect",
            params={
                "message_id": _ensure_session(),
                "rating": rating,
                "user_id": _user_id,
                "session_id": _session_id,
            },
            timeout=5,
        )
        if resp.status_code == 200:
            if rating > 0:
                status_label.set_text("✓ 已赞")
                up_btn.props("color=green")
                down_btn.props("color=grey")
            else:
                status_label.set_text("✓ 已踩")
                down_btn.props("color=red")
                up_btn.props("color=grey")
    except Exception:
        status_label.set_text("反馈提交失败")


# ═══════════════════════════ 导航栏 ═══════════════════════════


def _drawer():
    with ui.left_drawer(fixed=True).classes("bg-gray-100 dark:bg-gray-800"):
        with ui.column().classes("w-full h-full justify-between"):
            # Top: sessions (scrollable)
            with ui.column().classes("w-full overflow-y-auto flex-1"):
                ui.label("Sessions").classes("text-lg font-bold px-3 pt-3 pb-1")
                ui.button("New", icon="add",
                    on_click=lambda: _create_session() if not _session_refreshing else None
                ).props("flat color=primary").classes("w-[calc(100%-16px)] mx-2 mb-1")
                _render_session_list()
            # Bottom: navigation
            ui.separator()
            with ui.column().classes("w-full px-2 pb-2 gap-0"):
                ui.label("Navigate").classes("text-lg font-bold px-2 pt-1 pb-1")
                nav_items = [
                    ("Chat", "/", "chat"),
                    ("NL2Query", "/nl2query", "code"),
                    ("Charts", "/chart-studio", "bar_chart"),
                    ("Knowledge", "/knowledge", "library_books"),
                    ("Memory", "/memories", "psychology"),
                    ("Settings", "/settings", "settings"),
                ]
                for label, path, icon in nav_items:
                    ui.button(label, icon=icon, on_click=lambda p=path: ui.navigate.to(p)
                             ).props("flat").classes("w-full justify-start")

@ui.refreshable
def _render_session_list():
    if not _sessions:
        ui.label("（暂无对话）").classes("text-gray-400 text-sm px-2")
        return
    for s in _sessions:
        sid = s.get("id", "")
        title = s.get("title", "对话")
        msg_count = s.get("message_count", 0)
        is_active = sid == _current_session_id
        css = "bg-blue-100 dark:bg-blue-900 rounded" if is_active else ""
        with ui.row().classes(f"items-center w-full px-2 py-1 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-700 {css}").on("click", lambda sid=sid: _navigate_to_session(sid)):
            ui.icon("chat").props("size=16px").classes("text-gray-500 shrink-0")
            ui.label(title[:20]).classes("text-sm truncate flex-1")
            if msg_count > 0:
                ui.label(str(msg_count)).classes("text-xs text-gray-400 shrink-0")
            ui.button(icon="delete",
                      on_click=lambda e, sid=sid: (_delete_session(sid), _render_session_list.refresh())
                      ).props("flat dense round size=sm color=grey").classes("opacity-60 hover:opacity-100 shrink-0")


def _header(title="Research Agent"):
    available = _list_available_models()
    with ui.header(elevated=True).classes("items-center justify-between"):
        with ui.row().classes("items-center gap-2"):
            ui.button(icon="menu", on_click=lambda: nicegui_app.toggle_left_drawer()
                     ).props("flat dense round").classes("lg:hidden")
            ui.label(title).classes("text-lg font-bold")
        ui.select(
            label="Model",
            options={m: m for m in available},
            value=_current_model if _current_model in available else available[0],
            on_change=lambda e: setattr(globals(), "_current_model", e.value),
        ).classes("w-52").props("outlined dense")

def _scroll_bottom() -> None:
    ui.run_javascript("""
        var el = document.querySelector(".chat-messages-area");
        if (el) { el.scrollTop = el.scrollHeight; }
        else { window.scrollTo(0, document.body.scrollHeight); }
    """)



# ═══════════════════════════ 对话页面 ═══════════════════════════


@ui.page("/")
def chat_page():
    """Chat page with file upload and session support"""
    _ensure_layout_css()
    _drawer()
    _header()


    # Inject custom CSS for drag-and-drop visual feedback
    ui.add_body_html('''<style>
.chat-input-bar.drag-over {
    border: 2px dashed #4a9eff !important;
    background-color: rgba(74, 158, 255, 0.06) !important;
    border-radius: 10px !important;
}
.drop-indicator {
    display: none;
    text-align: center;
    padding: 10px 16px;
    color: #4a9eff;
    font-size: 14px;
    font-weight: 500;
    border: 2px dashed #4a9eff;
    border-radius: 8px;
    margin-bottom: 8px;
    background-color: rgba(74, 158, 255, 0.05);
}
.chat-input-bar.drag-over .drop-indicator {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
}
</style>''')

    # Inject drag-and-drop JavaScript
    ui.add_body_html('''<script>
// Drag-and-drop file upload handler
window.__dropResults = [];
window._backendUrl = 'http://localhost:8000/api/v1';

document.addEventListener('DOMContentLoaded', function() {
    let dragCounter = 0;
    const body = document.body;
    body.addEventListener('dragenter', function(e) {
        const types = e.dataTransfer.types;
        if (!types) return;
        if (!Array.from(types).includes('Files')) return;
        dragCounter++;
        if (dragCounter === 1) {
            document.querySelectorAll('.chat-input-bar').forEach(function(el) {
                el.classList.add('drag-over');
            });
        }
    });
    body.addEventListener('dragover', function(e) {
        const types = e.dataTransfer.types;
        if (!types) return;
        if (!Array.from(types).includes('Files')) return;
        e.preventDefault();
        e.stopPropagation();
    });
    body.addEventListener('dragleave', function(e) {
        dragCounter--;
        if (dragCounter <= 0) {
            dragCounter = 0;
            document.querySelectorAll('.chat-input-bar').forEach(function(el) {
                el.classList.remove('drag-over');
            });
        }
    });
    body.addEventListener('drop', function(e) {
        e.preventDefault();
        e.stopPropagation();
        dragCounter = 0;
        document.querySelectorAll('.chat-input-bar').forEach(function(el) {
            el.classList.remove('drag-over');
        });
        var inputBar = e.target.closest('.chat-input-bar');
        if (!inputBar) return;
        var files = e.dataTransfer.files;
        if (!files || files.length === 0) return;
        Array.from(files).forEach(function(file) {
            var formData = new FormData();
            formData.append('file', file, file.name);
            fetch(window._backendUrl + '/upload/upload', { method: 'POST', body: formData })
                .then(function(r) {
                    if (!r.ok) { throw new Error('HTTP ' + r.status); }
                    return r.json();
                })
                .then(function(data) { window.__dropResults.push(data); })
                .catch(function(err) {
                    console.error('Drop upload failed:', err);
                    if (!window.__dropErrors) window.__dropErrors = [];
                    window.__dropErrors.push({error: (err.message || String(err)), filename: file.name});
                });
        });
    });
});
</script>''')

    has_model = _list_available_models() != ["No model available"]

    with ui.column().classes("full-height-container w-full"):
        with ui.column().classes("chat-messages-area w-full px-4"):
            chat_area = ui.column().classes("w-full max-w-4xl mx-auto gap-3 py-2")

            if not has_model:
                with chat_area:
                    ui.markdown(
                        "## Welcome to Research Agent\n\n"
                        "Configure API Key in `.env` and restart."
                    )
            else:
                with chat_area:
                    ui.markdown(
                        "## Welcome to Research Agent\n\n"
                        "I am your research data analysis assistant, supporting:"
                        "\n\n- **Chat**: Natural language Q&A\n"
                        "- **NL2Query**: Natural language to Python code\n"
                        "- **Charts**: Custom chart styling\n"
                        "- **Knowledge**: Document upload & retrieval\n\n"
                        "Type your question below or explore features via the sidebar."
                    )
            # Feedback row (hidden, placed in chat_area)
            fb_row = ui.row().classes("items-center gap-1 ml-12 hidden")
            fb_status = ui.label("").classes("text-xs text-gray-400")
            fb_up = ui.button(icon="thumb_up", on_click=lambda: _submit_feedback(1, "up", fb_up, fb_down, fb_status)
                ).props("flat dense round size=sm color=green")
            fb_down = ui.button(icon="thumb_down", on_click=lambda: _submit_feedback(-1, "down", fb_up, fb_down, fb_status)
                ).props("flat dense round size=sm color=red")

        with ui.column().classes("chat-input-bar w-full bg-white dark:bg-gray-900 px-3 py-2"):
            preview_container = ui.row().classes("w-full gap-2 flex-wrap hidden")
            drop_indicator = ui.label("  Drop files here to upload").classes("drop-indicator")

            with ui.row().classes("w-full items-center gap-2 max-w-4xl mx-auto"):

                async def _on_upload(e):
                    try:
                        file_content = await e.file.read()
                        file_name = e.file.name or "file"
                        resp = requests.post(
                            f"{_BACKEND_URL}/api/v1/upload/upload",
                            files={"file": (file_name, file_content)},
                            timeout=30,
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            _pending_attachments.append(data)
                            with preview_container:
                                with ui.row().classes("items-center gap-1 bg-gray-100 dark:bg-gray-800 rounded px-2 py-1"):
                                    if data.get("mime_type", "").startswith("image/"):
                                        img_url = f"{_BACKEND_URL}{data.get("url", "")}" if data.get("url", "").startswith("/") else data.get("url", "")
                                        ui.image(img_url).classes("w-8 h-8 rounded object-cover")
                                    else:
                                        ui.icon("description").props("size=20px").classes("text-gray-500")
                                    ui.label(file_name[:15]).classes("text-xs truncate max-w-24")
                                    ui.button(icon="close", on_click=lambda d=data: (
                                        _pending_attachments.remove(d) if d in _pending_attachments else None,
                                        preview_container.clear(),
                                        preview_container.classes(add="hidden"),
                                    )).props("flat dense round size=xs").classes("text-gray-400")
                            preview_container.classes(remove="hidden")
                            ui.notify(f"Uploaded: {file_name}", type="positive")
                    except Exception as ex:
                        ui.notify(f"Upload failed: {ex}", type="negative")

                ui.upload(label="", on_upload=_on_upload, multiple=False
                    ).props("flat dense round icon=attach_file").classes("shrink-0")

                input_field = ui.input(
                    placeholder="Type your question, press Enter to send..."
                ).classes("flex-1").props("clearable autofocus")
                send_btn = ui.button("Send", icon="send").props("flat")



        async def do_send():
            text = input_field.value
            if not text or not has_model:
                return
            input_field.value = ""
            send_btn.disable()
            input_field.disable()

            attachments = list(_pending_attachments)
            _pending_attachments.clear()
            preview_container.clear()
            preview_container.classes(add="hidden")

            metadata = {"attachments": attachments} if attachments else {}

            with chat_area:
                with ui.chat_message("", name="You", sent=True):
                    if attachments:
                        for att in attachments:
                            if att.get("mime_type", "").startswith("image/"):
                                img_url = f"{_BACKEND_URL}{att["url"]}" if att["url"].startswith("/") else att["url"]
                                ui.image(img_url).classes("max-w-xs rounded mb-1")
                            else:
                                file_url = f"{_BACKEND_URL}{att["url"]}" if att["url"].startswith("/") else att["url"]
                                ui.link(att["filename"], file_url).classes("text-sm block mb-1")
                    ui.markdown(text)

            with chat_area:
                bubble = ui.chat_message("", name="Assistant", sent=False)

            full = ""
            try:
                agent = _get_agent()
                async for token in agent.stream_chat(text, attachments=attachments if attachments else None):
                    full += token
                    bubble.clear()
                    with bubble:
                        ui.markdown(full)
            except ValueError as e:
                bubble.clear()
                with bubble:
                    ui.markdown(f"Config Error: {e}")
            except Exception as e:
                bubble.clear()
                with bubble:
                    ui.markdown(f"Error: {e}")
                    logger.exception("Chat error")
            finally:
                msgs = []
                user_content = text
                if text:
                    msgs.append({"role": "user", "content": user_content, "metadata": metadata})
                if full:
                    msgs.append({"role": "assistant", "content": full})
                if msgs and _current_session_id:
                    _persist_messages(_current_session_id, msgs)
                try:
                    fb_row.classes(remove="hidden")
                except Exception:
                    pass
                input_field.enable()
                send_btn.enable()
                _scroll_bottom()

        send_btn.on_click(do_send)
        input_field.on("keydown.enter", do_send)

    # Polling timer for detecting files dropped via JS drag-and-drop
    async def _check_drop_results():
        try:
            result_json = await ui.run_javascript(
                "JSON.stringify(window.__dropResults || [])",
                respond=True,
                timeout=3.0
            )
            # Check for JS-side upload errors
            err_json = await ui.run_javascript(
                "JSON.stringify(window.__dropErrors || [])",
                respond=True,
                timeout=2.0
            )
            if err_json and err_json != "[]":
                import json as _json
                errs = _json.loads(err_json)
                for err_data in errs:
                    err_msg = err_data.get("error", "Unknown error")
                    err_fn = err_data.get("filename", "file")
                    ui.notify(f"Cannot upload {err_fn}: {err_msg}", type="negative")
                await ui.run_javascript("window.__dropErrors = []")
            if result_json and result_json != "[]":
                import json as _json
                results = _json.loads(result_json)
                for data in results:
                    _pending_attachments.append(data)
                    # Show in preview
                    with preview_container:
                        with ui.row().classes("items-center gap-1 bg-gray-100 dark:bg-gray-800 rounded px-2 py-1"):
                            mime = data.get("mime_type", "")
                            if mime.startswith("image/"):
                                img_url = f"{_BACKEND_URL}{data['url']}" if data["url"].startswith("/") else data["url"]
                                ui.image(img_url).classes("w-8 h-8 rounded object-cover")
                            else:
                                ui.icon("description").props("size=20px").classes("text-gray-500")
                            ui.label(data.get("filename", "file")[:15]).classes("text-xs truncate max-w-24")
                            ui.button(icon="close", on_click=lambda d=data: (
                                _pending_attachments.remove(d) if d in _pending_attachments else None,
                                preview_container.clear(),
                                preview_container.classes(add="hidden"),
                            )).props("flat dense round size=xs").classes("text-gray-400")
                    preview_container.classes(remove="hidden")
                    ui.notify(f"Uploaded: {data.get('filename', 'file')}", type="positive")
                await ui.run_javascript("window.__dropResults = []")
        except Exception as ex:
            import logging
            logging.getLogger("research_agent.frontend").warning("Drop check error: %s", ex)

    ui.timer(0.6, _check_drop_results)

    # Initialize session (outside any with block to avoid parent-slot issues)
    def _init_session_sync():
        """Initialize session: load local sessions, create if needed, load messages.

        Also loads messages when returning to chat page with an existing session.
        """
        if not _current_session_id:
            _refresh_sessions()
            if _sessions:
                _switch_session(_sessions[0].get("id", ""))
            if not _current_session_id:
                _create_session()
        if _current_session_id:
            _load_and_display_messages(chat_area, None)
        try:
            _render_session_list.refresh()
        except Exception:
            pass
    ui.timer(0.5, _init_session_sync, once=True)

@ui.page("/nl2query")
def nl2query_page():
    _ensure_layout_css()
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
    _ensure_layout_css()
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
            fig_width = ui.label("宽度 (英寸)").classes("text-sm")
            fig_width = ui.slider(min=4, max=12, value=7, step=0.5)
            fig_height = ui.label("高度 (英寸)").classes("text-sm")
            fig_height = ui.slider(min=3, max=9, value=4.2, step=0.5)
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
    _ensure_layout_css()
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
        raw = await e.file.read()
        content = VectorStore.extract_text_from_bytes(raw, filename=e.file.name or "")
        store = get_vector_store()
        from datetime import datetime
        doc_id = f"doc_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{e.file.name}"
        await store.add_document(doc_id=doc_id, content=content, metadata={"filename": e.file.name})
        result_label.set_text(f"✓ 上传成功: {e.file.name} ({len(content)} 字符)")
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
@ui.page("/settings")
def settings_page():
    _ensure_layout_css()
    _drawer()
    _header("设置")
    with ui.column().classes("w-full max-w-4xl mx-auto p-4 gap-6"):
        # API Key 配置
        with ui.card().classes("w-full gap-3 p-4"):
            ui.markdown("## API Key 配置")
            ui.label("在此输入 API Key，配置后无需重启即可生效").classes("text-sm text-gray-500")

            deepseek_input = ui.input(
                label="DeepSeek API Key",
                value=_load_user_config().get("deepseek_key", ""),
                password=True,
            ).classes("w-full").props("clearable")
            kimi_input = ui.input(
                label="Kimi API Key",
                value=_load_user_config().get("kimi_key", ""),
                password=True,
            ).classes("w-full").props("clearable")
            openai_input = ui.input(
                label="OpenAI API Key",
                value=_load_user_config().get("openai_key", ""),
                password=True,
            ).classes("w-full").props("clearable")

            config_status = ui.label("").classes("text-sm")
            test_status = ui.label("").classes("text-sm")

            def do_save_keys():
                cfg = {}
                if deepseek_input.value:
                    cfg["deepseek_key"] = deepseek_input.value.strip()
                if kimi_input.value:
                    cfg["kimi_key"] = kimi_input.value.strip()
                if openai_input.value:
                    cfg["openai_key"] = openai_input.value.strip()
                _save_user_config(cfg)
                _apply_user_config()
                from backend.models import init_models
                init_models()
                config_status.set_text("保存成功")
                config_status.classes("text-green-500")

            def do_test_connection():
                _apply_user_config()
                from backend.models import init_models
                init_models()
                from backend.models.registry import ModelRegistry
                llm = ModelRegistry.get_llm_with_fallback()
                if llm is None:
                    test_status.set_text("连接失败: 无可用模型")
                    test_status.classes("text-red-500")
                    return
                import asyncio
                async def _test():
                    try:
                        from backend.models.base import Message
                        resp = await llm.chat([Message(role="user", content="ping")], max_tokens=10)
                        test_status.set_text("连接成功: " + resp.content[:50])
                        test_status.classes("text-green-500")
                    except Exception as e:
                        test_status.set_text("连接失败: " + str(e))
                        test_status.classes("text-red-500")
                asyncio.create_task(_test())

            with ui.row().classes("gap-3"):
                ui.button("保存配置", icon="save", on_click=do_save_keys).props("flat color=primary")
                ui.button("测试连接", icon="wifi", on_click=do_test_connection).props("flat color=secondary")

        # 模型状态
        with ui.card().classes("w-full gap-2 p-4"):
            ui.markdown("## 模型状态")
            from backend.models.registry import ModelRegistry
            models = ModelRegistry.list_models()
            if models:
                for m in models:
                    tag = chr(10003) if m.get("status", "active") == "active" else chr(10007)
                    df = " (默认)" if m.get("default") else ""
                    ui.label(tag + " " + m["model_id"] + " - " + m["type"] + df)
            else:
                ui.label("请在上方填写 API Key 后保存").classes("text-yellow-500")

        # 反馈概览
        with ui.card().classes("w-full gap-2 p-4"):
            ui.markdown("## 反馈概览")
            fb_stats = {}
            try:
                agent = _get_agent()
                fb_stats = agent.feedback_collector.get_stats()
            except Exception:
                pass
            if fb_stats:
                pos = fb_stats.get("positive_count", 0)
                neg = fb_stats.get("negative_count", 0)
                total = fb_stats.get("total_count", 0)
                rate = (pos / total * 100) if total > 0 else 0
                ui.label("好评: " + str(pos) + " | 差评: " + str(neg) + " | 好评率: " + str(int(rate)) + "%" + " | 共 " + str(total) + " 条反馈").classes("text-sm")
            else:
                ui.label("暂无反馈数据").classes("text-sm text-gray-400")

        # 系统信息
        with ui.card().classes("w-full gap-2 p-4"):
            ui.markdown("## 系统信息")
            from backend.config import settings
            ui.label("向量数据库: " + str(settings.chroma_persist_dir)).classes("text-sm")
            ui.label("Embedding 模型: " + str(settings.embedding_model)).classes("text-sm")
            ui.label("自成长: " + ("启用" if settings.feature_self_growth else "关闭")).classes("text-sm")
            ui.label("沙箱: " + ("启用" if settings.sandbox_enabled else "关闭") + " (超时 " + str(settings.sandbox_timeout) + "s)").classes("text-sm")
            ui.label("日志目录: data/logs/").classes("text-sm")

@ui.page("/memories")
def memories_page():
    _ensure_layout_css()
    _drawer()
    _header("长期记忆管理")

    with ui.column().classes("w-full max-w-4xl mx-auto p-4 gap-4"):
        ui.markdown("## 长期记忆管理")

        # 统计卡片
        with ui.row().classes("w-full gap-4"):
            stats_card = ui.card().classes("flex-1 p-3")
            with stats_card:
                ui.label("记忆统计").classes("text-sm font-bold")
                stats_label = ui.label("加载中...").classes("text-xs text-gray-500")

        # 搜索
        with ui.row().classes("w-full items-center gap-2"):
            search_input = ui.input(placeholder="搜索记忆...").classes("flex-1").props("clearable")
            def do_search():
                refresh_memories(search_input.value)
            search_input.on("keydown.enter", do_search)
            ui.button("搜索", icon="search", on_click=do_search).props("flat")

        # 筛选
        filter_select = ui.select(
            label="记忆类型",
            options={"": "全部", "preference": "偏好", "knowledge": "知识", "experience": "经验"},
            value="",
            on_change=lambda e: refresh_memories(search_input.value, e.value),
        ).classes("w-44")

        # 记忆列表
        memory_list = ui.column().classes("w-full gap-2")

        # 开关
        with ui.row().classes("items-center gap-2"):
            toggle_label = ui.label("记忆系统状态:").classes("text-sm")
            toggle_switch = ui.switch(value=True, on_change=lambda e: _toggle_memory(e.value))

    def refresh_memories(search_text="", mtype_filter=""):
        memory_list.clear()
        try:
            agent = _get_agent()

            # 显示统计
            try:
                stats = agent.memory.get_stats(_user_id)
                stats_label.set_text(f"共 {stats['total']} 条记忆")
                if stats.get("by_type"):
                    parts = [f"{k}: {v['count']}条" for k, v in stats["by_type"].items()]
                    stats_label.set_text(" | ".join(parts))
            except Exception:
                stats_label.set_text("记忆系统就绪")

            if search_text:
                memories = agent.search_memories(search_text, top_k=20)
            elif mtype_filter:
                memories = agent.list_memories(memory_type=mtype_filter, top_k=50)
            else:
                memories = agent.list_memories(top_k=50)

            if not memories:
                with memory_list:
                    ui.label("（暂无记忆）").classes("text-gray-400 text-sm")
                return

            for m in memories:
                with memory_list:
                    with ui.card().classes("w-full p-3 gap-1"):
                        # 头部: 类型 + 权重 + 删除
                        with ui.row().classes("items-center justify-between"):
                            type_labels = {"preference": "偏好", "knowledge": "知识", "experience": "经验"}
                            type_badge = type_labels.get(m.get("memory_type", ""), m.get("memory_type", ""))
                            ui.label(f"[{type_badge}]").classes("text-xs font-bold text-blue-600")
                            ui.label(f"权重: {m.get('weight', 0):.2f}").classes("text-xs text-gray-400")
                            ui.button(icon="delete", on_click=lambda mid=m["id"], rcb=refresh_memories: _delete_memory(mid, rcb)
                                     ).props("flat dense round size=sm color=red")

                        # Key
                        ui.label(m.get("key", "")).classes("text-sm font-medium")

                        # Value (max 3 lines)
                        val = m.get("value", "")
                        ui.label(val).classes("text-xs text-gray-600 line-clamp-3")

                        # 来源
                        source = m.get("source", "")
                        if source:
                            ui.label(f"来源: {source}").classes("text-xs text-gray-400")
        except Exception:
            pass

    def _delete_memory(memory_id, refresh_cb):
        try:
            agent = _get_agent()
            agent.delete_memory(memory_id)
            ui.notify("记忆已删除")
            refresh_cb()
        except Exception as e:
            ui.notify(f"删除失败: {e}", type="error")

    def _toggle_memory(enabled):
        try:
            agent = _get_agent()
            agent.toggle_memory(enabled=enabled)
            ui.notify(f"记忆系统{'已开启' if enabled else '已关闭'}")
        except Exception as e:
            ui.notify(f"切换失败: {e}", type="error")

    refresh_memories()


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


