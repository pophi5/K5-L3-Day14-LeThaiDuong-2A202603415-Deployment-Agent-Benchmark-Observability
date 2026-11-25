"""
Production AI Agent — Part 6 Final Project
"""
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


class JsonFormatter(logging.Formatter):
    """Format every log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lvl": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
root_logger = logging.getLogger()
root_logger.handlers = [handler]
root_logger.setLevel(logging.INFO)

logger = logging.getLogger("agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(json.dumps({"event": "startup", "env": settings.environment}))
    yield
    logger.info(json.dumps({"event": "shutdown", "env": settings.environment}))


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(json.dumps({"event": "unhandled_error", "path": request.url.path}))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = None


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment}


@app.get("/ready")
def ready():
    if redis_healthy():
        return {"ready": True}
    return JSONResponse(status_code=503, content={"ready": False, "detail": "Redis unavailable"})


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    start = time.perf_counter()
    check_rate_limit(api_key)
    check_budget()

    answer = llm_ask(body.question)
    in_tokens = max(1, len(body.question) // 4)
    out_tokens = max(1, len(answer) // 4)
    cost = record_cost(in_tokens, out_tokens)

    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        json.dumps(
            {
                "event": "ask",
                "path": "/ask",
                "status": 200,
                "ms": elapsed_ms,
                "cost_usd": cost,
            }
        )
    )
    return {"question": body.question, "answer": answer}
