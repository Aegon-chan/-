"""数据分析 API 路由"""
from __future__ import annotations


from fastapi import APIRouter, Depends, Query
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


# ═══════════════════════════════════════════════════════════════
# NL2Query endpoints
# ═══════════════════════════════════════════════════════════════

from pydantic import BaseModel, Field  # noqa: E402
from typing import Optional  # noqa: E402

class CodeGenRequest(BaseModel):
    query: str = Field(..., description="自然语言查询")
    data_type: str = Field("gnss", description="数据类型")
    data_description: str = Field("", description="数据列描述")
    file_id: Optional[str] = Field(None, description="已上传的数据文件 ID")
    model_id: Optional[str] = Field(None, description="模型 ID")

class ExecuteRequest(BaseModel):
    query: str = Field(..., description="自然语言查询")
    data_type: str = Field("gnss", description="数据类型")
    data_description: str = Field("", description="数据列描述")
    file_id: Optional[str] = Field(None, description="已上传的数据文件 ID")
    model_id: Optional[str] = Field(None, description="模型 ID")
    use_cache: bool = Field(True, description="是否使用缓存")
@router.post("/nl2query/code", summary="NL→Python 代码生成")
async def nl2query_code(body: CodeGenRequest):
    """将自然语言查询转换为 Python 代码"""
    from backend.analysis.codegen import generate_code

    # Load data schema if a file was specified
    data_schema = None
    if body.file_id:
        from backend.analysis.data_loader import load_data_for_analysis
        _df, data_schema, err = load_data_for_analysis(body.file_id)
        if err:
            return {"code": "", "success": False, "error": f"数据读取失败: {err}"}

    result = await generate_code(
        query=body.query,
        data_type=body.data_type,
        data_description=body.data_description,
        model_id=body.model_id,
        data_schema=data_schema,
    )
    return result
async def nl2query_execute(body: ExecuteRequest):
    """将自然语言查询转换为 Python 代码并在沙箱中执行"""
    from backend.analysis.codegen import generate_code
    from backend.core.sandbox import CodeSandbox

    # Load data if a file was specified
    df = None
    data_schema = None
    sandbox_context = None
    if body.file_id:
        from backend.analysis.data_loader import load_data_for_analysis, dataframe_to_sandbox_context
        df, data_schema, err = load_data_for_analysis(body.file_id)
        if err:
            return {"code": "", "success": False, "error": f"数据读取失败: {err}"}
        if df is not None:
            sandbox_context = dataframe_to_sandbox_context(df)

    # 1. Check cache (only when no file context changes)
    if body.use_cache and not sandbox_context:
        from backend.analysis.cache import QueryCache
        cache = QueryCache()
        cached = cache.get(body.query, body.data_type)
        if cached is not None:
            return {
                "success": True,
                "from_cache": True,
                "code": cached.get("code", ""),
                "result": cached.get("result", {}),
            }

    # 2. Generate code with data schema
    gen_result = await generate_code(
        query=body.query,
        data_type=body.data_type,
        data_description=body.data_description,
        model_id=body.model_id,
        data_schema=data_schema,
    )
    if not gen_result["success"]:
        return gen_result

    code = gen_result["code"]

    # 3. Execute in sandbox with data context injected
    sandbox = CodeSandbox(timeout=30)
    try:
        exec_result = sandbox.execute_python(code, context=sandbox_context)
        output = exec_result.to_dict()

        # 4. Cache result (only when no data file context, since schema can vary)
        if body.use_cache and exec_result.success and not sandbox_context:
            cache = QueryCache()
            cache.set(body.query, body.data_type, code, output)

        return {
            "success": exec_result.success,
            "from_cache": False,
            "code": code,
            "result": output,
        }
    finally:
        sandbox.clean()

async def clear_query_cache(cache_key: str):
    """清除指定的查询缓存"""
    from backend.analysis.cache import QueryCache
    cache = QueryCache()
    cache.delete(cache_key)
    return {"success": True}


@router.get("/nl2query/files", summary="列出已上传的数据文件")
async def list_data_files():
    """列出所有 CSV/XLSX 数据文件供前端选择"""
    from backend.analysis.data_loader import list_uploaded_files
    return {"files": list_uploaded_files()}


@router.get("/nl2query/files/{file_id}/preview", summary="数据文件预览")
async def preview_data_file(file_id: str):
    """读取数据文件的列信息和前5行示例"""
    from backend.analysis.data_loader import load_data_for_analysis
    _df, schema, err = load_data_for_analysis(file_id)
    if err:
        return {"success": False, "error": err}
    if not schema:
        return {"success": False, "error": "无法提取数据结构"}

    sample_rows = []
    for row in schema.get("sample_rows", []):
        sample_rows.append({k: str(v) for k, v in row.items()})

    return {
        "success": True,
        "column_names": schema["column_names"],
        "column_info": schema["column_info"],
        "row_count": schema["row_count"],
        "sample_rows": sample_rows,
    }


@router.get("/nl2query/cache", summary="查询缓存列表")
async def list_query_cache(limit: int = Query(20, description="返回条数")):
    """列出最近的查询缓存"""
    from backend.analysis.cache import QueryCache
    cache = QueryCache()
    return {"entries": cache.list_recent(limit=limit)}


