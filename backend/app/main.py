from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis

from app.auth.router import router as auth_router
from app.backtesting.router import router as backtest_router
from app.brokers.router import router as broker_router
from app.strategies.router import router as strategy_router
from app.paper_trading.router import router as paper_trading_router
from app.webhooks.router import webhook_config_router, webhook_public_router
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
app.include_router(backtest_router)
app.include_router(broker_router)
app.include_router(strategy_router)
app.include_router(webhook_public_router)
app.include_router(webhook_config_router)
app.include_router(paper_trading_router)


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}
