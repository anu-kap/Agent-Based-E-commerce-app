#!/usr/bin/env python3
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agent import db  # noqa: E402  -- optional Postgres cache + persistence

SEED_CATALOG_PATH = ROOT / "data" / "seed_catalog.json"
SHOPIFY_STORE_DOMAIN = os.getenv("SHOPIFY_STORE_DOMAIN", "").replace("https://", "").replace("http://", "").strip("/")
KESTRA_URL = os.getenv("KESTRA_URL", "http://localhost:8080").rstrip("/")
KESTRA_NAMESPACE = os.getenv("KESTRA_NAMESPACE", "demo.commerce")
KESTRA_FLOW_ID = os.getenv("KESTRA_FLOW_ID", "chat-commerce-order-fulfillment")
KESTRA_RADAR_FLOW_ID = os.getenv("KESTRA_RADAR_FLOW_ID", "campus-demand-radar")
COE_EVENTS_URL = "https://www.coe.edu/why-coe/events/calendar"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast?latitude=41.9779&longitude=-91.6656&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max&temperature_unit=fahrenheit&timezone=America%2FChicago&forecast_days=7"
CACHE_TTL_SECONDS = int(os.getenv("CATALOG_CACHE_TTL_SECONDS", "3600"))


def seed_catalog():
    return json.loads(SEED_CATALOG_PATH.read_text())


