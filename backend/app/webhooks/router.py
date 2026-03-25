import json
import secrets
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_session, get_tenant_session
from app.config import settings
from app.db.models import Strategy, User, WebhookSignal
from app.webhooks.mapper import apply_mapping
from app.webhooks.processor import evaluate_rules

# ---------------------------------------------------------------------------
# Public router – webhook ingestion (token-based auth, no JWT)
# ---------------------------------------------------------------------------
webhook_public_router = APIRouter(tags=["webhooks"])


@webhook_public_router.post("/api/v1/webhook/{token}")
async def receive_webhook(
    token: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    # 1. Look up user by webhook_token
    result = await session.execute(
        select(User).where(User.webhook_token == token)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    # 2. Read and check payload size
    body = await request.body()
    if len(body) > settings.max_webhook_payload_bytes:
        raise HTTPException(status_code=413, detail="Payload too large")

    payload: dict = json.loads(body)

    # 3. Record start time
    start_time = time.perf_counter()

    # 4. Fetch all active strategies for this user
    strat_result = await session.execute(
        select(Strategy).where(
            Strategy.tenant_id == user.id,
            Strategy.is_active.is_(True),
        )
    )
    strategies = strat_result.scalars().all()

    signals_processed = 0

    for strategy in strategies:
        if not strategy.mapping_template:
            continue

        parsed_signal = None
        rule_result_str = None
        rule_detail = None
        execution_result = None

        try:
            signal = apply_mapping(payload, strategy.mapping_template)
            parsed_signal = signal.model_dump(mode="json")
        except (ValueError, Exception) as exc:
            rule_result_str = "mapping_error"
            rule_detail = str(exc)
            # Log the signal even on mapping error
            ws = WebhookSignal(
                tenant_id=user.id,
                strategy_id=strategy.id,
                raw_payload=payload,
                parsed_signal=None,
                rule_result=rule_result_str,
                rule_detail=rule_detail,
                processing_ms=int(
                    (time.perf_counter() - start_time) * 1000
                ),
            )
            session.add(ws)
            signals_processed += 1
            continue

        # Evaluate rules (pass 0 for open_positions and signals_today for now)
        rule_out = evaluate_rules(
            signal,
            strategy.rules or {},
            open_positions=0,
            signals_today=0,
        )

        if rule_out.passed:
            rule_result_str = "passed"
            if strategy.mode == "paper":
                from app.paper_trading.engine import execute_paper_trade
                from app.db.models import PaperTradingSession

                ps_result = await session.execute(
                    select(PaperTradingSession).where(
                        PaperTradingSession.strategy_id == strategy.id,
                        PaperTradingSession.status == "active",
                    )
                )
                paper_session = ps_result.scalar_one_or_none()
                if paper_session:
                    execution_result = await execute_paper_trade(
                        session, paper_session.id, user.id, signal
                    )
                else:
                    execution_result = "no_active_session"
        else:
            rule_result_str = "blocked_by_rule"
            rule_detail = rule_out.reason

        ws = WebhookSignal(
            tenant_id=user.id,
            strategy_id=strategy.id,
            raw_payload=payload,
            parsed_signal=parsed_signal,
            rule_result=rule_result_str,
            rule_detail=rule_detail,
            execution_result=execution_result,
            processing_ms=int((time.perf_counter() - start_time) * 1000),
        )
        session.add(ws)
        signals_processed += 1

    await session.commit()
    return {"received": True, "signals_processed": signals_processed}


# ---------------------------------------------------------------------------
# Authenticated router – config & signal listing
# ---------------------------------------------------------------------------
webhook_config_router = APIRouter(
    prefix="/api/v1/webhooks", tags=["webhooks"]
)


@webhook_config_router.get("/config")
async def get_webhook_config(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"webhook_token": user.webhook_token}


@webhook_config_router.post("/config/regenerate-token")
async def regenerate_webhook_token(
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
    return {"webhook_token": user.webhook_token}


@webhook_config_router.get("/signals")
async def list_signals(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(WebhookSignal)
        .where(WebhookSignal.tenant_id == tenant_id)
        .order_by(WebhookSignal.received_at.desc())
    )
    signals = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "strategy_id": str(s.strategy_id) if s.strategy_id else None,
            "received_at": s.received_at.isoformat() if s.received_at else None,
            "raw_payload": s.raw_payload,
            "parsed_signal": s.parsed_signal,
            "rule_result": s.rule_result,
            "rule_detail": s.rule_detail,
            "execution_result": s.execution_result,
            "execution_detail": s.execution_detail,
            "processing_ms": s.processing_ms,
        }
        for s in signals
    ]
