"""监测数据库会话管理。

独立的 SQLite 引擎，与主应用数据库分离，避免数据膨胀影响主库性能。
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import create_engine

from backend.config import settings


def _async_sqlite_url(url: str) -> str:
    """将 sqlite:/// 转为 aiosqlite 兼容的 sqlite+aiosqlite:///"""
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return url


async_engine = create_async_engine(
    _async_sqlite_url(settings.monitoring_db_url),
    echo=settings.app_debug,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    pool_pre_ping=True,    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# --- 同步引擎（用于脚本、后台任务）---
sync_engine = create_engine(
    settings.monitoring_db_url,
    echo=settings.app_debug,
    future=True,
)

SyncSessionLocal = sessionmaker(
    sync_engine,
    expire_on_commit=False,
)


# --- ORM 基类 ---
class MonitoringBase(DeclarativeBase):
    pass


# --- FastAPI 依赖注入 ---
async def get_monitoring_session() -> AsyncSession:
    """FastAPI 依赖：获取异步监测数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_monitoring_sync_session():
    """获取同步监测数据库会话（用于脚本/后台任务）"""
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def init_monitoring_db():
    """启动时创建所有监测数据表（如不存在）"""
    async with async_engine.begin() as conn:
        await conn.run_sync(MonitoringBase.metadata.create_all)