def post_json(url, payload, headers=None, timeout=12):
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST"
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get_json(url, timeout=12):
    request = Request(url, headers={"User-Agent": "CampusDemandRadar/0.1"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get_text(url, timeout=12):
    request = Request(url, headers={"User-Agent": "CampusDemandRadar/0.1"})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def shopify_mcp_call(name, arguments):
    if not SHOPIFY_STORE_DOMAIN:
        raise RuntimeError("SHOPIFY_STORE_DOMAIN is not configured")
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "id": str(uuid.uuid4()),
        "params": {"name": name, "arguments": arguments}
    }
    return post_json(f"https://{SHOPIFY_STORE_DOMAIN}/api/mcp", payload)


def content_payload(response):
    if "error" in response:
        raise RuntimeError(response["error"].get("message", "Shopify MCP request failed"))
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


def collect_product_like(value):
    if isinstance(value, list):
        items = []
        for entry in value:
            items.extend(collect_product_like(entry))
        return items
    if isinstance(value, dict):
        keys = {key.lower() for key in value}
        if {"title", "name"} & keys and any(key in keys for key in ["price", "variants", "variant_id", "variantid", "url"]):
            return [value]
        items = []
        for child in value.values():
            items.extend(collect_product_like(child))
        return items
    return []


def first_present(source, *keys, default=None):
    for key in keys:
        if isinstance(source, dict) and source.get(key) is not None:
            return source[key]
    return default


def normalize_price(value):
    if isinstance(value, dict):
        value = first_present(value, "amount", "value", "price", default=0)
    if isinstance(value, str):
        value = value.replace("$", "").replace(",", "")
    try:
        price = float(value)
        return price / 100 if price >= 1000 else price
    except (TypeError, ValueError):
        return 0


def normalize_description(value):
    if isinstance(value, dict):
        return first_present(value, "html", "text", default="")
    return value or ""


def media_url(source):
    media = source.get("media") if isinstance(source, dict) else None
    if isinstance(media, list) and media:
        return first_present(media[0], "url", "src", default="")
    image = first_present(source, "image_url", "imageUrl", "featuredImage", default="")
    if isinstance(image, dict):
        return first_present(image, "url", "src", default="")
    return image


def normalize_shopify_product(item):
    variants = item.get("variants") if isinstance(item.get("variants"), list) else []
    variant = variants[0] if variants else {}
    price_range = first_present(item, "price_range", "priceRange", default={})
    min_price = first_present(price_range, "min", "minimum", default={})
    price = normalize_price(first_present(item, "price", "amount", default=first_present(variant, "price", default=min_price)))
    variant_id = first_present(item, "variant_id", "variantId", "merchandise_id", "merchandiseId", default=first_present(variant, "id", "variant_id"))
    currency = first_present(item, "currency", "currencyCode", default=first_present(first_present(variant, "price", default={}), "currency", "currencyCode", default=first_present(min_price, "currency", default="")))
    return {
        "sku": variant_id or first_present(item, "id", "product_id", "productId", default="SHOPIFY-RESULT"),
        "name": first_present(item, "name", "title", default="Shopify product"),
        "category": first_present(item, "productType", "category", default="shopify"),
        "price": price,
        "currency": currency,
        "inventory": first_present(item, "availableForSale", "inventory", default="available"),
        "rating": first_present(item, "rating", default=""),
        "tags": first_present(item, "tags", default=[]),
        "description": normalize_description(first_present(item, "description", "descriptionHtml", default="")),
        "url": first_present(item, "url", "onlineStoreUrl", "productUrl", default=""),
        "imageUrl": media_url(item) or media_url(variant),
        "source": "shopify",
        "raw": item
    }


def search_shopify_catalog(query):
    try:
        response = shopify_mcp_call("search_catalog", {
            "catalog": {
                "query": query,
                "context": {"intent": "Customer is shopping through an AI commerce assistant.", "currency": "USD"},
                "pagination": {"limit": 5}
            }
        })
    except RuntimeError:
        response = shopify_mcp_call("search_shop_catalog", {"query": query, "context": "Customer is shopping through an AI commerce assistant."})
    payload = content_payload(response)
    products = [normalize_shopify_product(item) for item in collect_product_like(payload)]
    return products[:5]


def _cache_key(query, max_price, tags):
    return json.dumps(
        {
            "shop": SHOPIFY_STORE_DOMAIN or "seed",
            "q": str(query or "").lower().strip(),
            "max_price": max_price if max_price is not None else None,
            "tags": sorted(tag.lower() for tag in (tags or [])),
        },
        sort_keys=True,
    )


def _search_seed_catalog(query, max_price, tags):
    terms = {term.lower() for term in str(query).replace(",", " ").split() if len(term) > 2}
    desired_tags = {tag.lower() for tag in (tags or [])}
    results = []

    for item in seed_catalog():
        haystack = " ".join([
            item["name"],
            item["category"],
            item["description"],
            " ".join(item["tags"]),
        ]).lower()
        if max_price is not None and item["price"] > float(max_price):
            continue
        score = sum(1 for term in terms if term in haystack)
        score += sum(2 for tag in desired_tags if tag in item["tags"])
        if score or not terms:
            results.append({**item, "matchScore": score, "source": "seed"})

    return sorted(results, key=lambda item: (-item["matchScore"], -item["rating"], item["price"]))[:5]


def search_catalog(query="", max_price=None, tags=None):
    """Find products. Live Shopify (when configured) is primary, with a
    Postgres cache in front and the seed catalog as last-resort fallback.

    Order of attempts when SHOPIFY_STORE_DOMAIN is set:
      1. Fresh cache hit (< CATALOG_CACHE_TTL_SECONDS)
      2. Shopify Storefront MCP (writes the response to cache on success)
      3. Stale cache (any age) if Shopify is unreachable
      4. Seed catalog (data/seed_catalog.json)

    With no SHOPIFY_STORE_DOMAIN, the seed catalog is the source of truth.
    """
    key = _cache_key(query, max_price, tags)

    if SHOPIFY_STORE_DOMAIN:
        cached, _ = db.cache_get(key, max_age_seconds=CACHE_TTL_SECONDS)
        if cached is not None:
            return cached
        try:
            products = search_shopify_catalog(query)
            if products:
                db.cache_put(key, products)
                return products
        except Exception:
            pass
        stale = db.cache_get_stale(key)
        if stale:
            return stale

    return _search_seed_catalog(query, max_price, tags)


def cart_quote(items):
    if SHOPIFY_STORE_DOMAIN:
        lines = []
        for item in items:
            merchandise_id = item.get("merchandise_id") or item.get("sku")
            if merchandise_id:
                lines.append({"product_variant_id": merchandise_id, "quantity": int(item.get("quantity", 1))})
        response = shopify_mcp_call("update_cart", {"add_items": lines})
        payload = content_payload(response)
        cart = payload.get("cart", payload) if isinstance(payload, dict) else {}
        cost = first_present(cart, "cost", default={})
        total_amount = first_present(cost, "total_amount", "totalAmount", default={})
        return {
            "source": "shopify",
            "cart": cart,
            "checkoutUrl": first_present(cart, "checkoutUrl", "checkout_url", default=""),
            "total": normalize_price(first_present(total_amount, "amount", default=first_present(cart, "totalAmount", "total", default=0))),
            "lines": lines
        }

    by_sku = {item["sku"]: item for item in seed_catalog()}
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


def trigger_kestra(order_id, total, workflow_event, cart_id="", checkout_url="", flow_id=None):
    flow_id = flow_id or KESTRA_FLOW_ID
    data = urlencode({
        "orderId": order_id,
        "total": str(total),
        "workflowEvent": workflow_event,
        "cartId": cart_id,
        "checkoutUrl": checkout_url
    }).encode("utf-8")
    request = Request(
        f"{KESTRA_URL}/api/v1/main/executions/{KESTRA_NAMESPACE}/{flow_id}",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST"
    )
    try:
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return {
                "status": "triggered",
                "executionId": payload.get("id"),
                "url": f"{KESTRA_URL}/ui/executions/{payload.get('id')}" if payload.get("id") else KESTRA_URL,
                "workflowEvent": workflow_event,
                "flowId": flow_id
            }
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": str(exc), "url": KESTRA_URL, "workflowEvent": workflow_event, "flowId": flow_id}


def create_order(items, shipping_method="standard", session_id="demo"):
    quote = cart_quote(items)
    order_id = "ORD-DEMO-1001" if quote.get("source") != "shopify" else f"SHOPIFY-CART-{uuid.uuid4().hex[:8].upper()}"
    order = {
        "orderId": order_id,
        "status": "created",
        "shippingMethod": shipping_method,
        "quote": quote,
        "kestraWorkflow": KESTRA_FLOW_ID,
    }
    if quote.get("source") != "shopify":
        db.save_order(order, session_id=session_id)
    return order


def post_order_automation(order=None, cart=None, session_id="demo"):
    order = order or {}
    quote = order.get("quote", {})
    shopify_cart = quote.get("cart", {}) if isinstance(quote, dict) else {}
    total = quote.get("total", 0) if isinstance(quote, dict) else 0
    cart_id = shopify_cart.get("id") if isinstance(shopify_cart, dict) else ""
    checkout_url = quote.get("checkoutUrl", "") if isinstance(quote, dict) else ""
    order_id = order.get("orderId") or f"SHOPIFY-PAID-{uuid.uuid4().hex[:8].upper()}"

    return {
        "orderId": order_id,
        "status": "paid",
        "source": "shopify_webhook_simulation",
        "sessionId": session_id,
        "total": total,
        "cartId": cart_id,
        "checkoutUrl": checkout_url,
        "kestraWorkflow": KESTRA_FLOW_ID,
        "kestra": trigger_kestra(order_id, total, "shopify.orders.paid", cart_id, checkout_url)
    }


def compact_text(html):
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def campus_events_signal():
    try:
        text = compact_text(get_text(COE_EVENTS_URL, timeout=5))
        keywords = ["graduation", "alumni", "homecoming", "athletics", "family", "orientation", "student", "admission"]
        hits = []
        for keyword in keywords:
            match = re.search(r"([A-Z][a-z]{2}\d{2}[^.]{0,140}" + keyword + r"[^.]{0,160})", text, flags=re.I)
            if match:
                hits.append(match.group(1).strip())
        return {
            "status": "live",
            "source": COE_EVENTS_URL,
            "signals": hits[:4] or ["Upcoming campus events detected on Coe calendar."],
            "keywords": [keyword for keyword in keywords if keyword in text.lower()]
        }
    except Exception as exc:
        return {
            "status": "fallback",
            "source": COE_EVENTS_URL,
            "signals": ["Could not read live Coe calendar; using campus retail season defaults."],
            "keywords": ["alumni", "student", "athletics"],
            "error": str(exc)
        }


def weather_signal():
    try:
        data = get_json(OPEN_METEO_URL, timeout=5)
        daily = data.get("daily", {})
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])
        precip = daily.get("precipitation_probability_max", [])
        avg_high = round(sum(max_temps) / len(max_temps), 1) if max_temps else None
        cold_days = sum(1 for value in max_temps if value is not None and value < 55)
        rain_days = sum(1 for value in precip if value is not None and value >= 40)
        signals = []
        if cold_days:
            signals.append(f"{cold_days} cool days in Cedar Rapids forecast; feature hoodies and fleece.")
        if rain_days:
            signals.append(f"{rain_days} higher-rain-probability days; feature outerwear and pickup-ready items.")
        if not signals and avg_high:
            signals.append(f"Average high near {avg_high}F; feature lighter tees, hats, and drinkware.")
        return {
            "status": "live",
            "source": "https://open-meteo.com/",
            "avgHighF": avg_high,
            "minLowF": min(min_temps) if min_temps else None,
            "rainDays": rain_days,
            "signals": signals
        }
    except Exception as exc:
        return {
            "status": "fallback",
            "source": "https://open-meteo.com/",
            "signals": ["Weather unavailable; defaulting to hoodie, hat, and drinkware opportunities."],
            "error": str(exc)
        }


