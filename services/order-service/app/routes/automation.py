import uuid

from fastapi import APIRouter, Depends

from ..config import Settings, get_settings
from ..kestra import trigger_kestra
from ..models import AutomationRequest, AutomationResponse
from ..sqs import publish_order_event

router = APIRouter(prefix="/orders")


@router.post("/{order_id}/automate", response_model=AutomationResponse)
async def automate(order_id: str, body: AutomationRequest, settings: Settings = Depends(get_settings)) -> dict:
    order = body.order or {}
    quote = order.get("quote", {}) if isinstance(order, dict) else {}
    shopify_cart = quote.get("cart", {}) if isinstance(quote, dict) else {}
    total = quote.get("total", 0) if isinstance(quote, dict) else 0
    cart_id = shopify_cart.get("id") if isinstance(shopify_cart, dict) else ""
    checkout_url = quote.get("checkoutUrl", "") if isinstance(quote, dict) else ""
    oid = order.get("orderId") or order_id or f"SHOPIFY-PAID-{uuid.uuid4().hex[:8].upper()}"

    msg_id = publish_order_event("order.paid", {"orderId": oid, "total": total, "sessionId": body.session_id})
    kestra = trigger_kestra(oid, total, "shopify.orders.paid", cart_id, checkout_url)

    return {
        "orderId": oid,
        "status": "paid",
        "source": "shopify_webhook_simulation",
        "total": total,
        "cartId": cart_id or "",
        "checkoutUrl": checkout_url or "",
        "kestraWorkflow": settings.kestra_flow_id,
        "kestra": kestra,
        "sqsMessageId": msg_id,
    }
