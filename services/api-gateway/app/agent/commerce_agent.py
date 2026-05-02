"""LangGraph commerce agent — orchestrates microservices via HTTP instead of
direct MCP tool imports. Falls back to a deterministic graph when LangGraph
is unavailable, preserving identical behaviour.
"""
import re
from typing import Any, Dict, List, TypedDict

from ..clients import catalog as catalog_client
from ..clients import order as order_client
from ..clients import payment as payment_client
from ..config import Settings


class CommerceState(TypedDict, total=False):
    message: str
    sessionId: str
    selectedSku: str
    intent: str
    constraints: Dict[str, Any]
    products: List[Dict[str, Any]]
    cart: List[Dict[str, Any]]
    order: Dict[str, Any]
    automation: Dict[str, Any]
    radar: Dict[str, Any]
    recentIntents: List[Dict[str, Any]]
    reply: str
    trace: List[str]
    _settings: Any


def classify(state: CommerceState) -> CommerceState:
    message = state["message"].lower()
    trace = state.get("trace", []) + ["classify_intent"]
    if any(p in message for p in ["radar", "opportunity scan", "demand scan", "campus scan", "homecoming readiness", "readiness"]):
        intent = "radar"
    elif any(p in message for p in ["order paid", "paid order", "simulate paid", "simulate order", "post-order", "post order", "webhook"]):
        intent = "post_order"
    elif any(w in message for w in ["checkout", "buy", "order", "place order"]):
        intent = "checkout"
    elif any(w in message for w in ["add", "cart", "quote"]):
        intent = "cart"
    else:
        intent = "search"
    prices = [float(m) for m in re.findall(r"\$?(\d{2,4})(?:\s*dollars)?", message)]
    tags = [t for t in ["waterproof", "trail", "rain", "running", "hiking", "laptop", "lightweight"] if t in message]
    return {**state, "intent": intent, "constraints": {"max_price": min(prices) if prices else None, "tags": tags}, "trace": trace}


async def search_products(state: CommerceState) -> CommerceState:
    settings: Settings = state["_settings"]
    constraints = state.get("constraints", {})
    try:
        products = await catalog_client.search_catalog(
            settings.catalog_service_url,
            state["message"],
            constraints.get("max_price"),
            constraints.get("tags", []),
        )
    except Exception:
        products = []
    return {**state, "products": products, "trace": state.get("trace", []) + ["catalog-service.search"]}


async def update_cart(state: CommerceState) -> CommerceState:
    settings: Settings = state["_settings"]
    products = state.get("products") or []
    if not products:
        try:
            products = await catalog_client.search_catalog(settings.catalog_service_url, state["message"], None, [])
        except Exception:
            products = []
    selected_sku = state.get("selectedSku")
    selected = next((p for p in products if p.get("sku") == selected_sku), None) if selected_sku else None
    selected = selected or (products[0] if products else None)
    cart = [{"sku": selected["sku"], "quantity": 1}] if selected else []
    try:
        quote = await payment_client.cart_quote(settings.payment_service_url, cart) if cart else {"lines": [], "total": 0}
    except Exception:
        quote = {"lines": [], "total": 0}
    return {**state, "products": products, "cart": cart, "order": {"quote": quote}, "trace": state.get("trace", []) + ["payment-service.cart_quote"]}


async def checkout(state: CommerceState) -> CommerceState:
    settings: Settings = state["_settings"]
    cart = state.get("cart")
    order = state.get("order", {})
    if order.get("quote", {}).get("source") == "shopify":
        return {**state, "order": order, "trace": state.get("trace", []) + ["shopify.checkout_ready"]}
    if not cart:
        try:
            products = await catalog_client.search_catalog(settings.catalog_service_url, state["message"], None, [])
        except Exception:
            products = []
        cart = [{"sku": products[0]["sku"], "quantity": 1}] if products else []
        state = {**state, "products": products if products else state.get("products", []), "cart": cart}
    try:
        order = await order_client.create_order(settings.order_service_url, cart, "standard", state.get("sessionId", "demo"))
    except Exception:
        order = {}
    return {**state, "order": order, "trace": state.get("trace", []) + ["order-service.create_order"]}


async def post_order(state: CommerceState) -> CommerceState:
    settings: Settings = state["_settings"]
    order = state.get("order", {})
    order_id = order.get("orderId", "demo")
    try:
        automation = await order_client.automate_order(
            settings.order_service_url,
            order_id,
            order,
            state.get("cart", []),
            state.get("sessionId", "demo"),
        )
    except Exception:
        automation = {}
    return {**state, "automation": automation, "trace": state.get("trace", []) + ["order-service.automate", "kestra.post_order_workflow"]}


async def campus_radar(state: CommerceState) -> CommerceState:
    from ..routes.radar import run_radar
    settings: Settings = state["_settings"]
    try:
        radar = await run_radar(state.get("recentIntents", []), "this week's campus retail opportunity scan", settings)
    except Exception as exc:
        radar = {"error": str(exc)}
    return {**state, "radar": radar, "products": radar.get("featuredProducts", []), "trace": state.get("trace", []) + ["radar.campus_demand"]}


