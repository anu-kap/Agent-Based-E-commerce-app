import json
import redis.asyncio as aioredis

SESSION_TTL = 7200
SESSION_FIELDS = ["products", "cart", "order", "automation", "radar"]


async def get_session(session_id: str, redis: aioredis.Redis) -> dict:
    raw = await redis.get(f"session:{session_id}")
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return {field: {} if field in ("order", "automation", "radar") else [] for field in SESSION_FIELDS}


async def save_session(session_id: str, result: dict, redis: aioredis.Redis) -> None:
    data = {field: result.get(field, {} if field in ("order", "automation", "radar") else []) for field in SESSION_FIELDS}
    await redis.setex(f"session:{session_id}", SESSION_TTL, json.dumps(data))
