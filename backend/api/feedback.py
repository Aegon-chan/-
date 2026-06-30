"""???? API ??"""
from __future__ import annotations

from fastapi import APIRouter, Query
from typing import Optional

from backend.self_growth.feedback import FeedbackCollector

router = APIRouter()
_feedback_collector = FeedbackCollector()


@router.post("/collect", summary="????")
async def collect_feedback(
    message_id: str,
    rating: int,
    comment: str = "",
    tags: str = "[]",
    user_id: str = "default",
    session_id: str = "",
):
    """??????????/? + ?? + ?????"""
    import json
    result = _feedback_collector.collect(
        message_id=message_id,
        rating=rating,
        comment=comment,
        tags=json.loads(tags),
        user_id=user_id,
        session_id=session_id,
    )
    return result


@router.get("/stats", summary="????")
async def feedback_stats():
    return _feedback_collector.get_stats()


@router.get("/history", summary="????")
async def feedback_history(
    user_id: str = "default",
    limit: int = 50,
):
    return {"feedback": _feedback_collector.get_feedback_by_user(user_id, limit=limit)}


@router.post("/implicit", summary="??????")
async def log_implicit(
    user_id: str = "default",
    event_type: str = "",
    event_data: str = "{}",
    session_id: str = "",
):
    """????????"""
    import json
    _feedback_collector.log_implicit(
        user_id=user_id,
        event_type=event_type,
        event_data=json.loads(event_data),
        session_id=session_id,
    )
    return {"logged": True}
