import hashlib
import json
import re
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import redis.asyncio as aioredis

from .cache import cache_get, cache_get_stale, cache_put
from .config import Settings


def _load_seed(path: str) -> list[dict]:
    return json.loads(Path(path).read_text())


def _cache_key(query: str, max_price: float | None, tags: list[str]) -> str:
    raw = json.dumps(
        {"q": str(query or "").lower().strip(), "max_price": max_price, "tags": sorted(t.lower() for t in (tags or []))},
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _search_seed(seed_path: str, query: str, max_price: float | None, tags: list[str]) -> list[dict]:
    terms = {t.lower() for t in str(query).replace(",", " ").split() if len(t) > 2}
    desired_tags = {t.lower() for t in (tags or [])}
    results = []
    for item in _load_seed(seed_path):
        if max_price is not None and item["price"] > float(max_price):
            continue
        haystack = " ".join([item["name"], item.get("category", ""), item.get("description", ""), " ".join(item.get("tags", []))]).lower()
        score = sum(1 for t in terms if t in haystack)
        score += sum(2 for tag in desired_tags if tag in item.get("tags", []))
        if score or not terms:
            results.append({**item, "matchScore": score, "source": "seed"})
    return sorted(results, key=lambda x: (-x["matchScore"], -x.get("rating", 0), x["price"]))[:5]


def _post_json(url: str, payload: dict, timeout: int = 12) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _content_payload(response: dict) -> dict:
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


def _collect_product_like(value) -> list[dict]:
    if isinstance(value, list):
        items = []
        for entry in value:
            items.extend(_collect_product_like(entry))
        return items
    if isinstance(value, dict):
        keys = {k.lower() for k in value}
        if {"title", "name"} & keys and any(k in keys for k in ["price", "variants", "variant_id", "url"]):
            return [value]
        items = []
        for child in value.values():
            items.extend(_collect_product_like(child))
        return items
    return []


def _first(source: dict, *keys, default=None):
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


def _media_url(source: dict) -> str:
    media = source.get("media") if isinstance(source, dict) else None
    if isinstance(media, list) and media:
        return _first(media[0], "url", "src", default="")
    image = _first(source, "image_url", "imageUrl", "featuredImage", default="")
    if isinstance(image, dict):
        return _first(image, "url", "src", default="")
    return image or ""


def normalize_shopify_product(item: dict) -> dict:
    variants = item.get("variants") if isinstance(item.get("variants"), list) else []
    variant = variants[0] if variants else {}
    price_range = _first(item, "price_range", "priceRange", default={})
    min_price = _first(price_range, "min", "minimum", default={})
    price = _normalize_price(_first(item, "price", "amount", default=_first(variant, "price", default=min_price)))
    variant_id = _first(item, "variant_id", "variantId", "merchandise_id", default=_first(variant, "id", "variant_id"))
    currency = _first(item, "currency", "currencyCode", default=_first(_first(variant, "price", default={}), "currency", "currencyCode", default=_first(min_price, "currency", default="")))
    desc = _first(item, "description", "descriptionHtml", default="")
    if isinstance(desc, dict):
        desc = _first(desc, "html", "text", default="")
    return {
        "sku": variant_id or _first(item, "id", "product_id", default="SHOPIFY-RESULT"),
        "name": _first(item, "name", "title", default="Shopify product"),
        "category": _first(item, "productType", "category", default="shopify"),
        "price": price,
        "currency": currency,
        "inventory": _first(item, "availableForSale", "inventory", default="available"),
        "rating": _first(item, "rating", default=""),
        "tags": _first(item, "tags", default=[]),
        "description": desc or "",
        "url": _first(item, "url", "onlineStoreUrl", "productUrl", default=""),
        "imageUrl": _media_url(item) or _media_url(variant),
        "source": "shopify",
    }


def _search_shopify(domain: str, query: str) -> list[dict]:
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "id": str(uuid.uuid4()),
        "params": {
            "name": "search_catalog",
            "arguments": {
                "catalog": {
                    "query": query,
                    "context": {"intent": "Customer is shopping through an AI commerce assistant.", "currency": "USD"},
                    "pagination": {"limit": 5},
                }
            },
        },
    }
    try:
        response = _post_json(f"https://{domain}/api/mcp", payload)
    except Exception:
        alt_payload = {**payload, "params": {"name": "search_shop_catalog", "arguments": {"query": query, "context": "Customer is shopping through an AI commerce assistant."}}}
        response = _post_json(f"https://{domain}/api/mcp", alt_payload)
    products = [normalize_shopify_product(item) for item in _collect_product_like(_content_payload(response))]
    return products[:5]


async def search_catalog(
    query: str,
    max_price: float | None,
    tags: list[str],
    redis: aioredis.Redis,
    settings: Settings,
) -> list[dict]:
    key = _cache_key(query, max_price, tags)
    domain = settings.shopify_store_domain.replace("https://", "").replace("http://", "").strip("/")

    if domain:
        cached = await cache_get(redis, key, settings.catalog_cache_ttl_seconds)
        if cached is not None:
            return cached
        try:
            products = _search_shopify(domain, query)
            await cache_put(redis, key, products, settings.catalog_cache_ttl_seconds)
            return products
        except Exception:
            pass
        stale = await cache_get_stale(redis, key)
        if stale is not None:
            return stale

    return _search_seed(settings.seed_catalog_path, query, max_price, tags)
