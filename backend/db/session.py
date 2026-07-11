"""
数据库会话管理。

支持同步和异步两种会话模式。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import create_engine

from backend.config import settings

# --- 异步引擎（用于 FastAPI 请求） ---

def _async_sqlite_url(url: str) -> str:
    """将 sqlite:/// 转为 aiosqlite 兼容的 sqlite+aiosqlite:///"""
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return url


async_engine = create_async_engine(
    _async_sqlite_url(settings.database_url),
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


# --- 同步引擎（用于 Alembic、脚本） ---
sync_engine = create_engine(
    settings.database_url,
    echo=settings.app_debug,
    future=True,
)

SyncSessionLocal = sessionmaker(
    sync_engine,
    expire_on_commit=False,
)


# --- ORM 基类 ---
class Base(DeclarativeBase):
    pass


# --- 依赖注入 ---
async def get_async_session() -> AsyncSession:
    """FastAPI 依赖：获取异步数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_session_ctx():
    """获取同步数据库会话（用于脚本/后台任务）"""
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()



def get_sync_session():
    """获取一个新的同步数据库会话"""
    return SyncSessionLocal()
