import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def cache_get(key: str) -> Any | None:
    try:
        client = await get_redis()
        value = await client.get(key)
        if value:
            return json.loads(value)
    except Exception as e:
        logger.warning("Cache GET failed: %s", e)
    return None


async def cache_set(key: str, value: Any, ttl: int = settings.CACHE_TTL) -> None:
    try:
        client = await get_redis()
        await client.setex(key, ttl, json.dumps(value, default=str))
    except Exception as e:
        logger.warning("Cache SET failed: %s", e)


async def cache_delete(key: str) -> None:
    try:
        client = await get_redis()
        await client.delete(key)
    except Exception as e:
        logger.warning("Cache DELETE failed: %s", e)


async def cache_delete_pattern(pattern: str) -> None:
    try:
        client = await get_redis()
        keys = await client.keys(pattern)
        if keys:
            await client.delete(*keys)
    except Exception as e:
        logger.warning("Cache DELETE PATTERN failed: %s", e)


async def close_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
