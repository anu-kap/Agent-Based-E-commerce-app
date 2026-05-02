import json
import redis.asyncio as aioredis
from .config import Settings


async def get_redis(settings: Settings) -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)


async def cache_get(redis: aioredis.Redis, key: str, ttl: int) -> list | None:
    raw = await redis.get(f"catalog:v1:{key}")
    if raw is None:
        return None
    try:
        entry = json.loads(raw)
        return entry.get("data")
    except (json.JSONDecodeError, AttributeError):
        return None


async def cache_get_stale(redis: aioredis.Redis, key: str) -> list | None:
    raw = await redis.get(f"catalog:v1:stale:{key}")
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def cache_put(redis: aioredis.Redis, key: str, data: list, ttl: int) -> None:
    payload = json.dumps({"data": data})
    await redis.setex(f"catalog:v1:{key}", ttl, payload)
    await redis.set(f"catalog:v1:stale:{key}", json.dumps(data))
