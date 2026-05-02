import uuid

from fastapi import APIRouter, Depends

from ..config import Settings, get_settings
from ..models import CheckoutRequest
from .cart import _cart_quote_local
from ..shopify import cart_quote_shopify

router = APIRouter()


@router.post("/checkout")
async def checkout(body: CheckoutRequest, settings: Settings = Depends(get_settings)) -> dict:
    items = [i.model_dump() for i in body.items]
    domain = settings.shopify_store_domain.replace("https://", "").replace("http://", "").strip("/")

    if domain:
        try:
            quote = cart_quote_shopify(domain, items)
            order_id = f"SHOPIFY-CART-{uuid.uuid4().hex[:8].upper()}"
            return {"orderId": order_id, "status": "created", "shippingMethod": body.shipping_method, "quote": quote}
        except Exception:
            pass

    quote = _cart_quote_local(settings.seed_catalog_path, items)
    order_id = "ORD-DEMO-1001"
    return {"orderId": order_id, "status": "created", "shippingMethod": body.shipping_method, "quote": quote}
