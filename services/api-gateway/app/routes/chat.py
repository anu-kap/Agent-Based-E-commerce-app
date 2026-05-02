from fastapi import APIRouter, Depends
from pydantic import BaseModel
import redis.asyncio as aioredis

from ..agent.commerce_agent import CommerceState, run_agent
from ..config import Settings, get_settings
from ..intent_log import log_intent, recent_intents
from ..session import get_session, save_session

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    sessionId: str = "demo"
    selectedSku: str = ""
    products: list = []
    cart: list = []
    order: dict = {}
    automation: dict = {}
    radar: dict = {}
    recentIntents: list = []


@router.post("/api/chat")
async def chat(body: ChatRequest, settings: Settings = Depends(get_settings)) -> dict:
    redis: aioredis.Redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        session = await get_session(body.sessionId, redis)
        log_intent(body.sessionId, body.message, body.selectedSku)
        db_intents = recent_intents(limit=15)

        state: CommerceState = {
            "message": body.message,
            "sessionId": body.sessionId,
            "selectedSku": body.selectedSku,
            "products": session.get("products") or body.products,
            "cart": session.get("cart") or body.cart,
            "order": session.get("order") or body.order,
            "automation": session.get("automation") or body.automation,
            "radar": session.get("radar") or body.radar,
            "recentIntents": db_intents or body.recentIntents,
            "trace": [],
            "_settings": settings,
        }

        result = await run_agent(state)
        await save_session(body.sessionId, result, redis)

        return {
            "reply": result.get("reply", ""),
            "trace": result.get("trace", []),
            "products": result.get("products", []),
            "cart": result.get("cart", []),
            "order": result.get("order", {}),
            "automation": result.get("automation", {}),
            "radar": result.get("radar", {}),
        }
    finally:
        await redis.aclose()
