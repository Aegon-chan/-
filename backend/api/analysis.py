"""数据分析 API"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.post("/query")
async def analyze_data():
    """自然语言数据分析"""
    return {"message": "Not implemented yet"}


@router.get("/tasks/{task_id}")
async def get_analysis_task(task_id: str):
    """获取分析任务状态"""
    return {"task_id": task_id, "status": "pending"}
