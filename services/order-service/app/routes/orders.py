import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends

from ..config import Settings, get_settings
from ..db import save_order
from ..models import OrderRequest, OrderResponse
from ..sqs import publish_order_event

router = APIRouter(prefix="/orders")


def _seed(path: str) -> list[dict]:
    return json.loads(Path(path).read_text())


def _cart_quote_local(seed_path: str, items: list[dict]) -> dict:
    by_sku = {item["sku"]: item for item in _seed(seed_path)}
    lines = []
    subtotal = 0.0
    for entry in items:
        product = by_sku.get(entry["sku"])
        if not product:
            continue
        qty = int(entry.get("quantity", 1))
        line_total = product["price"] * qty
        subtotal += line_total
        lines.append({"sku": entry["sku"], "name": product["name"], "quantity": qty, "unitPrice": product["price"], "lineTotal": line_total})
    shipping = 0.0 if subtotal >= 100 else 8.0
    tax = round(subtotal * 0.0825, 2)
    return {"lines": lines, "subtotal": subtotal, "shipping": shipping, "tax": tax, "total": round(subtotal + shipping + tax, 2)}


@router.post("", response_model=OrderResponse)
async def create_order(body: OrderRequest, settings: Settings = Depends(get_settings)) -> dict:
    items = [i.model_dump() for i in body.items]
    quote = _cart_quote_local("/app/data/seed_catalog.json", items)
    order_id = f"ORD-DEMO-{uuid.uuid4().hex[:6].upper()}"
    order = {
        "orderId": order_id,
        "status": "created",
        "shippingMethod": body.shipping_method,
        "quote": quote,
        "kestraWorkflow": settings.kestra_flow_id,
    }
    save_order(order, session_id=body.session_id)
    publish_order_event("order.created", {"orderId": order_id, "total": quote.get("total", 0), "sessionId": body.session_id})
    return order
