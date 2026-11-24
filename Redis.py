"""Sliding-window rate limiter backed by Redis sorted sets."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass

import redis


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    request_count: int
    retry_after: int = 0


class RateLimiter:
    """Rate limiter using one Redis ZSET per user and an atomic Lua script."""

    _SCRIPT = """
    local now_parts = redis.call('TIME')
    local now = tonumber(now_parts[1]) + (tonumber(now_parts[2]) / 1000000)
    local window_start = now - ARGV[1]
    redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', window_start)
    local count = redis.call('ZCARD', KEYS[1])
    if count < tonumber(ARGV[2]) then
        redis.call('ZADD', KEYS[1], now, ARGV[3])
        redis.call('EXPIRE', KEYS[1], ARGV[1])
        return {1, count + 1, 0}
    end
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    local retry = 0
    if #oldest >= 2 then
        retry = math.max(0, math.ceil((tonumber(oldest[2]) + tonumber(ARGV[1])) - now))
    end
    redis.call('EXPIRE', KEYS[1], ARGV[1])
    return {0, count, retry}
    """

    def __init__(
        self,
        client: redis.Redis,
        max_requests: int = 5,
        window_seconds: int = 60,
        key_prefix: str = "udb:rate-limit",
    ) -> None:
        if not isinstance(max_requests, int) or max_requests <= 0:
            raise ValueError("max_requests must be a positive integer")
        if not isinstance(window_seconds, int) or window_seconds <= 0:
            raise ValueError("window_seconds must be a positive integer")
        if not key_prefix.strip():
            raise ValueError("key_prefix must not be empty")
        self.client = client
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix.strip()
        self._script = client.register_script(self._SCRIPT)

    def check_request(self, user_id: str) -> RateLimitResult:
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id must be a non-empty string")
        key = f"{self.key_prefix}:{user_id.strip()}"
        request_id = uuid.uuid4().hex
        try:
            raw = self._script(
                keys=[key],
                args=[self.window_seconds, self.max_requests, request_id],
            )
        except (redis.RedisError, TypeError, ValueError) as exc:
            raise RuntimeError(f"Redis rate-limit operation failed: {exc}") from exc
        if not isinstance(raw, (list, tuple)) or len(raw) != 3:
            raise RuntimeError(f"Unexpected Redis response: {raw!r}")
        try:
            allowed, count, retry = (int(value) for value in raw)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"Unexpected Redis response: {raw!r}") from exc
        return RateLimitResult(bool(allowed), count, retry)


def connect_from_environment() -> redis.Redis:
    """Create a Redis client using REDIS_URL or localhost defaults."""
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        client = redis.Redis.from_url(url, decode_responses=True)
        client.ping()
        return client
    except (redis.RedisError, ValueError) as exc:
        raise ConnectionError(
            f"Could not connect to Redis at {url}. Start Redis and try again. Details: {exc}"
        ) from exc


def main() -> None:
    try:
        client = connect_from_environment()
        limiter = RateLimiter(client)
        user_id = f"demo-user-{uuid.uuid4().hex[:8]}"
        print(f"Rate limiter demo for {user_id} (limit: 5 requests / 60 seconds)")
        for number in range(1, 8):
            result = limiter.check_request(user_id)
            status = "ALLOWED" if result.allowed else "REJECTED"
            line = f"Request {number}: {status} | count={result.request_count}"
            if not result.allowed:
                line += f" | retry in approximately {result.retry_after}s"
            print(line)
            time.sleep(0.05)
    except (ConnectionError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
