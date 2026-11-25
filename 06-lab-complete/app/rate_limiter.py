"""
Rate limiting (tiêu chí 7) — sliding window lưu trong Redis.
"""
import time
import uuid
from fastapi import HTTPException
import redis
from app.config import settings
from app.redis_client import r

WINDOW_SECONDS = 60


def check_rate_limit(key: str) -> None:
    """Kiểm tra rate limit theo API key bằng Redis sorted set."""
    if r is None:
        raise HTTPException(status_code=503, detail="Rate limiter unavailable")

    now = time.time()
    redis_key = f"rate_limit:{key}"
    member = f"{now}:{uuid.uuid4().hex}"

    try:
        pipe = r.pipeline()
        pipe.zremrangebyscore(redis_key, 0, now - WINDOW_SECONDS)
        pipe.zcard(redis_key)
        _, current_count = pipe.execute()

        if current_count >= settings.rate_limit_per_minute:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(WINDOW_SECONDS)},
            )

        pipe2 = r.pipeline()
        pipe2.zadd(redis_key, {member: now})
        pipe2.expire(redis_key, WINDOW_SECONDS + 1)
        pipe2.execute()
    except HTTPException:
        raise
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Rate limiter unavailable")
