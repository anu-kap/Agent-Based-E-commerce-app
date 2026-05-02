from typing import Any
from pydantic import BaseModel


class CartItem(BaseModel):
    sku: str
    quantity: int = 1
    merchandise_id: str | None = None


class CartQuoteRequest(BaseModel):
    items: list[CartItem]


class CartLine(BaseModel):
    sku: str
    name: str = ""
    quantity: int
    unitPrice: float = 0
    lineTotal: float = 0


class CartQuoteResponse(BaseModel):
    source: str = "local"
    lines: list[CartLine] = []
    subtotal: float | None = None
    shipping: float | None = None
    tax: float | None = None
    total: float = 0
    checkoutUrl: str | None = None
    cart: Any = None


class CheckoutRequest(BaseModel):
    items: list[CartItem]
    session_id: str = "demo"
    shipping_method: str = "standard"
