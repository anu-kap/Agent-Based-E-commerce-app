import json
from pathlib import Path

from fastapi import APIRouter, Depends

from ..config import Settings, get_settings
from ..models import CartQuoteRequest, CartQuoteResponse
from ..shopify import cart_quote_shopify

router = APIRouter()


def _seed(path: str) -> list[dict]:
    return json.loads(Path(path).read_text())


def _cart_quote_local(seed_path: str, items: list[dict]) -> dict:
    by_sku = {item["sku"]: item for item in _seed(seed_path)}
    lines = []
    subtotal = 0.0
    for entry in items:
        sku = entry["sku"]
        quantity = int(entry.get("quantity", 1))
        product = by_sku.get(sku)
        if not product:
            continue
        line_total = product["price"] * quantity
        subtotal += line_total
        lines.append({"sku": sku, "name": product["name"], "quantity": quantity, "unitPrice": product["price"], "lineTotal": line_total})
    shipping = 0.0 if subtotal >= 100 else 8.0
    tax = round(subtotal * 0.0825, 2)
    return {"lines": lines, "subtotal": subtotal, "shipping": shipping, "tax": tax, "total": round(subtotal + shipping + tax, 2)}


@router.post("/cart/quote", response_model=CartQuoteResponse)
async def quote(body: CartQuoteRequest, settings: Settings = Depends(get_settings)) -> dict:
    items = [i.model_dump() for i in body.items]
    domain = settings.shopify_store_domain.replace("https://", "").replace("http://", "").strip("/")
    if domain:
        try:
            return cart_quote_shopify(domain, items)
        except Exception:
            pass
    return _cart_quote_local(settings.seed_catalog_path, items)