def intent_signal(recent_intents=None):
    recent_intents = recent_intents or []
    text = " ".join(entry.get("message", "") for entry in recent_intents).lower()
    buckets = {
        "alumni": ["alum", "alumni"],
        "hoodie": ["hoodie", "fleece", "cold"],
        "gift": ["gift", "parent", "family"],
        "drinkware": ["mug", "bottle", "drink"],
        "pickup": ["pickup", "today", "tomorrow", "weekend"]
    }
    counts = {
        name: sum(text.count(term) for term in terms)
        for name, terms in buckets.items()
    }
    ranked = [name for name, count in sorted(counts.items(), key=lambda item: -item[1]) if count]
    return {
        "status": "live" if recent_intents else "seeded",
        "source": "in-app shopper intent log",
        "topIntents": ranked[:5] or ["alumni", "hoodie", "gift"],
        "sampleCount": len(recent_intents),
        "signals": [
            f"{len(recent_intents)} recent chat turns analyzed.",
            "Top inferred demand: " + ", ".join(ranked[:3] or ["alumni", "hoodie", "gift"])
        ]
    }


def product_signal(queries):
    recommendations = []
    gaps = []
    for query in queries:
        try:
            matches = search_catalog(query)
            if matches:
                recommendations.append({"query": query, "product": matches[0]})
            else:
                gaps.append(f"No strong Shopify match for '{query}'.")
        except Exception as exc:
            gaps.append(f"Could not search Shopify for '{query}': {exc}")
    return {
        "status": "live" if recommendations else "partial",
        "source": f"https://{SHOPIFY_STORE_DOMAIN}/api/mcp" if SHOPIFY_STORE_DOMAIN else "local catalog",
        "recommendations": recommendations[:5],
        "products": [item["product"] for item in recommendations[:5]],
        "gaps": gaps[:4]
    }


