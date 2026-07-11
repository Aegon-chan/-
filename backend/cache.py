"""Caching layer with Redis backend and in-memory fallback.

Usage:
    from backend.cache import cache

    # Set with TTL
    cache.set("my_key", {"data": 42}, ttl=300)

    # Get
    value = cache.get("my_key")

    # Decorator
    @cache.cached(ttl=60)
    def expensive_function(arg1, arg2):
        ...
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any, Callable, Optional

logger = logging.getLogger("research_agent.cache")

# ---------------------------------------------------------------------------
# In-memory fallback (used when Redis is unavailable)
# ---------------------------------------------------------------------------

class _MemoryCache:
    """Thread-safe in-memory cache with TTL."""

    def __init__(self):
        self._store: dict[str, tuple[float, Any]] = {}
        self._cleanup_interval = 300  # 5 min
        self._last_cleanup = time.time()

    def get(self, key: str) -> Optional[Any]:
        self._maybe_cleanup()
        entry = self._store.get(key)
        if entry is None:
            return None
        expires, value = entry
        if expires and time.time() > expires:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        expires = time.time() + ttl if ttl else 0
        self._store[key] = (expires, value)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def _maybe_cleanup(self):
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now
        expired = [k for k, (e, _) in self._store.items() if e and now > e]
        for k in expired:
            del self._store[k]

    def stats(self) -> dict:
        return {
            "backend": "memory",
            "entries": len(self._store),
        }


# ---------------------------------------------------------------------------
# Redis backend (optional, requires redis-py)
# ---------------------------------------------------------------------------

class _RedisCache:
    """Redis-backed cache with connection pooling."""

    def __init__(self, redis_url: str = ""):
        self._redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._client: Any = None
        self._connected = False

    def _connect(self) -> bool:
        if self._connected:
            return True
        try:
            import redis.asyncio as aioredis
            self._client = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            self._connected = True
            logger.info("Connected to Redis at %s", self._redis_url)
            return True
        except ImportError:
            logger.warning("redis-py not installed; falling back to memory cache")
            return False
        except Exception as e:
            logger.warning("Redis connection failed: %s", e)
            return False

    def get(self, key: str) -> Optional[Any]:
        if not self._connect():
            return None
        try:
            import asyncio
            raw = asyncio.run(self._client.get(key))
            return json.loads(raw) if raw else None
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        if not self._connect():
            return
        try:
            import asyncio
            asyncio.run(self._client.setex(key, ttl, json.dumps(value)))
        except Exception:
            pass

    def delete(self, key: str) -> None:
        if not self._connect():
            return
        try:
            import asyncio
            asyncio.run(self._client.delete(key))
        except Exception:
            pass

    def clear(self) -> None:
        if not self._connect():
            return
        try:
            import asyncio
            asyncio.run(self._client.flushdb())
        except Exception:
            pass

    def stats(self) -> dict:
        return {"backend": "redis" if self._connected else "redis(disconnected)"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class Cache:
    """Unified cache interface: Redis if available, else in-memory."""

    def __init__(self):
        self._redis = _RedisCache()
        self._memory = _MemoryCache()
        self._use_redis = self._redis._connect() if not os.getenv("CACHE_DISABLE_REDIS") else False

    def get(self, key: str) -> Optional[Any]:
        if self._use_redis:
            val = self._redis.get(key)
            if val is not None:
                return val
        return self._memory.get(key)

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        if self._use_redis:
            self._redis.set(key, value, ttl)
        self._memory.set(key, value, ttl)

    def delete(self, key: str) -> None:
        if self._use_redis:
            self._redis.delete(key)
        self._memory.delete(key)

    def clear(self) -> None:
        if self._use_redis:
            self._redis.clear()
        self._memory.clear()

    def stats(self) -> dict:
        return {
            "primary": self._redis.stats() if self._use_redis else self._memory.stats(),
            "fallback": self._memory.stats(),
        }

    def cached(self, ttl: int = 300, key_prefix: str = ""):
        """Decorator: cache function return values."""
        def decorator(func: Callable) -> Callable:
            def wrapper(*args, **kwargs) -> Any:
                key_parts = [key_prefix or func.__name__]
                if args:
                    key_parts.append(str(args))
                if kwargs:
                    key_parts.append(str(sorted(kwargs.items())))
                cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
                cached = self.get(cache_key)
                if cached is not None:
                    logger.debug("Cache hit: %s", cache_key)
                    return cached
                result = func(*args, **kwargs)
                self.set(cache_key, result, ttl)
                logger.debug("Cache set: %s", cache_key)
                return result
            return wrapper
        return decorator


# Singleton
cache = Cache()
