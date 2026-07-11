"""对话 API 路由"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_async_session
from backend.db.models import Session as SessionModel, Message
from backend.schemas.chat import ChatRequest, ChatResponse, StreamEvent
from backend.core.exceptions import NotFoundError, ModelError
from backend.models.registry import ModelRegistry
from backend.uploads import process_attachments

router = APIRouter()


@router.post("/completions", response_model=ChatResponse, summary="创建对话补全")
async def create_chat_completion(
    body: ChatRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """发送消息并获取 AI 回复（非流式）"""
    # 1. 校验会话
    q = select(SessionModel).where(SessionModel.id == body.session_id)
    session = (await db.execute(q)).scalar_one_or_none()
    if not session:
        raise NotFoundError(resource="会话", resource_id=body.session_id)

    model_id = body.model_id or session.model_id

    # 2. 存储用户消息
    user_msg = Message(
        session_id=body.session_id,
        role="user",
        content=body.message,
        model_id=model_id,
    )
    db.add(user_msg)
    await db.flush()

    # 3. 验证模型可用
    llm = ModelRegistry.get_llm(model_id)
    if llm is None:
        raise ModelError(
            model_id=model_id,
            detail=f"模型 {model_id} 未注册，请先在设置中配置 API Key 并重启服务",
        )

    # 4. 加载历史消息到 ResearchAgent
    from backend.core.agent import ResearchAgent

    agent = ResearchAgent(
        session_id=body.session_id,
        user_id=session.user_id,
        model_id=model_id,
    )
    history_q = (
        select(Message)
        .where(Message.session_id == body.session_id)
        .order_by(Message.created_at)
    )
    history_rows = (await db.execute(history_q)).scalars().all()
    agent.load_history([
        {"role": m.role, "content": m.content}
        for m in history_rows
    ])

    # 5. 准备附件数据
    att_dicts = None
    if body.attachments:
        att_dicts = [{"url": a.url, "filename": a.filename, "mime_type": a.mime_type} for a in body.attachments]

    # 6. 调用 Agent 完整管道
    collected = []
    async for token in agent.stream_chat(body.message, attachments=att_dicts):
        collected.append(token)
    full_content = "".join(collected)

    # 7. 存储助手回复
    assistant_msg = Message(
        session_id=body.session_id,
        role="assistant",
        content=full_content,
        model_id=model_id,
        token_usage={},
    )
    db.add(assistant_msg)
    await db.flush()

    # 8. 更新会话时间
    from datetime import datetime, timezone
    session.updated_at = datetime.now(timezone.utc)

    return ChatResponse(
        session_id=body.session_id,
        message_id=assistant_msg.id,
        content=full_content,
        model_id=model_id,
        token_usage={},
    )


@router.post("/stream", summary="流式对话")
async def stream_chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """发送消息并流式获取 AI 回复（SSE 格式）"""
    from fastapi.responses import StreamingResponse
    import json

    # 校验会话
    q = select(SessionModel).where(SessionModel.id == body.session_id)
    session = (await db.execute(q)).scalar_one_or_none()
    if not session:
        raise NotFoundError(resource="会话", resource_id=body.session_id)

    model_id = body.model_id or session.model_id

    # 存储用户消息
    user_msg = Message(
        session_id=body.session_id,
        role="user",
        content=body.message,
        model_id=model_id,
    )
    db.add(user_msg)
    await db.flush()

    # 获取模型
    llm = ModelRegistry.get_llm(model_id)
    if llm is None:
        raise ModelError(
            model_id=model_id,
            detail=f"模型 {model_id} 未注册，请先在设置中配置 API Key 并重启服务",
        )

    from backend.models.base import Message as LLMMessage
    from backend.models.base import ContentPart
    multimodal_parts = process_attachments(body.attachments)
    llm_messages = [LLMMessage(role="user", content=body.message, multimodal_parts=multimodal_parts)]
    if session.system_prompt:
        llm_messages.insert(0, LLMMessage(role="system", content=session.system_prompt))

    async def event_generator():
        full_content = ""
        async for token in llm.stream_chat(llm_messages):
            full_content += token
            yield f"data: {json.dumps({'event': 'token', 'data': token})}\n\n"

        # 存储完整回复
        msg = Message(
            session_id=body.session_id,
            role="assistant",
            content=full_content,
            model_id=model_id,
        )
        db.add(msg)
        await db.commit()

        from datetime import datetime, timezone
        session.updated_at = datetime.now(timezone.utc)
        await db.commit()

        yield f"data: {json.dumps({'event': 'done', 'session_id': body.session_id, 'message_id': msg.id})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
