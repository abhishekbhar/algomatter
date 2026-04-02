import json
import secrets
import time
import uuid
from decimal import Decimal

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
        execution_detail = None

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
            elif strategy.mode == "live":
                if not strategy.broker_connection_id:
                    execution_result = "no_broker_connection"
                else:
                    from app.brokers.factory import get_broker
                    from app.brokers.base import OrderRequest as BrokerOrderRequest
                    from app.crypto.encryption import decrypt_credentials
                    from app.db.models import BrokerConnection

                    bc_result = await session.execute(
                        select(BrokerConnection).where(
                            BrokerConnection.id == strategy.broker_connection_id,
                            BrokerConnection.tenant_id == user.id,
                        )
                    )
                    bc = bc_result.scalar_one_or_none()
                    if not bc:
                        execution_result = "broker_connection_not_found"
                    else:
                        creds = decrypt_credentials(user.id, bc.credentials)
                        broker = await get_broker(bc.broker_type, creds)
                        try:
                            order_req = BrokerOrderRequest(
                                symbol=signal.symbol,
                                exchange=signal.exchange,
                                action=signal.action,
                                quantity=signal.quantity,
                                order_type=signal.order_type or "MARKET",
                                price=signal.price or Decimal("0"),
                                product_type=signal.product_type or "DELIVERY",
                                trigger_price=signal.trigger_price,
                            )
                            result = await broker.place_order(order_req)
                            execution_result = result.status
                            execution_detail = result.model_dump(mode="json")
                        except Exception as exc:
                            execution_result = "broker_error"
                            execution_detail = {"error": str(exc)}
                        finally:
                            await broker.close()
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
            execution_detail=execution_detail,
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
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])

    # Fetch strategies for name lookup
    strat_result = await session.execute(
        select(Strategy).where(Strategy.tenant_id == tenant_id)
    )
    strat_map = {s.id: s.name for s in strat_result.scalars().all()}

    result = await session.execute(
        select(WebhookSignal)
        .where(WebhookSignal.tenant_id == tenant_id)
        .order_by(WebhookSignal.received_at.desc())
    )
    signals = result.scalars().all()
    return [_signal_to_dict(s, strat_map) for s in signals]


@webhook_config_router.get("/signals/strategy/{strategy_id}")
async def list_strategy_signals(
    strategy_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])

    # Verify strategy belongs to user
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
        "error_message": s.rule_detail,
        "execution_result": s.execution_result,
        "execution_detail": s.execution_detail,
        "processing_ms": s.processing_ms,
    }
