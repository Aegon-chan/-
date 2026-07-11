"""FastAPI 应用入口。

注册所有路由、中间件、事件处理器。
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.db.session import async_engine as engine
from backend.core.exceptions import AppException

_start_time = time.time()

logger = logging.getLogger("research_agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    # Ensure all data directories exist at startup
    settings.ensure_dirs()
    #应用生命周期管理"""
    # 启动：数据库表由 Alembic migration 管理（scripts/setup.ps1 中执行）

    # 启动：注册 AI 模型
    from backend.models import init_models
    init_models()

    # Ensure default user exists
    try:
        from backend.db.session import sync_engine as _sync_engine
        from sqlalchemy import text as _text
        with _sync_engine.connect() as _conn:
            result = _conn.execute(_text("SELECT id FROM users WHERE username = 'default'"))
            exists = result.scalar()
            if not exists:
                import uuid
                from datetime import datetime, timezone
                _conn.execute(
                    _text("INSERT INTO users (id, username, display_name, created_at, updated_at) "
                           "VALUES (:id, :username, :display_name, :created_at, :updated_at)"),
                    {
                        "id": str(uuid.uuid4()),
                        "username": "default",
                        "display_name": "Default User",
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                )
                _conn.commit()
                logger.info("Default user created")
            else:
                logger.debug("Default user already exists")
    except Exception as _ue:
        logger.warning("Could not create default user: %s", _ue)


    # Initialize monitoring database
    try:
        from backend.db.monitoring_session import init_monitoring_db
        await init_monitoring_db()
        logger.info("Monitoring database initialized")
    except Exception as e:
        logger.warning("Monitoring database init failed: %s", e)

    # Seed monitoring data if empty
    if settings.monitoring_seed_on_startup:
        try:
            from scripts.seed_monitoring_data import seed_monitoring_data
            stats = seed_monitoring_data()
            logger.info("Monitoring seed data: %s", stats)
        except Exception as e:
            logger.warning("Monitoring seed data failed: %s", e)

    logger.info("Research Agent 启动完成: env=%s", settings.app_env)
    yield

    # 关闭：释放资源
    await engine.dispose()
    logger.info("Research Agent 已关闭")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- 请求日志中间件 ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    logger.info(
        "%s %s %s %.0fms",
        request.method,
        request.url.path,
        response.status_code,
        elapsed * 1000,
    )
    return response


# --- 异常处理 ---

@app.exception_handler(status.HTTP_404_NOT_FOUND)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={"code": "NOT_FOUND", "message": "接口不存在", "detail": str(request.url.path)},
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "code": "VALIDATION_ERROR",
            "message": "请求参数校验失败",
            "detail": exc.errors(),
        },
    )


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    if exc.status_code >= 500:
        logger.exception("AppException: %s - %s", exc.code, exc.message)
    else:
        logger.warning("AppException: %s - %s", exc.code, exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "服务器内部错误",
            "detail": str(exc) if settings.app_debug else None,
        },
    )


# --- 路由注册 ---
from backend.api import router as api_router

app.include_router(api_router, prefix="/api/v1")

# --- Monitoring data routes ---
from backend.api.monitoring import router as monitoring_router
app.include_router(monitoring_router, prefix="/api/v1/monitoring")

# --- Mobile API routes ---
from mobile import mobile_router
app.include_router(mobile_router, prefix="/api/v1/mobile")

# --- Static file serving for uploads ---
import os as _os
_uploads_dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "data", "uploads")
_os.makedirs(_uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_uploads_dir), name="uploads")


# --- 健康检查 ---
@app.get("/health")
async def health_check():
    """Enhanced health check with component status."""
    import os, time
    from backend.db.session import sync_engine
    from backend.models.registry import ModelRegistry
    from datetime import datetime, timezone

    checks = {"database": False, "models_registered": 0, "disk_space": "unknown"}
    try:
        with sync_engine.connect() as conn:
            conn.execute(sync_engine.text("SELECT 1"))
            checks["database"] = True
    except Exception:
        checks["database"] = False

    try:
        checks["models_registered"] = len(ModelRegistry.list_models())
    except Exception:
        pass

    data_dir = settings.data_dir
    try:
        if data_dir.exists():
            usage = sum(f.stat().st_size for f in data_dir.rglob("*") if f.is_file())
            checks["disk_space"] = f"{usage / 1024 / 1024:.1f} MB"
    except Exception:
        pass

    checks["feature_self_growth"] = settings.feature_self_growth
    checks["feature_feedback"] = settings.feature_feedback
    checks["feature_finetune"] = settings.feature_finetune

    return {
        "status": "ok",
        "app": settings.app_name,
        "version": "0.1.0",
        "env": settings.app_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime": round(time.time() - _start_time, 1),
        "checks": checks,
    }

# --- Prometheus Metrics Endpoint ---
@app.get("/metrics")
async def metrics_endpoint():
    """Expose basic Prometheus-style metrics."""
    import os, time
    from backend.models.registry import ModelRegistry

    lines = []
    lines.append("# HELP research_agent_info Static metadata about Research Agent")
    lines.append("# TYPE research_agent_info gauge")
    lines.append(f'research_agent_info{{env="{settings.app_env}",version="0.1.0"}} 1')
    lines.append("")
    lines.append("# HELP research_agent_models_registered Number of registered LLM models")
    lines.append("# TYPE research_agent_models_registered gauge")
    try:
        models = ModelRegistry.list_models()
        llm_count = sum(1 for m in models if m["type"] == "llm")
    except Exception:
        llm_count = 0
    lines.append(f"research_agent_models_registered {llm_count}")
    lines.append("")

    lines.append("# HELP research_agent_database_up Whether the database is reachable")
    lines.append("# TYPE research_agent_database_up gauge")
    try:
        from backend.db.session import sync_engine
        with sync_engine.connect() as conn:
            conn.execute(sync_engine.text("SELECT 1"))
        lines.append("research_agent_database_up 1")
    except Exception:
        lines.append("research_agent_database_up 0")
    lines.append("")

    lines.append("# HELP research_agent_features Feature flag states")
    lines.append("# TYPE research_agent_features gauge")
    lines.append(f'research_agent_features{{feature="self_growth"}} {"1" if settings.feature_self_growth else "0"}')
    lines.append(f'research_agent_features{{feature="feedback"}} {"1" if settings.feature_feedback else "0"}')
    lines.append(f'research_agent_features{{feature="finetune"}} {"1" if settings.feature_finetune else "0"}')

    return "\n".join(lines) + "\n"


# --- 直接运行 ---
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )
