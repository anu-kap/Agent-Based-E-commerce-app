import httpx


async def create_order(base_url: str, items: list[dict], shipping_method: str, session_id: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(f"{base_url}/orders", json={"items": items, "shipping_method": shipping_method, "session_id": session_id})
        r.raise_for_status()
        return r.json()


async def automate_order(base_url: str, order_id: str, order: dict, cart: list, session_id: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(f"{base_url}/orders/{order_id}/automate", json={"order": order, "cart": cart, "session_id": session_id})
        r.raise_for_status()
        return r.json()
