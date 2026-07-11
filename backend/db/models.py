"""
数据模型定义。

包含用户、会话、任务、记忆、反馈等核心实体。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import relationship

from backend.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    """用户"""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    username = Column(String(64), unique=True, nullable=False)
    display_name = Column(String(128), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    """对话会话"""
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    title = Column(String(256), default="新会话")
    model_id = Column(String(64), default="deepseek-chat")
    system_prompt = Column(Text, default="")
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan",
                            order_by="Message.created_at")


class Message(Base):
    """对话消息"""
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    role = Column(String(16), nullable=False)  # user / assistant / system / tool
    content = Column(Text, nullable=False)
    model_id = Column(String(64), default="")
    token_usage = Column(JSON, default=dict)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    session = relationship("Session", back_populates="messages")
    feedback = relationship("Feedback", back_populates="message", uselist=False)


class Feedback(Base):
    """用户反馈"""
    __tablename__ = "feedback"

    id = Column(String(36), primary_key=True, default=_uuid)
    message_id = Column(String(36), ForeignKey("messages.id"), nullable=False)
    rating = Column(Integer, default=0)
    comment = Column(Text, default="")
    tags = Column(JSON, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    message = relationship("Message", back_populates="feedback")


class Memory(Base):
    """长期记忆"""
    __tablename__ = "memories"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    memory_type = Column(String(32), nullable=False)  # preference / knowledge / experience
    key = Column(String(256), nullable=False)
    value = Column(Text, nullable=False)
    weight = Column(Float, default=1.0)
    source = Column(String(64), default="")
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AnalysisTask(Base):
    """数据分析任务"""
    __tablename__ = "analysis_tasks"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=True)
    data_type = Column(String(32), nullable=False)  # gnss / insar / rainfall / groundwater / pore_pressure
    query = Column(Text, nullable=False)
    status = Column(String(16), default="pending")  # pending / running / completed / failed
    result_ = Column("result", JSON, default=dict)
    error = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
