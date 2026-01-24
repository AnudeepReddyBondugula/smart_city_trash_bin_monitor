import redis
import json
import os
from datetime import datetime
from typing import Any

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

redis_client = redis.Redis(             #type: ignore
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True
)

def serialize(obj: Any):
    if isinstance(obj, datetime):
        return obj.isoformat()

    if isinstance(obj, list):
        return [serialize(item) for item in obj]

    if isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}

    return obj

def get_cache(key: str):
    raw = redis_client.get(key)
    if not raw:
        return None

    # IMPORTANT: raw must be valid JSON
    return json.loads(raw)

def set_cache(key: str, value, ttl: int = 30):
    safe_value = serialize(value)
    redis_client.setex(key, ttl, json.dumps(safe_value))
