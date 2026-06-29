"""NiceGUI 前端应用入口"""

from __future__ import annotations

from nicegui import ui

# 全局主题
ui.dark_mode().enable()

# 页面状态
current_model = "deepseek-chat"


@ui.page("/")
def main_page():
    """主页面：对话界面"""
    with ui.left_drawer().classes("bg-gray-100 dark:bg-gray-800"):
        ui.label("导航").classes("text-lg font-bold p-4")
        with ui.column().classes("p-2 gap-2"):
            ui.button("对话", on_click=lambda: ui.navigate.to("/")
                     ).props("flat icon=chat")
            ui.button("数据分析", on_click=lambda: ui.navigate.to("/analysis")
                     ).props("flat icon=analytics")
            ui.button("知识库", on_click=lambda: ui.navigate.to("/knowledge")
                     ).props("flat icon=library_books")
            ui.button("设置", on_click=lambda: ui.navigate.to("/settings")
                     ).props("flat icon=settings")

    with ui.header(elevated=True).classes("items-center justify-between"):
        ui.label("Research Agent").classes("text-lg font-bold")
        ui.select(
            label="模型",
            options={
                "deepseek-chat": "DeepSeek Chat",
                "moonshot-v1": "KIMI (Moonshot)",
                "gpt-4o": "GPT-4o",
            },
            value=current_model,
            on_change=lambda e: setattr(ui, "_model", e.value),
        ).classes("w-48")

    with ui.column().classes("w-full max-w-4xl mx-auto p-4 h-[calc(100vh-140px)]"):
        chat_area = ui.column().classes("flex-1 overflow-y-auto w-full gap-2")
        with ui.row().classes("w-full items-center gap-2 sticky bottom-0 bg-white dark:bg-gray-900 pt-2"):
            input_field = ui.input(
                placeholder="输入你的问题...",
            ).classes("flex-1").props("clearable autofocus")
            input_field.on("keydown.enter", lambda: send_message())

            async def send_message():
                text = input_field.value
                if not text:
                    return
                input_field.value = ""
                with chat_area:
                    ui.chat_message(text, name="用户", sent=True)
                with chat_area:
                    ui.chat_message("正在思考...", name="助手", sent=False)

            ui.button("发送", on_click=send_message).props("flat")

    with ui.footer().classes("justify-between"):
        ui.label("v0.1.0-dev")
        ui.label("状态: 就绪").classes("text-green-500")


@ui.page("/analysis")
def analysis_page():
    """数据分析页面"""
    with ui.header(elevated=True).classes("items-center justify-between"):
        ui.label("数据分析").classes("text-lg font-bold")
        ui.button("返回", on_click=lambda: ui.navigate.to("/")).props("flat")

    with ui.column().classes("w-full max-w-4xl mx-auto p-4"):
        ui.markdown("## 数据分析")
        ui.markdown("上传监测数据文件，用自然语言进行分析。")
        ui.upload(
            label="上传数据文件",
            on_upload=lambda e: ui.notify(f"已上传: {e.name}"),
            multiple=True,
        ).classes("w-full")
        ui.textarea(
            label="分析需求",
            placeholder="例如：分析这个月的 GNSS 位移趋势..."
        ).classes("w-full")
        ui.button("开始分析", on_click=lambda: ui.notify("分析任务已提交"))


@ui.page("/knowledge")
def knowledge_page():
    """知识库管理页面"""
    with ui.header(elevated=True).classes("items-center justify-between"):
        ui.label("知识库").classes("text-lg font-bold")
        ui.button("返回", on_click=lambda: ui.navigate.to("/")).props("flat")

    with ui.column().classes("w-full max-w-4xl mx-auto p-4"):
        ui.markdown("## 知识库管理")
        ui.markdown("上传并管理规范条文、文献和监测案例。")
        ui.upload(
            label="上传文档 (PDF/TXT/MD)",
            on_upload=lambda e: ui.notify(f"已上传: {e.name}"),
        ).classes("w-full")
        ui.separator()
        ui.label("已上传文档:")
        ui.label("（暂无文档）").classes("text-gray-400")


@ui.page("/settings")
def settings_page():
    """设置页面"""
    with ui.header(elevated=True).classes("items-center justify-between"):
        ui.label("设置").classes("text-lg font-bold")
        ui.button("返回", on_click=lambda: ui.navigate.to("/")).props("flat")

    with ui.column().classes("w-full max-w-4xl mx-auto p-4 gap-4"):
        ui.markdown("## 设置")
        ui.input("DeepSeek API Key", password=True, value="").classes("w-full")
        ui.input("KIMI API Key", password=True, value="").classes("w-full")
        ui.input("OpenAI API Key", password=True, value="").classes("w-full")
        ui.separator()
        ui.label("生成报告默认格式:")
        ui.toggle(["PDF", "Word", "HTML"], value="PDF")
        ui.separator()
        ui.button("保存设置", on_click=lambda: ui.notify("设置已保存")).props("primary")


def run():
    ui.run(title="Research Agent", host="0.0.0.0", port=8080)


if __name__ == "__main__":
    run()
