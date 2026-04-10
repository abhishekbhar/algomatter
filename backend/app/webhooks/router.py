import json
import secrets
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_session, get_tenant_session
from app.config import settings
from app.db.models import Strategy, User, WebhookSignal
from app.webhooks.executor import SignalResult, execute

# ---------------------------------------------------------------------------
# Public router – webhook ingestion (token-based auth, no JWT)
# ---------------------------------------------------------------------------
webhook_public_router = APIRouter(tags=["webhooks"])

_STRATEGY_CACHE_TTL = 60  # seconds


async def _resolve_user(token: str, session: AsyncSession) -> User:
    result = await session.execute(select(User).where(User.webhook_token == token))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user


async def _get_active_strategies(redis, session: AsyncSession, tenant_id: uuid.UUID) -> list[dict]:
    """Return all active strategies for tenant, Redis-cached (60 s TTL)."""
    cache_key = f"strategies:active:{tenant_id}"
    try:
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    result = await session.execute(
        select(Strategy).where(
            Strategy.tenant_id == tenant_id,
            Strategy.is_active.is_(True),
        )
    )
    strategies = result.scalars().all()
    payload = [
        {
            "id": str(s.id),
            "mapping_template": s.mapping_template,
            "mode": s.mode,
            "broker_connection_id": str(s.broker_connection_id) if s.broker_connection_id else None,
            "rules": s.rules,
            "name": s.name,
        }
        for s in strategies
    ]
    try:
        await redis.set(cache_key, json.dumps(payload), ex=_STRATEGY_CACHE_TTL)
    except Exception:
        pass
    return payload


async def _write_signal_logs(
    session: AsyncSession,
    results: list[SignalResult],
    tenant_id: uuid.UUID,
    raw_payload: dict,
    start_time: float,
) -> None:
    for r in results:
        ws = WebhookSignal(
            tenant_id=tenant_id,
            strategy_id=uuid.UUID(r.strategy_id),
            raw_payload=raw_payload,
            parsed_signal=r.parsed_signal,
            rule_result=r.rule_result,
            rule_detail=r.rule_detail,
            execution_result=r.execution_result,
            execution_detail=r.execution_detail,
            processing_ms=int((time.perf_counter() - start_time) * 1000),
        )
        session.add(ws)
    await session.commit()


@webhook_public_router.post("/api/v1/webhook/{token}")
async def receive_webhook(
    token: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    user = await _resolve_user(token, session)

    body = await request.body()
    if len(body) > settings.max_webhook_payload_bytes:
        raise HTTPException(status_code=413, detail="Payload too large")
    payload: dict = json.loads(body)

    start_time = time.perf_counter()
    redis = request.app.state.redis
    arq_redis = request.app.state.arq_redis
    strategies = await _get_active_strategies(redis, session, user.id)

    results = await execute(strategies, payload, redis, session, arq_redis, tenant_id=user.id)
    await _write_signal_logs(session, results, user.id, payload, start_time)

    return {"received": True, "signals_processed": len(results)}


@webhook_public_router.post("/api/v1/webhook/{token}/{slug}")
async def receive_webhook_targeted(
    token: str,
    slug: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    user = await _resolve_user(token, session)

    body = await request.body()
    if len(body) > settings.max_webhook_payload_bytes:
        raise HTTPException(status_code=413, detail="Payload too large")
    payload: dict = json.loads(body)

    # Resolve single strategy by slug
    result = await session.execute(
        select(Strategy).where(
            Strategy.tenant_id == user.id,
            Strategy.slug == slug,
            Strategy.is_active.is_(True),
        )
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    strategy_dict = {
        "id": str(strategy.id),
        "mapping_template": strategy.mapping_template,
        "mode": strategy.mode,
        "broker_connection_id": str(strategy.broker_connection_id) if strategy.broker_connection_id else None,
        "rules": strategy.rules,
        "name": strategy.name,
    }

    start_time = time.perf_counter()
    redis = request.app.state.redis
    arq_redis = request.app.state.arq_redis

    results = await execute([strategy_dict], payload, redis, session, arq_redis, tenant_id=user.id)
    await _write_signal_logs(session, results, user.id, payload, start_time)

    return {"received": True, "signals_processed": len(results)}


# ---------------------------------------------------------------------------
# Authenticated router – config & signal listing
# ---------------------------------------------------------------------------
webhook_config_router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@webhook_config_router.get("/config")
async def get_webhook_config(
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    base_url = str(request.base_url).rstrip("/")
    webhook_url = f"{base_url}/api/v1/webhook/{user.webhook_token}"
    return {"webhook_url": webhook_url, "token": user.webhook_token}


@webhook_config_router.post("/config/regenerate-token")
async def regenerate_webhook_token(
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.webhook_token = secrets.token_urlsafe(32)
    await session.commit()
    base_url = str(request.base_url).rstrip("/")
    webhook_url = f"{base_url}/api/v1/webhook/{user.webhook_token}"
    return {"webhook_url": webhook_url, "token": user.webhook_token}


@webhook_config_router.get("/signals")
async def list_signals(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    strat_result = await session.execute(
        select(Strategy).where(Strategy.tenant_id == tenant_id)
    )
    strat_map = {s.id: s.name for s in strat_result.scalars().all()}

    total_q = await session.execute(
        select(func.count()).select_from(WebhookSignal).where(WebhookSignal.tenant_id == tenant_id)
    )
    total = total_q.scalar() or 0

    result = await session.execute(
        select(WebhookSignal)
        .where(WebhookSignal.tenant_id == tenant_id)
        .order_by(WebhookSignal.received_at.desc())
        .offset(offset)
        .limit(limit)
    )
    signals = result.scalars().all()
    return {
        "signals": [_signal_to_dict(s, strat_map) for s in signals],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@webhook_config_router.get("/signals/strategy/{strategy_id}")
async def list_strategy_signals(
    strategy_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    strat_result = await session.execute(
        select(Strategy).where(
            Strategy.id == strategy_id,
            Strategy.tenant_id == tenant_id,
        )
    )
    strategy = strat_result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    strat_map = {strategy.id: strategy.name}
    result = await session.execute(
        select(WebhookSignal)
        .where(
            WebhookSignal.tenant_id == tenant_id,
            WebhookSignal.strategy_id == strategy_id,
        )
        .order_by(WebhookSignal.received_at.desc())
    )
    signals = result.scalars().all()
    return [_signal_to_dict(s, strat_map) for s in signals]


def _signal_to_dict(s: WebhookSignal, strat_map: dict) -> dict:
    return {
        "id": str(s.id),
        "strategy_id": str(s.strategy_id) if s.strategy_id else None,
        "strategy_name": strat_map.get(s.strategy_id, "Unknown"),
        "received_at": s.received_at.isoformat() if s.received_at else None,
        "raw_payload": s.raw_payload,
        "parsed_signal": s.parsed_signal,
        "status": s.rule_result,
        "rule_result": s.rule_result,
        "error_message": s.rule_detail,
        "execution_result": s.execution_result,
        "execution_detail": s.execution_detail,
        "processing_ms": s.processing_ms,
    }
