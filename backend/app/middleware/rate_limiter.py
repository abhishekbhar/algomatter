import time

from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings


class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis: Redis):
        super().__init__(app)
        self.redis = redis
        self.limit = settings.rate_limit_per_minute
        self.window = 60  # seconds

    async def dispatch(self, request: Request, call_next):
        # Only rate-limit webhook endpoints
        if not request.url.path.startswith("/api/v1/webhook/"):
            return await call_next(request)

        # Extract token from path as rate-limit key
        token = request.url.path.split("/api/v1/webhook/")[-1]
        key = f"ratelimit:{token}"
        now = time.time()
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - self.window)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, self.window)
        results = await pipe.execute()
        count = results[2]

        if count > self.limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(self.window)},
            )
        return await call_next(request)
