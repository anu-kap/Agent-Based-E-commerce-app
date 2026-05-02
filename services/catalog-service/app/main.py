from fastapi import FastAPI
from .routes.catalog import router as catalog_router

app = FastAPI(title="catalog-service", version="1.0.0")

app.include_router(catalog_router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "catalog-service"}
