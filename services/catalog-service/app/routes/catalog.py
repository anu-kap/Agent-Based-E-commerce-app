from fastapi import APIRouter, Depends, Query
import redis.asyncio as aioredis

from ..cache import get_redis
from ..config import Settings, get_settings
from ..models import Product
from ..search import search_catalog

router = APIRouter(prefix="/products")


@router.get("/search", response_model=list[Product])
async def search(
    q: str = Query(default="", description="Search query"),
    max_price: float | None = Query(default=None, description="Maximum price filter"),
    tags: str = Query(default="", description="Comma-separated tags"),
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    redis: aioredis.Redis = await get_redis(settings)
    try:
        return await search_catalog(q, max_price, tag_list, redis, settings)
    finally:
        await redis.aclose()
