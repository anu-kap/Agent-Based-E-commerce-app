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
    selected = products[0] if products else None
    cart = [{"sku": selected["sku"], "quantity": 1}] if selected else []
    quote = mcp_call("cart_quote", {"items": cart}) if cart else {"lines": [], "total": 0}
    return {**state, "products": products, "cart": cart, "order": {"quote": quote}, "trace": state.get("trace", []) + ["mcp.cart_quote"]}


def checkout(state: CommerceState) -> CommerceState:
    cart = state.get("cart")
    if not cart:
        products = state.get("products") or mcp_call("search_catalog", {"query": state["message"], "tags": []})
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
        reply = (
            f"Order {order['orderId']} is ready with {order['shippingMethod']} shipping. "
            f"Total is ${quote['total']:.2f}. Kestra workflow `{order['kestraWorkflow']}` would now handle payment capture, inventory reserve, and fulfillment."
        )
    elif intent == "cart" and order.get("quote"):
        line = order["quote"]["lines"][0]
        reply = (
            f"I added {line['name']} to the cart. Subtotal is ${order['quote']['subtotal']:.2f}; "
            f"estimated total is ${order['quote']['total']:.2f}."
        )
    elif products:
        top = products[0]
        comparisons = "\n".join(
            f"- {item['name']} ({item['sku']}): ${item['price']}, rating {item['rating']}, {item['inventory']} in stock"
            for item in products[:3]
        )
        reply = f"Best match: {top['name']} at ${top['price']}.\n\n{comparisons}\n\nI can add the best option to cart or compare these more closely."
    else:
        reply = "I could not find a strong match. Try a product type, budget, or condition like waterproof, trail, laptop, or lightweight."

    return {**state, "reply": reply, "trace": state.get("trace", []) + ["compose_response"]}


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
    result = run_langgraph({"message": message, "sessionId": payload.get("sessionId", "demo"), "trace": []})
    print(json.dumps({"reply": result["reply"], "trace": result.get("trace", [])}))


if __name__ == "__main__":
    main()
