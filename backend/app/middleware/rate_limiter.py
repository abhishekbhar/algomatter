import time

from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings


_AUTH_PATHS = {"/api/v1/auth/login", "/api/v1/auth/signup", "/api/v1/auth/refresh"}
# Auth endpoints use a stricter limit (20/min per IP) to slow brute-force attempts
_AUTH_LIMIT = 20


class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis: Redis):
        super().__init__(app)
        self.redis = redis
        self.limit = settings.rate_limit_per_minute
        self.window = 60  # seconds

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path.startswith("/api/v1/webhook/"):
            # Rate-limit by webhook token
            token = path.split("/api/v1/webhook/")[-1]
            key = f"ratelimit:{token}"
            limit = self.limit
        elif path in _AUTH_PATHS:
            # Rate-limit auth endpoints by client IP to prevent brute-force
            client_ip = request.client.host if request.client else "unknown"
            key = f"ratelimit:auth:{client_ip}"
            limit = _AUTH_LIMIT
        else:
            return await call_next(request)

        now = time.time()
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - self.window)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, self.window)
        results = await pipe.execute()
        count = results[2]

        if count > limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(self.window)},
            )
        return await call_next(request)
