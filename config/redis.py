"""config/redis.py — Redis connection (optional)."""
from typing import Optional

from redis.asyncio import Redis

from config.settings import settings

redis_client: Optional[Redis] = None

if settings.REDIS_URL:
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
