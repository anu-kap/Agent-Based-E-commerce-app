import httpx


async def cart_quote(base_url: str, items: list[dict]) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(f"{base_url}/cart/quote", json={"items": items})
        r.raise_for_status()
        return r.json()


async def checkout(base_url: str, items: list[dict], session_id: str, shipping_method: str = "standard") -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(f"{base_url}/checkout", json={"items": items, "session_id": session_id, "shipping_method": shipping_method})
        r.raise_for_status()
        return r.json()
