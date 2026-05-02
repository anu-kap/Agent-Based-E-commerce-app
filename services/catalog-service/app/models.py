from typing import Any
from pydantic import BaseModel


class Product(BaseModel):
    sku: str
    name: str
    category: str = ""
    price: float
    currency: str = ""
    inventory: Any = "available"
    rating: Any = ""
    tags: list[str] = []
    description: str = ""
    url: str = ""
    imageUrl: str = ""
    source: str = "seed"
