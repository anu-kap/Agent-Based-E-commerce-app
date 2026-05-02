import json
import uuid
from urllib.request import Request, urlopen


def post_json(url: str, payload: dict, timeout: int = 12) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def shopify_mcp_call(domain: str, name: str, arguments: dict) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "id": str(uuid.uuid4()),
        "params": {"name": name, "arguments": arguments},
    }
    return post_json(f"https://{domain}/api/mcp", payload)


def content_payload(response: dict) -> dict:
    if "error" in response:
        raise RuntimeError(response["error"].get("message", "Shopify MCP error"))
    result = response.get("result", {})
    if "structuredContent" in result:
        return result["structuredContent"]
    content = result.get("content", [])
    if content and isinstance(content, list):
        first = content[0]
        if "json" in first:
            return first["json"]
        if "text" in first:
            try:
                return json.loads(first["text"])
            except json.JSONDecodeError:
                return {"text": first["text"]}
    return result


def _first(source, *keys, default=None):
    for k in keys:
        if isinstance(source, dict) and source.get(k) is not None:
            return source[k]
    return default


def _normalize_price(value) -> float:
    if isinstance(value, dict):
        value = _first(value, "amount", "value", "price", default=0)
    if isinstance(value, str):
        value = value.replace("$", "").replace(",", "")
    try:
        p = float(value)
        return p / 100 if p >= 1000 else p
    except (TypeError, ValueError):
        return 0


def cart_quote_shopify(domain: str, items: list[dict]) -> dict:
    lines = [
        {"product_variant_id": item.get("merchandise_id") or item["sku"], "quantity": int(item.get("quantity", 1))}
        for item in items
        if item.get("merchandise_id") or item.get("sku")
    ]
    response = shopify_mcp_call(domain, "update_cart", {"add_items": lines})
    payload = content_payload(response)
    cart = payload.get("cart", payload) if isinstance(payload, dict) else {}
    cost = _first(cart, "cost", default={})
    total_amount = _first(cost, "total_amount", "totalAmount", default={})
    return {
        "source": "shopify",
        "cart": cart,
        "checkoutUrl": _first(cart, "checkoutUrl", "checkout_url", default=""),
        "total": _normalize_price(_first(total_amount, "amount", default=_first(cart, "totalAmount", "total", default=0))),
        "lines": lines,
    }
