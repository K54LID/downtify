from __future__ import annotations
import uuid
import json
from typing import Any
import redis.asyncio as redis
from app.middleware.throttle import get_redis

# Lightweight Redis-backed kv used to map short tokens -> arbitrary JSON payloads
# (URLs, search-result lists, etc.) so callback_data stays under Telegram's 64-byte limit.

TTL_SECONDS = 60 * 60  # 1 hour


async def put(payload: Any) -> str:
    token = uuid.uuid4().hex[:10]
    r: redis.Redis = get_redis()
    await r.set(f"kv:{token}", json.dumps(payload), ex=TTL_SECONDS)
    return token


async def get(token: str) -> Any | None:
    r: redis.Redis = get_redis()
    raw = await r.get(f"kv:{token}")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None