def compose_reply(state: CommerceState) -> CommerceState:
    intent = state.get("intent")
    products = state.get("products", [])
    order = state.get("order", {})
    automation = state.get("automation", {})
    radar = state.get("radar", {})
    shopify_domain = state.get("_settings").shopify_store_domain if state.get("_settings") else ""

    if intent == "radar" and radar:
        actions = radar.get("actions", [])
        action_text = " ".join(f"{i + 1}. {a}" for i, a in enumerate(actions[:3]))
        kestra = radar.get("kestra", {})
        kestra_text = (
            f" Kestra workflow `{radar.get('kestraWorkflow')}` started as execution `{kestra.get('executionId')}`."
            if kestra.get("status") == "triggered"
            else f" Kestra workflow `{radar.get('kestraWorkflow')}` is ready but not running locally."
        )
        reply = f"Campus Demand Radar scanned events, weather, shopper intent, and Shopify inventory. Recommended actions: {action_text}{kestra_text}"
    elif intent == "post_order" and automation:
        kestra = automation.get("kestra", {})
        if kestra and kestra.get("status") == "triggered":
            reply = f"Simulated Shopify paid order `{automation['orderId']}`. Kestra post-order workflow `{automation['kestraWorkflow']}` started as execution `{kestra.get('executionId')}`."
        else:
            reply = f"Simulated Shopify paid order `{automation.get('orderId', 'demo')}`. Kestra workflow is configured but not reachable right now."
    elif intent == "checkout" and order:
        quote = order.get("quote", {})
        if quote.get("source") == "shopify":
            reply = f"Your Shopify cart is ready. Estimated total is ${quote.get('total', 0):.2f}. Use the checkout button to complete payment."
        else:
            reply = f"Local demo order {order.get('orderId')} is ready with {order.get('shippingMethod', 'standard')} shipping. Total is ${quote.get('total', 0):.2f}."
    elif intent == "cart" and order.get("quote"):
        quote = order["quote"]
        if quote.get("source") == "shopify":
            reply = f"I updated the Shopify cart. Estimated total is ${quote.get('total', 0):.2f}."
            if quote.get("checkoutUrl"):
                reply += " Use the checkout button when you are ready."
        elif quote.get("lines"):
            line = quote["lines"][0]
            reply = f"I added {line['name']} to the cart. Subtotal is ${quote.get('subtotal', 0):.2f}; estimated total is ${quote['total']:.2f}."
        else:
            reply = "I could not add an item yet. Ask me to find a product first, then I can add the best match."
    elif products:
        top = products[0]
        currency = top.get("currency") or "USD"
        if top.get("source") == "shopify":
            reply = f"I found {len(products)} live Shopify items. Best match is {top['name']} at {currency} ${top.get('price', 0):g}. Pick a card to add it to your cart."
        else:
            comparisons = "\n".join(f"- {p.get('name')} ({p.get('sku')}): {p.get('currency') or 'USD'} ${p.get('price', 0):g}" for p in products[:3])
            reply = f"Best match: {top['name']} at {currency} ${top.get('price', 0):g}.\n\n{comparisons}\n\nI can add the best option to cart or compare these more closely."
    else:
        if shopify_domain:
            reply = f"No matches in the live {shopify_domain} catalog for that. Try a broader keyword like t-shirt, mug, hoodie, or alumni gift."
        else:
            reply = "I could not find a match in the seed catalog. Try trail shoes, rain jacket, hoodie, daypack, or merino socks."
    return {**state, "reply": reply, "trace": state.get("trace", []) + ["compose_response"]}


async def run_agent(state: CommerceState) -> CommerceState:
    try:
        from langgraph.graph import END, StateGraph

        graph = StateGraph(CommerceState)
        graph.add_node("classify", classify)
        graph.add_node("search_products", search_products)
        graph.add_node("update_cart", update_cart)
        graph.add_node("checkout", checkout)
        graph.add_node("post_order", post_order)
        graph.add_node("campus_radar", campus_radar)
        graph.add_node("compose_reply", compose_reply)
        graph.set_entry_point("classify")
        graph.add_conditional_edges(
            "classify",
            lambda s: s["intent"],
            {"search": "search_products", "cart": "update_cart", "checkout": "checkout", "post_order": "post_order", "radar": "campus_radar"},
        )
        for node in ["search_products", "update_cart", "checkout", "post_order", "campus_radar"]:
            graph.add_edge(node, "compose_reply")
        graph.add_edge("compose_reply", END)
        compiled = graph.compile()
        result = compiled.invoke({**state, "trace": state.get("trace", []) + ["langgraph.StateGraph"]})
        return result
    except Exception:
        pass

    state = classify({**state, "trace": state.get("trace", []) + ["langgraph.fallback"]})
    intent = state["intent"]
    if intent == "search":
        state = await search_products(state)
    elif intent == "cart":
        state = await update_cart(state)
    elif intent == "post_order":
        state = await post_order(state)
    elif intent == "radar":
        state = await campus_radar(state)
    else:
        state = await checkout(state)
    return compose_reply(state)
