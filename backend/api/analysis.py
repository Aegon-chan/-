"""数据分析 API 路由"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_async_session
from backend.db.models import AnalysisTask
from backend.core.exceptions import NotFoundError

router = APIRouter()


@router.post("/query", summary="提交分析任务")
async def analyze_data(
    session_id: str = "",
    data_type: str = "gnss",
    query: str = "",
    db: AsyncSession = Depends(get_async_session),
):
    """提交自然语言数据分析任务"""
    task = AnalysisTask(
        session_id=session_id or None,
        data_type=data_type,
        query=query,
        status="pending",
    )
    db.add(task)
    await db.flush()
    return {
        "task_id": task.id,
        "status": task.status,
        "data_type": task.data_type,
        "created_at": task.created_at.isoformat(),
    }


@router.get("/tasks", summary="分析任务列表")
async def list_tasks(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_async_session),
):
    """获取分析任务列表"""
    count_q = select(func.count(AnalysisTask.id))
    total = (await db.execute(count_q)).scalar() or 0

    offset = (page - 1) * page_size
    q = (
        select(AnalysisTask)
        .order_by(AnalysisTask.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = (await db.execute(q)).scalars().all()

    return {
        "tasks": [
            {
                "id": t.id,
                "data_type": t.data_type,
                "query": t.query[:100] if t.query else "",
                "status": t.status,
                "created_at": t.created_at.isoformat(),
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            }
            for t in rows
        ],
        "total": total,
    }


@router.get("/tasks/{task_id}", summary="获取任务状态")
async def get_analysis_task(
    task_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    """获取分析任务状态和结果"""
    q = select(AnalysisTask).where(AnalysisTask.id == task_id)
    task = (await db.execute(q)).scalar_one_or_none()
    if not task:
        raise NotFoundError(resource="分析任务", resource_id=task_id)

    return {
        "task_id": task.id,
        "data_type": task.data_type,
        "query": task.query,
        "status": task.status,
        "result": task.result_ or {},
        "error": task.error or "",
        "created_at": task.created_at.isoformat(),
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }
