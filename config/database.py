"""
config/database.py — Database engine and session factories.

CRITICAL: Two separate session factories exist:
1. async_session_factory — for FastAPI request handlers (uses asyncpg)
2. sync_session_factory  — for Celery tasks (uses psycopg2)

NEVER use async sessions in Celery. NEVER use sync sessions in FastAPI handlers.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import settings

# ── Async engine (FastAPI) ──
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)
async_session_factory = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ── Sync engine (Celery tasks) ──
sync_engine = create_engine(
    settings.DATABASE_URL_SYNC,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
)
sync_session_factory = sessionmaker(
    sync_engine,
    class_=Session,
    expire_on_commit=False,
)
