"""
Cost guard (tiêu chí 8) — lưu tổng chi phí trong Redis.
"""
from datetime import datetime, timezone
from fastapi import HTTPException
import redis
from app.config import settings
from app.redis_client import r

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def _budget_key() -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"cost:daily:{day}"


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget -> raise HTTPException(status_code=402)."""
    if r is None:
        raise HTTPException(status_code=503, detail="Budget store unavailable")

    try:
        current = float(r.get(_budget_key()) or 0.0)
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Budget store unavailable")

    if current >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily budget exceeded")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    cost = (input_tokens / 1000.0) * PRICE_INPUT_PER_1K + (
        output_tokens / 1000.0
    ) * PRICE_OUTPUT_PER_1K
    if r is not None:
        try:
            key = _budget_key()
            r.incrbyfloat(key, cost)
            r.expire(key, 86400 * 2)
        except redis.RedisError:
            pass
    return cost
