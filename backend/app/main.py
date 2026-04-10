from contextlib import asynccontextmanager

from arq.connections import RedisSettings, create_pool
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text

from app.analytics.router import router as analytics_router
from app.auth.router import router as auth_router
from app.backtesting.router import router as backtest_router
from app.brokers.router import router as broker_router
from app.config import settings
from app.config_router import router as config_router
from app.db.session import async_session_factory
from app.deployments.router import router as deployment_router
from app.historical.router import router as historical_router
from app.hosted_strategies.router import router as hosted_strategy_router
from app.hosted_strategies.router import template_router
from app.manual_trades.router import router as manual_trades_router
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.paper_trading.router import router as paper_trading_router
from app.strategies.router import router as strategy_router
from app.webhooks.router import webhook_config_router, webhook_public_router

redis_pool = Redis.from_url(settings.redis_url, decode_responses=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: expose redis pool for other modules
    app.state.redis = redis_pool
    arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    app.state.arq_redis = arq_pool
    yield
    # shutdown: close redis pool
    await redis_pool.aclose()
    await arq_pool.aclose()


app = FastAPI(title="AlgoMatter", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimiterMiddleware, redis=redis_pool)
app.add_middleware(RequestLoggingMiddleware)
app.include_router(auth_router)
app.include_router(backtest_router)
app.include_router(broker_router)
app.include_router(strategy_router)
app.include_router(webhook_public_router)
app.include_router(webhook_config_router)
app.include_router(paper_trading_router)
app.include_router(analytics_router)
app.include_router(historical_router)
app.include_router(hosted_strategy_router)
app.include_router(template_router)
app.include_router(deployment_router)
app.include_router(manual_trades_router)
app.include_router(config_router)


@app.get("/api/v1/health")
async def health():
    db_status = "ok"
    redis_status = "ok"
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"
    try:
        await redis_pool.ping()
    except Exception:
        redis_status = "error"
    status_code = 200 if db_status == "ok" and redis_status == "ok" else 503
    return JSONResponse(
        status_code=status_code,
        content={"database": db_status, "redis": redis_status},
    )
