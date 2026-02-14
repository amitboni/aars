"""api/health.py — Health check that verifies all dependencies."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from config.database import async_engine
from config.redis import redis_client

router = APIRouter()


@router.get("/health")
async def health():
    checks = {}
    # Postgres
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = True
    except Exception:
        checks["postgres"] = False
    # Redis
    try:
        await redis_client.ping()
        checks["redis"] = True
    except Exception:
        checks["redis"] = False

    healthy = all(checks.values())
    checks["status"] = "healthy" if healthy else "degraded"
    return JSONResponse(checks, status_code=200 if healthy else 503)
