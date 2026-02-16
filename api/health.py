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
    if redis_client:
        try:
            await redis_client.ping()
            checks["redis"] = True
        except Exception:
            checks["redis"] = False
    else:
        checks["redis"] = "not_configured"

    # Check migrations
    try:
        async with async_engine.connect() as conn:
            result = await conn.execute(text(
                "SELECT version_num FROM alembic_version LIMIT 1"
            ))
            row = result.first()
            checks["alembic_version"] = row[0] if row else "no_version"
    except Exception as e:
        checks["alembic_version"] = f"error: {e}"

    # Check if tables exist
    try:
        async with async_engine.connect() as conn:
            result = await conn.execute(text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
            ))
            checks["tables"] = [r[0] for r in result.fetchall()]
    except Exception as e:
        checks["tables"] = f"error: {e}"

    healthy = checks["postgres"] is True
    checks["status"] = "healthy" if healthy else "degraded"
    return JSONResponse(checks, status_code=200 if healthy else 503)
