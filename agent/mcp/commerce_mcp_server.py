#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "data" / "catalog.json"


def catalog():
    return json.loads(CATALOG_PATH.read_text())


def search_catalog(query="", max_price=None, tags=None):
    terms = {term.lower() for term in str(query).replace(",", " ").split() if len(term) > 2}
    desired_tags = {tag.lower() for tag in (tags or [])}
    results = []

    for item in catalog():
        haystack = " ".join([
            item["name"],
            item["category"],
            item["description"],
            " ".join(item["tags"])
        ]).lower()
        if max_price is not None and item["price"] > float(max_price):
            continue
        score = sum(1 for term in terms if term in haystack)
        score += sum(2 for tag in desired_tags if tag in item["tags"])
        if score or not terms:
            results.append({**item, "matchScore": score})

    return sorted(results, key=lambda item: (-item["matchScore"], -item["rating"], item["price"]))[:5]


def cart_quote(items):
    by_sku = {item["sku"]: item for item in catalog()}
    lines = []
    subtotal = 0
    for entry in items:
        sku = entry["sku"]
        quantity = int(entry.get("quantity", 1))
        product = by_sku.get(sku)
        if not product:
            continue
        line_total = product["price"] * quantity
        subtotal += line_total
        lines.append({
            "sku": sku,
            "name": product["name"],
            "quantity": quantity,
            "unitPrice": product["price"],
            "lineTotal": line_total
        })
    shipping = 0 if subtotal >= 100 else 8
    tax = round(subtotal * 0.0825, 2)
    return {
        "lines": lines,
        "subtotal": subtotal,
        "shipping": shipping,
        "tax": tax,
        "total": round(subtotal + shipping + tax, 2)
    }


def create_order(items, shipping_method="standard"):
    quote = cart_quote(items)
    return {
        "orderId": "ORD-DEMO-1001",
        "status": "created",
        "shippingMethod": shipping_method,
        "quote": quote,
        "kestraWorkflow": "chat-commerce-order-fulfillment"
    }


TOOLS = {
    "search_catalog": {
        "description": "Search ecommerce catalog by query, budget, and product tags.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_price": {"type": "number"},
                "tags": {"type": "array", "items": {"type": "string"}}
            }
        },
        "handler": search_catalog
    },
    "cart_quote": {
        "description": "Calculate cart subtotal, tax, shipping, and total.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "items": {"type": "array"}
            },
            "required": ["items"]
        },
        "handler": cart_quote
    },
    "create_order": {
        "description": "Create a demo order and return the Kestra fulfillment workflow hook.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "items": {"type": "array"},
                "shipping_method": {"type": "string"}
            },
            "required": ["items"]
        },
        "handler": create_order
    }
}


def respond(message_id, result=None, error=None):
    payload = {"jsonrpc": "2.0", "id": message_id}
    if error:
        payload["error"] = {"code": -32000, "message": error}
    else:
        payload["result"] = result
    print(json.dumps(payload), flush=True)


def handle(message):
    method = message.get("method")
    params = message.get("params") or {}
    message_id = message.get("id")

    if method == "initialize":
        respond(message_id, {"protocolVersion": "2024-11-05", "serverInfo": {"name": "commerce-mcp", "version": "0.1.0"}})
    elif method == "tools/list":
        respond(message_id, {"tools": [
            {"name": name, "description": tool["description"], "inputSchema": tool["inputSchema"]}
            for name, tool in TOOLS.items()
        ]})
    elif method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        tool = TOOLS.get(name)
        if not tool:
            respond(message_id, error=f"Unknown tool: {name}")
            return
        result = tool["handler"](**arguments)
        respond(message_id, {"content": [{"type": "json", "json": result}]})
    else:
        respond(message_id, error=f"Unsupported method: {method}")


def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            handle(json.loads(line))
        except Exception as exc:
            respond(None, error=str(exc))


if __name__ == "__main__":
    main()
