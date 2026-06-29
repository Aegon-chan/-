"""
FastAPI 应用入口。

注册所有路由、中间件、事件处理器。
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.db.session import async_engine as engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    # 启动：创建表（开发环境自动迁移）
    if settings.app_env == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    # 关闭：释放资源
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- 异常处理 ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"},
    )


# --- 健康检查 ---
@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


# --- 路由注册 (Phase 1 逐步添加) ---
from backend.api import router as api_router

app.include_router(api_router, prefix="/api/v1")
