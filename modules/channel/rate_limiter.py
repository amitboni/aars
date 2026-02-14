"""modules/channel/rate_limiter.py — Redis-based rate limiting for channels.

Voice: max 5 concurrent calls, 50 calls/hour per tenant.
WhatsApp: 80 messages/second per tenant, 3 messages/day per agent.

Uses Redis INCR + EXPIRE for sliding windows and semaphores for concurrency.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    allowed: bool
    current_count: int
    limit: int
    retry_after_seconds: float | None = None


class ChannelRateLimiter:
    """Redis-based rate limiter for voice and WhatsApp channels."""

    # Voice defaults
    VOICE_MAX_CONCURRENT: int = 5
    VOICE_MAX_PER_HOUR: int = 50

    # WhatsApp defaults
    WHATSAPP_MAX_PER_SECOND: int = 80
    WHATSAPP_MAX_PER_DAY_PER_AGENT: int = 3

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    # ─── Voice Rate Limiting ──────────────────────────────────────────────────

    async def check_voice_rate(self, tenant_id: uuid.UUID) -> RateLimitResult:
        """Check both concurrent and hourly voice call limits for a tenant."""
        # Check concurrent first
        concurrent = await self._check_voice_concurrent(tenant_id)
        if not concurrent.allowed:
            return concurrent

        # Check hourly rate
        return await self._check_voice_hourly(tenant_id)

    async def _check_voice_concurrent(self, tenant_id: uuid.UUID) -> RateLimitResult:
        """Check concurrent voice call limit using a Redis counter."""
        key = f"voice:concurrent:{tenant_id}"
        count = int(await self._redis.get(key) or 0)
        if count >= self.VOICE_MAX_CONCURRENT:
            return RateLimitResult(
                allowed=False,
                current_count=count,
                limit=self.VOICE_MAX_CONCURRENT,
                retry_after_seconds=30.0,
            )
        return RateLimitResult(allowed=True, current_count=count, limit=self.VOICE_MAX_CONCURRENT)

    async def acquire_voice_slot(self, tenant_id: uuid.UUID) -> bool:
        """Acquire a concurrent voice call slot. Returns True if acquired."""
        key = f"voice:concurrent:{tenant_id}"
        count = await self._redis.incr(key)
        # Set TTL as safety net (calls should release explicitly)
        await self._redis.expire(key, 600)  # 10 min max call duration
        if count > self.VOICE_MAX_CONCURRENT:
            await self._redis.decr(key)
            return False
        return True

    async def release_voice_slot(self, tenant_id: uuid.UUID) -> None:
        """Release a concurrent voice call slot."""
        key = f"voice:concurrent:{tenant_id}"
        count = await self._redis.decr(key)
        if count < 0:
            await self._redis.set(key, 0)

    async def _check_voice_hourly(self, tenant_id: uuid.UUID) -> RateLimitResult:
        """Check hourly voice call rate using sliding window."""
        window = 3600  # 1 hour
        key = f"voice:hourly:{tenant_id}"
        now = time.time()
        window_start = now - window

        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        results = await pipe.execute()
        count = results[1]

        if count >= self.VOICE_MAX_PER_HOUR:
            # Find oldest entry to calculate retry-after
            oldest = await self._redis.zrangebyscore(key, "-inf", "+inf", start=0, num=1)
            retry_after = (float(oldest[0]) + window - now) if oldest else 60.0
            return RateLimitResult(
                allowed=False,
                current_count=count,
                limit=self.VOICE_MAX_PER_HOUR,
                retry_after_seconds=max(retry_after, 0),
            )
        return RateLimitResult(allowed=True, current_count=count, limit=self.VOICE_MAX_PER_HOUR)

    async def record_voice_call(self, tenant_id: uuid.UUID) -> None:
        """Record a voice call in the hourly sliding window."""
        key = f"voice:hourly:{tenant_id}"
        now = time.time()
        pipe = self._redis.pipeline()
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, 3700)  # Slightly longer than window
        await pipe.execute()

    # ─── WhatsApp Rate Limiting ───────────────────────────────────────────────

    async def check_whatsapp_rate(
        self, tenant_id: uuid.UUID, agent_id: uuid.UUID | None = None,
    ) -> RateLimitResult:
        """Check WhatsApp rate limit. If agent_id provided, also checks per-agent daily limit."""
        # Tenant-level per-second check
        tenant_result = await self._check_whatsapp_per_second(tenant_id)
        if not tenant_result.allowed:
            return tenant_result

        # Per-agent daily check
        if agent_id:
            return await self._check_whatsapp_daily_per_agent(tenant_id, agent_id)

        return tenant_result

    async def _check_whatsapp_per_second(self, tenant_id: uuid.UUID) -> RateLimitResult:
        """Check per-second WhatsApp message rate."""
        key = f"whatsapp:ps:{tenant_id}"
        count = int(await self._redis.get(key) or 0)
        if count >= self.WHATSAPP_MAX_PER_SECOND:
            return RateLimitResult(
                allowed=False,
                current_count=count,
                limit=self.WHATSAPP_MAX_PER_SECOND,
                retry_after_seconds=1.0,
            )
        return RateLimitResult(allowed=True, current_count=count, limit=self.WHATSAPP_MAX_PER_SECOND)

    async def record_whatsapp_message(
        self, tenant_id: uuid.UUID, agent_id: uuid.UUID | None = None,
    ) -> None:
        """Record a WhatsApp message send."""
        # Per-second counter
        ps_key = f"whatsapp:ps:{tenant_id}"
        pipe = self._redis.pipeline()
        pipe.incr(ps_key)
        pipe.expire(ps_key, 2)  # 2 second TTL
        await pipe.execute()

        # Per-agent daily counter
        if agent_id:
            daily_key = f"whatsapp:daily:{tenant_id}:{agent_id}"
            pipe = self._redis.pipeline()
            pipe.incr(daily_key)
            pipe.expire(daily_key, 86400)  # 24 hour TTL
            await pipe.execute()

    async def _check_whatsapp_daily_per_agent(
        self, tenant_id: uuid.UUID, agent_id: uuid.UUID,
    ) -> RateLimitResult:
        """Check per-agent daily WhatsApp message limit."""
        key = f"whatsapp:daily:{tenant_id}:{agent_id}"
        count = int(await self._redis.get(key) or 0)
        if count >= self.WHATSAPP_MAX_PER_DAY_PER_AGENT:
            return RateLimitResult(
                allowed=False,
                current_count=count,
                limit=self.WHATSAPP_MAX_PER_DAY_PER_AGENT,
                retry_after_seconds=3600.0,
            )
        return RateLimitResult(allowed=True, current_count=count, limit=self.WHATSAPP_MAX_PER_DAY_PER_AGENT)
