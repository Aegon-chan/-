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
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.db.session import async_engine as engine
from backend.core.exceptions import AppException

_start_time = time.time()

logger = logging.getLogger("research_agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # Ensure all data directories exist at startup
    settings.ensure_dirs()

    # Configure logging with rotation
    from backend.logging_config import setup_logging
    setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
    )

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


# --- Audit middleware (wraps around all requests) ---
from backend.audit import audit_middleware as _audit_mw  # noqa: E402
app.middleware("http")(_audit_mw)

# Audit log viewer
from fastapi.responses import HTMLResponse  # noqa: E402


@app.get("/audit", include_in_schema=False)
async def _audit_viewer():
    from backend.audit import get_audit_db  # noqa: E402
    db = get_audit_db()
    stats = db.stats()
    rows = db.query(limit=200)
    html_rows = ""
    for r in rows:
        html_rows += "<tr class="" + cls + ""><td>" + str(r.get("timestamp", ""))[:19] + "</td><td>" + str(r.get("method", "")) + "</td><td>" + str(r.get("path", "")) + "</td><td>" + str(r.get("status_code", "")) + "</td><td>" + str(r.get("duration_ms", "")) + "ms</td><td>" + str(r.get("error", "") or "")[:60] + "</td></tr>"
    html = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>Audit Log</title><style>
body{font-family:monospace;font-size:13px;padding:20px;background:#f5f5f5}
.stats{margin-bottom:20px;padding:10px 15px;background:#fff;border-radius:6px;box-shadow:0 1px 3px rgba(0,0,0,.1)}
.stats span{margin-right:20px}
table{border-collapse:collapse;width:100%;background:#fff;border-radius:6px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1)}
th{background:#4a5568;color:#fff;padding:8px 10px;text-align:left}
td{padding:6px 10px;border-bottom:1px solid #e2e8f0}
tr.error td{background:#fff5f5;color:#c53030}
tr.warn td{background:#fffff0;color:#975a16}
tr:hover td{background:#ebf4ff}
</style></head><body>
<div class="stats"><span>Total: <strong>""" + str(stats.get("total_entries", 0)) + """</strong></span>
<span>Errors: <strong>""" + str(stats.get("error_count", 0)) + """</strong></span>
<span>Methods: """ + str(stats.get("by_method", {})) + """</span></div>
<table><thead><tr><th>Time</th><th>Method</th><th>Path</th><th>Status</th><th>Duration</th><th>Error</th></tr></thead><tbody>""" + html_rows + """</tbody></table></body></html>"""
    return HTMLResponse(html)


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
from backend.api import router as api_router  # noqa: E402

app.include_router(api_router, prefix="/api/v1")

# --- Monitoring data routes ---
from backend.api.monitoring import router as monitoring_router  # noqa: E402
app.include_router(monitoring_router, prefix="/api/v1/monitoring")

# --- Mobile API routes ---
from mobile import mobile_router  # noqa: E402
app.include_router(mobile_router, prefix="/api/v1/mobile")

# --- Static file serving for uploads ---
import os as _os  # noqa: E402
_uploads_dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "data", "uploads")
_os.makedirs(_uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_uploads_dir), name="uploads")


# --- 健康检查 ---
@app.get("/health")
async def health_check():
    """Enhanced health check with component status."""
    import time
    from backend.db.session import sync_engine
    from backend.models.registry import ModelRegistry
    from datetime import datetime, timezone

    checks = {"database": False, "models_registered": 0, "disk_space": "unknown"}
    try:
        from sqlalchemy import text
        with sync_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
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
        from sqlalchemy import text
        with sync_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
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
