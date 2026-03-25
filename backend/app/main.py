from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis

from app.auth.router import router as auth_router
from app.config import settings
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.rate_limiter import RateLimiterMiddleware

redis_pool = Redis.from_url(settings.redis_url, decode_responses=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: expose redis pool for other modules
    app.state.redis = redis_pool
    yield
    # shutdown: close redis pool
    await redis_pool.aclose()


app = FastAPI(title="GainGuard", version="0.1.0", lifespan=lifespan)
app.add_middleware(RateLimiterMiddleware, redis=redis_pool)
app.add_middleware(RequestLoggingMiddleware)
app.include_router(auth_router)


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}
