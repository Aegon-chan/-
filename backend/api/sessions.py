"""会话管理 API"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_async_session
from backend.db.models import Session as SessionModel, Message, User
from backend.schemas.sessions import (
    MessageCreate,
    SessionCreate,
    SessionUpdate,
    SessionResponse,
    SessionDetailResponse,
    SessionListResponse,
)
from backend.core.exceptions import NotFoundError

router = APIRouter()


@router.post("/", response_model=SessionResponse, summary="创建会话")
async def create_session(
    body: SessionCreate,
    db: AsyncSession = Depends(get_async_session),
):
    """创建新的对话会话"""
    # Resolve user_id: try UUID first, then treat as username
    user_id = body.user_id
    user_q = select(User).where(User.id == body.user_id)
    user = (await db.execute(user_q)).scalar_one_or_none()
    if user is None:
        user_q = select(User).where(User.username == body.user_id)
        user = (await db.execute(user_q)).scalar_one_or_none()
    if user is not None:
        user_id = user.id

    session = SessionModel(
        title=body.title,
        model_id=body.model_id,
        system_prompt=body.system_prompt,
        user_id=user_id,
    )
    db.add(session)
    await db.flush()
    return SessionResponse(
        id=session.id,
        title=session.title,
        model_id=session.model_id,
        message_count=0,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get("/", response_model=SessionListResponse, summary="会话列表")
async def list_sessions(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_async_session),
):
    """获取会话列表，按更新时间倒序"""
    # 总数
    count_q = select(func.count(SessionModel.id))
    total = (await db.execute(count_q)).scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    q = (
        select(SessionModel)
        .order_by(SessionModel.updated_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = (await db.execute(q)).scalars().all()

    sessions = []
    for s in rows:
        msg_count_q = select(func.count(Message.id)).where(
            Message.session_id == s.id
        )
        msg_count = (await db.execute(msg_count_q)).scalar() or 0
        sessions.append(
            SessionResponse(
                id=s.id,
                title=s.title,
                model_id=s.model_id,
                message_count=msg_count,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
        )

    return SessionListResponse(sessions=sessions, total=total)


@router.get("/{session_id}", response_model=SessionDetailResponse, summary="会话详情")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    """获取会话详情及消息历史"""
    q = select(SessionModel).where(SessionModel.id == session_id)
    session = (await db.execute(q)).scalar_one_or_none()
    if not session:
        raise NotFoundError(resource="会话", resource_id=session_id)

    # 加载消息
    msg_q = (
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    messages = (await db.execute(msg_q)).scalars().all()

    return SessionDetailResponse(
        id=session.id,
        title=session.title,
        model_id=session.model_id,
        system_prompt=session.system_prompt or "",
        messages=[
            {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
            for m in messages
        ],
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.patch("/{session_id}", response_model=SessionResponse, summary="更新会话")
async def update_session(
    session_id: str,
    body: SessionUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    """更新会话标题或模型"""
    q = select(SessionModel).where(SessionModel.id == session_id)
    session = (await db.execute(q)).scalar_one_or_none()
    if not session:
        raise NotFoundError(resource="会话", resource_id=session_id)

    if body.title is not None:
        session.title = body.title
    if body.model_id is not None:
        session.model_id = body.model_id
    session.updated_at = datetime.now(timezone.utc)
    await db.flush()

    msg_count_q = select(func.count(Message.id)).where(
        Message.session_id == session_id
    )
    msg_count = (await db.execute(msg_count_q)).scalar() or 0
    return SessionResponse(
        id=session.id,
        title=session.title,
        model_id=session.model_id,
        message_count=msg_count,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )




@router.post("/{session_id}/messages", summary="批量追加消息")
async def append_messages(
    session_id: str,
    body: MessageCreate,
    db: AsyncSession = Depends(get_async_session),
):
    """向会话批量追加消息"""
    q = select(SessionModel).where(SessionModel.id == session_id)
    session = (await db.execute(q)).scalar_one_or_none()
    if not session:
        raise NotFoundError(resource="会话", resource_id=session_id)

    saved = []
    for msg in body.messages:
        message = Message(
            session_id=session_id,
            role=msg.get("role", "user"),
            content=msg.get("content", ""),
            model_id=msg.get("model_id", session.model_id),
            metadata_=msg.get("metadata", {}),
        )
        db.add(message)
        saved.append(message)

    # Update session timestamp
    session.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return {
        "ok": True,
        "session_id": session_id,
        "saved_count": len(saved),
    }

@router.delete("/{session_id}", summary="删除会话")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    """删除会话及所有消息"""
    q = select(SessionModel).where(SessionModel.id == session_id)
    session = (await db.execute(q)).scalar_one_or_none()
    if not session:
        raise NotFoundError(resource="会话", resource_id=session_id)

    await db.delete(session)
    await db.flush()
    return {"deleted": session_id, "ok": True}
