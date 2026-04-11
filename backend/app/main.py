import logging
import logging.config
from contextlib import asynccontextmanager

import structlog
from arq.connections import RedisSettings, create_pool
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text

from app.context import trace_id_var


def _inject_trace_id(logger, method, event_dict):  # noqa: ARG001
    tid = trace_id_var.get("")
    if tid:
        event_dict["trace_id"] = tid
    return event_dict


logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "default": {"class": "logging.StreamHandler", "stream": "ext://sys.stdout"},
    },
    "root": {"handlers": ["default"], "level": "INFO"},
})

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        _inject_trace_id,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

from app.analytics.router import router as analytics_router
from app.auth.router import router as auth_router
from app.backtesting.router import router as backtest_router
from app.brokers.pool import broker_pool
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
    # shutdown: close redis pool and broker pool
    await redis_pool.aclose()
    await arq_pool.aclose()
    await broker_pool.close_all()


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
