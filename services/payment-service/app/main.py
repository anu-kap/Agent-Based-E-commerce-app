from fastapi import FastAPI
from .routes.cart import router as cart_router
from .routes.checkout import router as checkout_router

app = FastAPI(title="payment-service", version="1.0.0")

app.include_router(cart_router)
app.include_router(checkout_router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "payment-service"}