def campus_demand_radar(recent_intents=None, focus="homecoming week"):
    events = campus_events_signal()
    weather = weather_signal()
    intents = intent_signal(recent_intents)
    query_terms = []

    joined_signals = " ".join(events.get("keywords", []) + intents.get("topIntents", []) + weather.get("signals", [])).lower()
    if "hoodie" in joined_signals or "cool" in joined_signals or "cold" in joined_signals:
        query_terms.append("hoodie")
    if "alumni" in joined_signals or "alum" in joined_signals:
        query_terms.append("alumni")
    if "gift" in joined_signals or "family" in joined_signals:
        query_terms.append("gift")
    if "rain" in joined_signals:
        query_terms.append("hat")
    if "drinkware" in joined_signals or "mug" in joined_signals:
        query_terms.append("mug")
    query_terms.extend(["hoodie", "alumni gift", "campus mug"])
    deduped_queries = list(dict.fromkeys(query_terms))[:3]
    products = product_signal(deduped_queries)

    actions = []
    if any("hoodie" in query for query in deduped_queries):
        actions.append("Feature hoodies/fleece in the concierge this week and check sizes before event traffic.")
    if "alumni" in " ".join(deduped_queries):
        actions.append("Create an alumni gift bundle: hoodie or tee plus license plate/drinkware.")
    if products.get("gaps"):
        actions.append("Review missed product gaps and decide whether to add substitutes or merchandising copy.")
    actions.append("Send daily event-week demand report to store staff with top searches and recommended products.")

    report_id = f"RADAR-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    kestra = trigger_kestra(
        report_id,
        len(products.get("products", [])),
        "campus.demand_radar",
        flow_id=KESTRA_RADAR_FLOW_ID
    )
    return {
        "reportId": report_id,
        "focus": focus,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "signals": {
            "events": events,
            "weather": weather,
            "intent": intents,
            "products": products
        },
        "actions": actions,
        "featuredProducts": products.get("products", []),
        "sourceSummary": [
            {"name": "Coe events", "status": events.get("status"), "url": events.get("source")},
            {"name": "Cedar Rapids weather", "status": weather.get("status"), "url": weather.get("source")},
            {"name": "Shopper intent", "status": intents.get("status"), "url": "local session intent log"},
            {"name": "Shopify MCP", "status": products.get("status"), "url": products.get("source")}
        ],
        "kestraWorkflow": KESTRA_RADAR_FLOW_ID,
        "kestra": kestra
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
        "description": "Create a local demo order. Shopify checkout should use Shopify instead.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "items": {"type": "array"},
                "shipping_method": {"type": "string"}
            },
            "required": ["items"]
        },
        "handler": create_order
    },
    "post_order_automation": {
        "description": "Simulate a Shopify order-paid webhook and trigger Kestra post-order automation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "order": {"type": "object"},
                "cart": {"type": "array"},
                "session_id": {"type": "string"}
            }
        },
        "handler": post_order_automation
    },
    "campus_demand_radar": {
        "description": "Run a web + Shopify + shopper-intent campus demand radar scan and prepare Kestra merchant actions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "recent_intents": {"type": "array"},
                "focus": {"type": "string"}
            }
        },
        "handler": campus_demand_radar
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
