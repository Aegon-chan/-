"""自成长状态与运维 API 路由。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from backend.core.agent import ResearchAgent

router = APIRouter()

# 与 feedback.py 共享的 Agent 缓存（避免重复创建）
_agent_cache: dict[str, ResearchAgent] = {}


def _get_agent(user_id: str) -> ResearchAgent:
    """获取或创建用户对应的 ResearchAgent 实例。"""
    if user_id not in _agent_cache:
        _agent_cache[user_id] = ResearchAgent(
            session_id=f"self_growth_api_{user_id}",
            user_id=user_id,
        )
    return _agent_cache[user_id]


@router.get("/stats", summary="自成长统计")
async def self_growth_stats(
    user_id: str = Query("default", description="用户 ID"),
):
    """获取自成长模块的全面统计信息。

    包含：
    - 记忆概览（各类型数量、权重分布）
    - 反馈统计（总量、评分分布）
    - Prompt 版本（各任务类型的最新版本和评分）
    - 微调状态（已训练模型数、当前活跃模型）
    - 后台优化状态
    """
    agent = _get_agent(user_id)
    return agent.get_optimization_stats()


@router.post("/run-optimization", summary="手动触发优化周期")
async def run_optimization(
    user_id: str = Query("default", description="用户 ID"),
):
    """手动触发一次完整的自成长优化周期。

    包括：
    1. 记忆权重衰减
    2. 重复记忆合并
    3. Prompt 自动优化（如有足够新反馈）
    4. LoRA 微调触发检查
    """
    agent = _get_agent(user_id)
    agent._run_optimization_cycle()
    return {"success": True, "message": "优化周期已执行"}


@router.get("/finetune/status", summary="微调状态")
async def finetune_status(
    user_id: str = Query("default", description="用户 ID"),
):
    """获取模型微调的详细状态。"""
    agent = _get_agent(user_id)
    models = agent.fine_tuner.list_models()
    jobs = agent.fine_tuner.list_jobs()
    return {
        "models": models,
        "jobs": jobs,
        "active_model": next((m for m in models if m.get("is_active")), None),
        "model_count": len(models),
        "job_count": len(jobs),
    }
