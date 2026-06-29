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

    # 3. 调用模型
    llm = ModelRegistry.get_llm(model_id)
    if llm is None:
        raise ModelError(
            model_id=model_id,
            detail=f"模型 {model_id} 未注册，请先在设置中配置 API Key 并重启服务",
        )

    from backend.models.base import Message as LLMMessage
    llm_messages = [LLMMessage(role="user", content=body.message)]
    if session.system_prompt:
        llm_messages.insert(0, LLMMessage(role="system", content=session.system_prompt))

    response = await llm.chat(llm_messages)

    # 4. 存储助手回复
    assistant_msg = Message(
        session_id=body.session_id,
        role="assistant",
        content=response.content,
        model_id=model_id,
        token_usage=response.token_usage,
    )
    db.add(assistant_msg)
    await db.flush()

    # 5. 更新会话时间
    from datetime import datetime
    session.updated_at = datetime.utcnow()

    return ChatResponse(
        session_id=body.session_id,
        message_id=assistant_msg.id,
        content=response.content,
        model_id=model_id,
        token_usage=response.token_usage,
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
    llm_messages = [LLMMessage(role="user", content=body.message)]
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

        from datetime import datetime
        session.updated_at = datetime.utcnow()
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
