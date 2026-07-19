"""反馈 API 路由"""

from __future__ import annotations

import json

from fastapi import APIRouter, Query

from backend.core.agent import ResearchAgent

router = APIRouter()

# 内存中的 Agent 缓存，按 user_id 隔离
_agent_cache: dict[str, ResearchAgent] = {}


def _get_agent(user_id: str) -> ResearchAgent:
    """获取或创建用户对应的 ResearchAgent 实例。"""
    if user_id not in _agent_cache:
        _agent_cache[user_id] = ResearchAgent(
            session_id=f"feedback_api_{user_id}",
            user_id=user_id,
        )
    return _agent_cache[user_id]


@router.post("/collect", summary="提交反馈")
async def collect_feedback(
    message_id: str,
    rating: int,
    comment: str = "",
    tags: str = "[]",
    user_id: str = "default",
    session_id: str = "",
):
    """提交用户反馈（评分 + 评论 + 标签），同时触发自成长流程。

    反馈数据会：
    1. 存入 FeedbackCollector 数据库
    2. 提取为记忆写入 MemoryStore
    3. 累计优质反馈计数，供后台 Prompt 优化和微调触发
    """
    parsed_tags = json.loads(tags) if isinstance(tags, str) else tags

    # 通过 Agent 提交反馈（包含自成长闭环）
    agent = _get_agent(user_id)
    result = agent.submit_feedback(
        message_id=message_id,
        rating=rating,
        comment=comment,
        tags=parsed_tags,
        session_id=session_id,
    )
    return result


@router.get("/stats", summary="反馈统计")
async def feedback_stats(user_id: str = Query("default", description="用户 ID")):
    """获取用户的反馈统计数据。"""
    agent = _get_agent(user_id)
    return agent.feedback_collector.get_stats()


@router.get("/history", summary="反馈历史")
async def feedback_history(
    user_id: str = Query("default", description="用户 ID"),
    limit: int = Query(50, description="返回条数"),
):
    """获取用户的反馈历史列表。"""
    agent = _get_agent(user_id)
    feedbacks = agent.feedback_collector.get_feedback_by_user(user_id, limit=limit)
    return {"feedback": feedbacks}


@router.post("/implicit", summary="记录隐式反馈")
async def log_implicit(
    user_id: str = Query("default", description="用户 ID"),
    event_type: str = Query("", description="事件类型"),
    event_data: str = Query("{}", description="事件数据 JSON"),
    session_id: str = Query("", description="会话 ID"),
):
    """记录用户隐式反馈（编辑行为、重复查询等）。"""
    agent = _get_agent(user_id)
    parsed_data = json.loads(event_data) if isinstance(event_data, str) else event_data
    agent.feedback_collector.log_implicit(
        user_id=user_id,
        event_type=event_type,
        event_data=parsed_data,
        session_id=session_id,
    )
    return {"logged": True}


@router.post("/optimize", summary="手动触发优化")
async def trigger_optimization(
    user_id: str = Query("default", description="用户 ID"),
):
    """手动触发一次完整的自成长优化周期。"""
    agent = _get_agent(user_id)
    agent._run_optimization_cycle()
    return {"success": True, "message": "优化周期已触发"}
