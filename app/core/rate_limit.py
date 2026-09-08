from fastapi import HTTPException
from app.core.redis import redis_client

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 300
FAILED_LOGIN_WINDOW_SECONDS = 600


async def enforce_rate_limit(key: str, max_requests: int, window_seconds: int):
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, window_seconds)
    if count > max_requests:
        raise HTTPException(status_code=429, detail="Too many requests, please try again later")


async def is_account_locked(email: str) -> bool:
    return bool(await redis_client.exists(f"locked:{email}"))


async def record_failed_login(email: str):
    fail_key = f"failed_logins:{email}"
    fails = await redis_client.incr(fail_key)
    if fails == 1:
        await redis_client.expire(fail_key, FAILED_LOGIN_WINDOW_SECONDS)
    if fails >= MAX_LOGIN_ATTEMPTS:
        await redis_client.set(f"locked:{email}", "1", ex=LOCKOUT_SECONDS)


async def clear_failed_logins(email: str):
    await redis_client.delete(f"failed_logins:{email}")