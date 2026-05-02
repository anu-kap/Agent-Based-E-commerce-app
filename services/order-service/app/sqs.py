"""SQS publisher — publishes order events to sqs://order-events.
No-ops gracefully when SQS_ORDER_EVENTS_URL is unset or boto3 unavailable.
"""
import json
import os


def publish_order_event(event_type: str, payload: dict) -> str | None:
    queue_url = os.getenv("SQS_ORDER_EVENTS_URL", "").strip()
    if not queue_url:
        return None
    try:
        import boto3
    except ImportError:
        return None
    try:
        client = boto3.client("sqs", region_name=os.getenv("AWS_REGION", "us-east-1"))
        params: dict = {
            "QueueUrl": queue_url,
            "MessageBody": json.dumps({"type": event_type, "payload": payload}),
        }
        if queue_url.endswith(".fifo"):
            params["MessageGroupId"] = "orders"
            params["MessageDeduplicationId"] = str(payload.get("orderId", event_type))
        response = client.send_message(**params)
        return response.get("MessageId")
    except Exception:
        return None
