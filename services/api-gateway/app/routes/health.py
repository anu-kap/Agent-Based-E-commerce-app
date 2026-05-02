from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "api-gateway"}


@router.get("/ready")
async def ready() -> dict:
    return {"ok": True}
