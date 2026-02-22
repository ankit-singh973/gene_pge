"""
Redis-backed cache with an in-memory dict fallback when Redis is unavailable.
"""
from __future__ import annotations

import json
import time
from typing import Any, Optional

import redis

from core.config import get_settings
from core.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()
# Cache prefix for versioning
CACHE_PREFIX = "gene_summary:v2"


class CacheService:
    def __init__(self) -> None:
        self._redis: Optional[redis.Redis] = None
        self._memory: dict[str, tuple[Any, float]] = {}  # key → (value, expire_at)
        self._connect()

    def _connect(self) -> None:
        try:
            self._redis = redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)
            self._redis.ping()
            logger.info("Redis cache connected", extra={"backend": "redis"})
        except Exception as exc:
            logger.warning(
                "Redis unavailable – falling back to in-memory cache",
                extra={"error": str(exc)},
            )
            self._redis = None

    # ------------------------------------------------------------------ #

    def _key(self, gene_symbol: str) -> str:
        return f"{CACHE_PREFIX}{gene_symbol.upper()}"

    def get(self, gene_symbol: str) -> Optional[dict]:
        key = self._key(gene_symbol)

        if self._redis:
            try:
                raw = self._redis.get(key)
                if raw:
                    return json.loads(raw)
            except Exception as exc:
                logger.warning("Redis GET error", extra={"error": str(exc)})
                self._redis = None  # fall through to memory

        # In-memory fallback
        if key in self._memory:
            value, expire_at = self._memory[key]
            if time.time() < expire_at:
                return value
            del self._memory[key]
        return None

    def set(self, gene_symbol: str, data: dict, ttl: int = settings.cache_ttl) -> None:
        key = self._key(gene_symbol)
        serialized = json.dumps(data)

        if self._redis:
            try:
                self._redis.setex(key, ttl, serialized)
                return
            except Exception as exc:
                logger.warning("Redis SET error", extra={"error": str(exc)})
                self._redis = None

        # In-memory fallback
        self._memory[key] = (data, time.time() + ttl)

    def delete(self, gene_symbol: str) -> None:
        key = self._key(gene_symbol)
        if self._redis:
            try:
                self._redis.delete(key)
            except Exception:
                pass
        self._memory.pop(key, None)

    def get_raw(self, key: str) -> Optional[dict]:
        if self._redis:
            try:
                raw = self._redis.get(key)
                if raw:
                    return json.loads(raw)
            except Exception as exc:
                logger.warning("Redis GET error", extra={"error": str(exc)})
                self._redis = None

        if key in self._memory:
            value, expire_at = self._memory[key]
            if time.time() < expire_at:
                return value
            del self._memory[key]
        return None

    def set_raw(self, key: str, data: dict, ttl: int = settings.cache_ttl) -> None:
        serialized = json.dumps(data)
        if self._redis:
            try:
                self._redis.setex(key, ttl, serialized)
                return
            except Exception as exc:
                logger.warning("Redis SET error", extra={"error": str(exc)})
                self._redis = None

        self._memory[key] = (data, time.time() + ttl)


# Singleton instance
cache_service = CacheService()
