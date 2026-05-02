from fastapi import FastAPI
from .routes.orders import router as orders_router
from .routes.automation import router as automation_router

app = FastAPI(title="order-service", version="1.0.0")

app.include_router(orders_router)
app.include_router(automation_router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "order-service"}
