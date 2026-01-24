# app/rate_limit.py

import time
import redis                                            # type: ignore
from fastapi import HTTPException, status, Request      # type: ignore

redis_client = redis.Redis(
    host="redis",
    port=6379,
    decode_responses=True,
)

RATE_LIMIT = 60
WINDOW_SECONDS = 60


async def rate_limiter(request: Request):
    """
    Rate limit per authenticated user
    """

    user = getattr(request.state, "user", None)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user_key = f"user:{user['username']}"

    now = int(time.time())
    window_key = f"ratelimit:{user_key}:{now // WINDOW_SECONDS}"

    count = redis_client.incr(window_key)

    if count == 1:
        redis_client.expire(window_key, WINDOW_SECONDS)

    if count > RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again later.",
        )
