import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def trigger_kestra(order_id: str, total, workflow_event: str, cart_id: str = "", checkout_url: str = "", flow_id: str | None = None) -> dict:
    kestra_url = os.getenv("KESTRA_URL", "http://localhost:8080").rstrip("/")
    namespace = os.getenv("KESTRA_NAMESPACE", "demo.commerce")
    flow_id = flow_id or os.getenv("KESTRA_FLOW_ID", "chat-commerce-order-fulfillment")

    data = urlencode({
        "orderId": order_id,
        "total": str(total),
        "workflowEvent": workflow_event,
        "cartId": cart_id,
        "checkoutUrl": checkout_url,
    }).encode("utf-8")
    req = Request(
        f"{kestra_url}/api/v1/main/executions/{namespace}/{flow_id}",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=8) as r:
            payload = json.loads(r.read().decode("utf-8"))
            return {
                "status": "triggered",
                "executionId": payload.get("id"),
                "url": f"{kestra_url}/ui/executions/{payload.get('id')}" if payload.get("id") else kestra_url,
                "workflowEvent": workflow_event,
                "flowId": flow_id,
            }
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": str(exc), "url": kestra_url, "workflowEvent": workflow_event, "flowId": flow_id}
