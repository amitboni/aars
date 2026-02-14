"""config/redis.py — Redis connection."""
from redis.asyncio import Redis

from config.settings import settings

redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
