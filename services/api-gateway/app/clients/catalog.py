import httpx


async def search_catalog(base_url: str, query: str, max_price: float | None, tags: list[str]) -> list[dict]:
    params: dict = {"q": query, "tags": ",".join(tags)}
    if max_price is not None:
        params["max_price"] = str(max_price)
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{base_url}/products/search", params=params)
        r.raise_for_status()
        return r.json()
