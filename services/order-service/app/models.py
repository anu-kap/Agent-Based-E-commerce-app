from typing import Any
from pydantic import BaseModel


class OrderItem(BaseModel):
    sku: str
    quantity: int = 1
    merchandise_id: str | None = None


class OrderRequest(BaseModel):
    items: list[OrderItem]
    shipping_method: str = "standard"
    session_id: str = "demo"


class AutomationRequest(BaseModel):
    order: dict = {}
    cart: list = []
    session_id: str = "demo"


class OrderResponse(BaseModel):
    orderId: str
    status: str
    shippingMethod: str = "standard"
    quote: dict = {}
    kestraWorkflow: str = ""


class AutomationResponse(BaseModel):
    orderId: str
    status: str
    source: str = ""
    total: float = 0
    cartId: str = ""
    checkoutUrl: str = ""
    kestraWorkflow: str = ""
    kestra: Any = None
    sqsMessageId: str | None = None
