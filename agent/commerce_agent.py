#!/usr/bin/env python3
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, TypedDict

ROOT = Path(__file__).resolve().parents[1]
MCP_SERVER = ROOT / "agent" / "mcp" / "commerce_mcp_server.py"


class CommerceState(TypedDict, total=False):
    message: str
    sessionId: str
    selectedSku: str
    intent: str
    constraints: Dict[str, Any]
    products: List[Dict[str, Any]]
    cart: List[Dict[str, Any]]
    order: Dict[str, Any]
    reply: str
    trace: List[str]


def mcp_call(name: str, arguments: Dict[str, Any]) -> Any:
    process = subprocess.Popen(
        [sys.executable, str(MCP_SERVER)],
        cwd=str(ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": name, "arguments": arguments}}
    ]
    stdout, stderr = process.communicate("\n".join(json.dumps(item) for item in requests) + "\n", timeout=10)
    if process.returncode not in (0, None):
        raise RuntimeError(stderr)
    lines = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    response = lines[-1]
    if "error" in response:
        raise RuntimeError(response["error"]["message"])
    return response["result"]["content"][0]["json"]


def classify(state: CommerceState) -> CommerceState:
    message = state["message"].lower()
    trace = state.get("trace", []) + ["classify_intent"]
    if any(word in message for word in ["checkout", "buy", "order", "place order"]):
        intent = "checkout"
    elif any(word in message for word in ["add", "cart", "quote"]):
        intent = "cart"
    else:
        intent = "search"

    prices = [float(match) for match in re.findall(r"\$?(\d{2,4})(?:\s*dollars)?", message)]
    tags = [tag for tag in ["waterproof", "trail", "rain", "running", "hiking", "laptop", "lightweight"] if tag in message]
    return {**state, "intent": intent, "constraints": {"max_price": min(prices) if prices else None, "tags": tags}, "trace": trace}


def search_products(state: CommerceState) -> CommerceState:
    constraints = state.get("constraints", {})
    products = mcp_call("search_catalog", {
        "query": state["message"],
        "max_price": constraints.get("max_price"),
        "tags": constraints.get("tags", [])
    })
    return {**state, "products": products, "trace": state.get("trace", []) + ["mcp.search_catalog"]}


def update_cart(state: CommerceState) -> CommerceState:
    products = state.get("products") or mcp_call("search_catalog", {"query": state["message"], "tags": []})
    if not products:
        products = mcp_call("search_catalog", {"query": "", "tags": []})
    selected_sku = state.get("selectedSku")
    selected = next((product for product in products if product.get("sku") == selected_sku), None) if selected_sku else None
    selected = selected or (products[0] if products else None)
    cart = [{"sku": selected["sku"], "quantity": 1}] if selected else []
    quote = mcp_call("cart_quote", {"items": cart}) if cart else {"lines": [], "total": 0}
    return {**state, "products": products, "cart": cart, "order": {"quote": quote}, "trace": state.get("trace", []) + ["mcp.cart_quote"]}


def checkout(state: CommerceState) -> CommerceState:
    cart = state.get("cart")
    if not cart:
        products = state.get("products") or mcp_call("search_catalog", {"query": state["message"], "tags": []})
        if not products:
            products = mcp_call("search_catalog", {"query": "", "tags": []})
        cart = [{"sku": products[0]["sku"], "quantity": 1}] if products else []
        state = {**state, "products": products, "cart": cart}
    order = mcp_call("create_order", {"items": cart, "shipping_method": "standard"}) if cart else {}
    return {**state, "order": order, "trace": state.get("trace", []) + ["mcp.create_order", "kestra.workflow.prepared"]}


def compose_reply(state: CommerceState) -> CommerceState:
    intent = state.get("intent")
    products = state.get("products", [])
    order = state.get("order", {})

    if intent == "checkout" and order:
        quote = order["quote"]
        kestra = order.get("kestra", {})
        kestra_line = (
            f"Kestra execution `{kestra.get('executionId')}` was triggered."
            if kestra.get("status") == "triggered"
            else f"Kestra workflow `{order['kestraWorkflow']}` is configured, but not reachable right now."
        )
        checkout_url = quote.get("checkoutUrl")
        checkout_line = f" Continue checkout here: {checkout_url}" if checkout_url else ""
        reply = (
            f"Order {order['orderId']} is ready with {order['shippingMethod']} shipping. "
            f"Total is ${quote.get('total', 0):.2f}. {kestra_line}{checkout_line}"
        )
    elif intent == "cart" and order.get("quote"):
        quote = order["quote"]
        if quote.get("source") == "shopify":
            checkout_url = quote.get("checkoutUrl")
            reply = f"I updated the Shopify cart. Estimated total is ${quote.get('total', 0):.2f}."
            if checkout_url:
                reply += " Use the checkout button when you are ready."
        elif quote.get("lines"):
            line = quote["lines"][0]
            reply = (
                f"I added {line['name']} to the cart. Subtotal is ${quote['subtotal']:.2f}; "
                f"estimated total is ${quote['total']:.2f}."
            )
        else:
            reply = "I could not add an item yet because I do not have a product selection. Ask me to find a product first, then I can add the best match."
    elif products:
        top = products[0]
        currency = top.get("currency") or "USD"
        comparisons = "\n".join(
            format_product_line(item)
            for item in products[:3]
        )
        reply = f"Best match: {top['name']} at {currency} ${top.get('price', 0):g}.\n\n{comparisons}\n\nI can add the best option to cart or compare these more closely."
    else:
        reply = (
            "I could not find a strong match in the connected catalog. "
            "For the Shopify demo store, try t-shirt, mug, business card, backpack, phone case, or wedding invitation."
        )

    return {**state, "reply": reply, "trace": state.get("trace", []) + ["compose_response"]}


def format_product_line(item: Dict[str, Any]) -> str:
    currency = item.get("currency") or "USD"
    suffix = f", rating {item['rating']}" if item.get("rating") else ""
    stock = f", {item['inventory']} in stock" if isinstance(item.get("inventory"), (int, float)) else ""
    link = f" - {item['url']}" if item.get("url") else ""
    return f"- {item.get('name', 'Product')} ({item.get('sku', 'SKU')}): {currency} ${item.get('price', 0):g}{suffix}{stock}{link}"


def run_fallback_graph(state: CommerceState) -> CommerceState:
    state = classify(state)
    if state["intent"] == "search":
        state = search_products(state)
    elif state["intent"] == "cart":
        state = update_cart(state)
    else:
        state = checkout(state)
    return compose_reply(state)


def run_langgraph(state: CommerceState) -> CommerceState:
    try:
        from langgraph.graph import END, StateGraph
    except Exception:
        return run_fallback_graph({**state, "trace": state.get("trace", []) + ["langgraph.fallback"]})

    graph = StateGraph(CommerceState)
    graph.add_node("classify", classify)
    graph.add_node("search_products", search_products)
    graph.add_node("update_cart", update_cart)
    graph.add_node("checkout", checkout)
    graph.add_node("compose_reply", compose_reply)
    graph.set_entry_point("classify")
    graph.add_conditional_edges(
        "classify",
        lambda current: current["intent"],
        {"search": "search_products", "cart": "update_cart", "checkout": "checkout"}
    )
    graph.add_edge("search_products", "compose_reply")
    graph.add_edge("update_cart", "compose_reply")
    graph.add_edge("checkout", "compose_reply")
    graph.add_edge("compose_reply", END)
    return graph.compile().invoke({**state, "trace": state.get("trace", []) + ["langgraph.StateGraph"]})


def main():
    payload = json.loads(sys.stdin.read() or "{}")
    message = payload.get("message", "").strip()
    if not message:
        print(json.dumps({"reply": "Send me a shopping request to start.", "trace": ["empty_message"]}))
        return
    result = run_langgraph({
        "message": message,
        "sessionId": payload.get("sessionId", "demo"),
        "selectedSku": payload.get("selectedSku", ""),
        "products": payload.get("products", []),
        "cart": payload.get("cart", []),
        "order": payload.get("order", {}),
        "trace": []
    })
    print(json.dumps({
        "reply": result["reply"],
        "trace": result.get("trace", []),
        "products": result.get("products", []),
        "cart": result.get("cart", []),
        "order": result.get("order", {})
    }))


if __name__ == "__main__":
    main()
