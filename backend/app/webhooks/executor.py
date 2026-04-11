# backend/app/webhooks/executor.py
"""Webhook execution pipeline.

execute()                  — public entry point called from router.
                             Live orders are placed synchronously (awaited) so
                             latency stays in the milliseconds range.
                             Paper trades are executed concurrently via asyncio.gather.
_execute_dual_leg()        — close-then-open two-leg execution for dual_leg strategies.
                             Called from execute() when dual_leg.enabled is true.
_place_live_order()        — opens its own DB session, decrypts creds, calls
                             broker.place_order(), updates Redis counters.
execute_live_order_task()  — ARQ background task used only by the recovery cron.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.brokers.factory import get_broker
from app.context import trace_id_var
from app.crypto.encryption import decrypt_credentials
from app.db.models import BrokerConnection, PaperTradingSession, Strategy, WebhookSignal
from app.db.session import async_session_factory
from app.paper_trading.engine import execute_paper_trade
from app.webhooks.mapper import apply_mapping
from app.webhooks.processor import (
    evaluate_rules,
    get_strategy_counts,
    increment_signals_today,
    update_position_count,
    get_dual_leg_state,
    set_dual_leg_position,
    clear_dual_leg_position,
    increment_dual_leg_trade_count,
)
from app.webhooks.schemas import StandardSignal

logger = structlog.get_logger(__name__)


@dataclass
class SignalResult:
    strategy_id: str
    rule_result: str
    rule_detail: str | None = None
    execution_result: str | None = None
    execution_detail: dict | None = None
    parsed_signal: dict | None = None
    signal_id: uuid.UUID | None = None  # Set for live orders; used as WebhookSignal.id


async def _get_active_paper_session(session: AsyncSession, strategy_id: uuid.UUID):
    result = await session.execute(
        select(PaperTradingSession).where(
            PaperTradingSession.strategy_id == strategy_id,
            PaperTradingSession.status == "active",
        )
    )
    return result.scalar_one_or_none()


async def _execute_paper(
    session: AsyncSession,
    strategy: dict,
    signal: StandardSignal,
    tenant_id: uuid.UUID,
    signal_id: uuid.UUID,
) -> SignalResult:
    paper_session = await _get_active_paper_session(
        session, uuid.UUID(strategy["id"])
    )
    if not paper_session:
        return SignalResult(
            strategy_id=strategy["id"],
            rule_result="passed",
            parsed_signal=signal.model_dump(mode="json"),
            execution_result="no_active_session",
        )
    result = await execute_paper_trade(
        session, paper_session.id, tenant_id, signal, signal_id
    )
    return SignalResult(
        strategy_id=strategy["id"],
        rule_result="passed",
        parsed_signal=signal.model_dump(mode="json"),
        execution_result=result,
    )


def _is_position_not_found(execution_detail: dict) -> bool:
    """Return True if broker error indicates the position was already closed (Exchange1 9012)."""
    haystack = execution_detail.get("message", "") or execution_detail.get("error", "")
    return "9012" in haystack


def _is_stop_condition(dual_leg_config: dict, strategy: dict, trade_count: int) -> bool:
    """Return True if no new open legs should be placed."""
    max_trades = dual_leg_config.get("max_trades", 0)
    if max_trades and trade_count >= max_trades:
        return True
    if hours := strategy.get("rules", {}).get("trading_hours"):
        tz = ZoneInfo(hours.get("timezone", "Asia/Kolkata"))
        now_time = datetime.now(tz).time()
        start = datetime.strptime(hours["start"], "%H:%M").time()
        end = datetime.strptime(hours["end"], "%H:%M").time()
        if not (start <= now_time <= end):
            return True
    return False


async def _execute_dual_leg(
    strategy: dict,
    signal: StandardSignal,
    tenant_id: uuid.UUID,
    redis,
    dual_leg_config: dict,
) -> tuple[str, dict]:
    """Execute close-then-open legs for a dual-leg strategy.

    Returns (execution_result, execution_detail) where:
    - execution_result: "opened" | "reversed" | "closed" | "close_failed" |
                        "open_failed" | "no_action"
    - execution_detail: {"close": OrderResponse|None, "open": OrderResponse|None}
    """
    strategy_id = strategy["id"]
    broker_connection_id = strategy["broker_connection_id"]
    action = signal.action.upper()  # "BUY" or "SELL"
    opposite_action = "SELL" if action == "BUY" else "BUY"
    new_side = "long" if action == "BUY" else "short"
    current_side_map = {"BUY": "long", "SELL": "short"}
    existing_side_for_action = current_side_map[action]

    position_side, trade_count = await get_dual_leg_state(redis, strategy_id)
    stop = _is_stop_condition(dual_leg_config, strategy, trade_count)

    # Determine what to do
    same_side = (position_side == existing_side_for_action)
    need_close = (
        position_side != ""
        and (stop or position_side != existing_side_for_action)
    )
    need_open = not stop and (
        position_side == "" or position_side != existing_side_for_action
    )

    if same_side and not stop:
        return "no_action", {"close": None, "open": None}

    if not need_close and not need_open:
        return "no_action", {"close": None, "open": None}

    close_detail = None
    open_detail = None

    # --- Close leg ---
    if need_close:
        close_signal = StandardSignal(
            symbol=signal.symbol,
            exchange=signal.exchange,
            action=opposite_action,
            quantity=signal.quantity,
            order_type="MARKET",
            product_type=signal.product_type,
            leverage=signal.leverage,
            position_model=signal.position_model,
        )
        exec_result, exec_detail = await _place_live_order(
            broker_connection_id, tenant_id, strategy_id, close_signal, redis,
            update_redis=False,
        )

        if exec_result in ("filled", "accepted"):
            close_detail = exec_detail
            await clear_dual_leg_position(redis, strategy_id)
        elif _is_position_not_found(exec_detail):
            # Position already closed on exchange — treat as success
            close_detail = {"status": "already_closed"}
            await clear_dual_leg_position(redis, strategy_id)
        else:
            # Close genuinely failed — abort
            logger.warning(
                "dual_leg_close_failed",
                strategy_id=strategy_id,
                error=exec_detail.get("error"),
            )
            return "close_failed", {"close": exec_detail, "open": None}

    # --- Open leg ---
    if need_open:
        # Dual-leg open must explicitly set position_side so the broker adapter
        # routes correctly: BUY→long uses _open_futures, SELL→short uses _open_futures.
        # Without this, SELL with default position_side=None is treated as "close long".
        open_signal = signal.model_copy(update={"position_side": new_side})
        exec_result, exec_detail = await _place_live_order(
            broker_connection_id, tenant_id, strategy_id, open_signal, redis,
            update_redis=False,
        )
        open_detail = exec_detail

        if exec_result in ("filled", "accepted"):
            await set_dual_leg_position(redis, strategy_id, new_side)
            await increment_dual_leg_trade_count(redis, strategy_id)
            await increment_signals_today(redis, strategy_id)
            outcome = "reversed" if need_close else "opened"
        else:
            logger.warning(
                "dual_leg_open_failed",
                strategy_id=strategy_id,
                error=exec_detail.get("error"),
            )
            outcome = "open_failed"

        return outcome, {"close": close_detail, "open": open_detail}

    # Only close leg ran (stop condition)
    await increment_signals_today(redis, strategy_id)
    return "closed", {"close": close_detail, "open": None}


async def _place_live_order(
    broker_connection_id: str,
    tenant_id: uuid.UUID,
    strategy_id: str,
    signal: StandardSignal,
    redis,
    update_redis: bool = True,
) -> tuple[str, dict]:
    """Open own DB session, decrypt credentials, call broker.place_order().

    Returns (execution_result, execution_detail).
    When update_redis=True (default), updates Redis position/signal counters on success.
    Pass update_redis=False when the caller manages Redis state itself.
    Does NOT write to the WebhookSignal table (that is the router's job).
    """
    from app.brokers.base import OrderRequest as BrokerOrderRequest

    execution_result = "broker_error"
    execution_detail: dict = {}
    broker = None

    async with async_session_factory() as session:
        bc_result = await session.execute(
            select(BrokerConnection).where(
                BrokerConnection.id == uuid.UUID(broker_connection_id),
                BrokerConnection.tenant_id == tenant_id,
            )
        )
        bc = bc_result.scalar_one_or_none()
        if not bc:
            logger.error("live_order_broker_not_found", broker_connection_id=broker_connection_id)
            return "broker_not_found", {"error": "broker_connection_not_found"}

        try:
            creds = decrypt_credentials(tenant_id, bc.credentials)
            broker = await get_broker(bc.broker_type, creds)

            order_req = BrokerOrderRequest(
                symbol=signal.symbol,
                exchange=signal.exchange,
                action=signal.action,
                quantity=signal.quantity,
                order_type=signal.order_type or "MARKET",
                price=signal.price or Decimal("0"),
                product_type=signal.product_type or "DELIVERY",
                trigger_price=signal.trigger_price,
                leverage=signal.leverage,
                position_model=signal.position_model,
                position_side=signal.position_side,
                take_profit=signal.take_profit,
                stop_loss=signal.stop_loss,
            )
            order_response = await broker.place_order(order_req)
            execution_result = order_response.status
            execution_detail = order_response.model_dump(mode="json")
            logger.info(
                "live_order_placed",
                strategy_id=strategy_id,
                symbol=signal.symbol,
                action=signal.action,
                execution_result=execution_result,
                broker_order_id=execution_detail.get("order_id"),
            )
        except Exception as exc:
            execution_result = "broker_error"
            execution_detail = {"error": str(exc)}
            logger.error(
                "live_order_broker_error",
                strategy_id=strategy_id,
                symbol=signal.symbol,
                action=signal.action,
                error=str(exc),
            )
        finally:
            if broker is not None:
                await broker.close()

    # Update Redis position counter
    if update_redis and redis and execution_result in ("filled", "accepted"):
        await update_position_count(redis, strategy_id, signal.action)
        await increment_signals_today(redis, strategy_id)

    return execution_result, execution_detail


async def execute(
    strategies: list[dict],
    payload: dict,
    redis,
    session: AsyncSession,
    arq_redis=None,  # kept for interface compatibility; unused on primary path
    tenant_id: uuid.UUID | None = None,
) -> list[SignalResult]:
    """Process a webhook payload against a list of strategies.

    Live orders are placed synchronously (awaited) so the HTTP response
    reflects the real execution outcome and latency stays in milliseconds.
    Multiple live strategies are executed concurrently via asyncio.gather.
    Paper trades are also executed concurrently via asyncio.gather.
    """
    results: list[SignalResult] = []
    paper_tasks: list[asyncio.Task] = []
    paper_task_indices: list[int] = []
    live_tasks: list[asyncio.Task] = []
    live_task_indices: list[int] = []

    # Phase 1: map, evaluate rules, schedule coroutines
    for strategy in strategies:
        if not strategy.get("mapping_template"):
            results.append(SignalResult(
                strategy_id=strategy["id"],
                rule_result="no_mapping_template",
            ))
            continue

        # --- Mapping ---
        try:
            signal = apply_mapping(payload, strategy["mapping_template"])
        except Exception as exc:
            logger.warning(
                "signal_mapping_error",
                strategy_id=strategy["id"],
                strategy=strategy.get("name"),
                error=str(exc),
            )
            results.append(SignalResult(
                strategy_id=strategy["id"],
                rule_result="mapping_error",
                rule_detail=str(exc),
            ))
            continue

        # --- Rule evaluation ---
        open_positions, signals_today = await get_strategy_counts(
            redis, strategy["id"]
        )
        rule_out = evaluate_rules(
            signal,
            strategy["rules"] or {},
            open_positions=open_positions,
            signals_today=signals_today,
        )

        if not rule_out.passed:
            logger.info(
                "signal_rule_blocked",
                strategy_id=strategy["id"],
                strategy=strategy.get("name"),
                reason=rule_out.reason,
                symbol=signal.symbol,
                action=signal.action,
            )
            results.append(SignalResult(
                strategy_id=strategy["id"],
                rule_result="blocked_by_rule",
                rule_detail=rule_out.reason,
                parsed_signal=signal.model_dump(mode="json"),
            ))
            continue

        # --- Execution ---
        mode = strategy.get("mode", "log")

        if mode == "paper":
            signal_id = uuid.uuid4()
            idx = len(results)
            results.append(SignalResult(
                strategy_id=strategy["id"],
                rule_result="passed",
                parsed_signal=signal.model_dump(mode="json"),
            ))
            t = asyncio.create_task(
                _execute_paper(
                    session,
                    strategy,
                    signal,
                    tenant_id or uuid.uuid4(),
                    signal_id,
                )
            )
            paper_tasks.append(t)
            paper_task_indices.append(idx)

        elif mode == "live":
            if not strategy.get("broker_connection_id"):
                results.append(SignalResult(
                    strategy_id=strategy["id"],
                    rule_result="passed",
                    parsed_signal=signal.model_dump(mode="json"),
                    execution_result="no_broker_connection",
                ))
                continue

            if tenant_id is None:
                results.append(SignalResult(
                    strategy_id=strategy["id"],
                    rule_result="passed",
                    parsed_signal=signal.model_dump(mode="json"),
                    execution_result="no_tenant_id",
                ))
                continue

            signal_id = uuid.uuid4()
            idx = len(results)
            results.append(SignalResult(
                strategy_id=strategy["id"],
                rule_result="passed",
                parsed_signal=signal.model_dump(mode="json"),
                execution_result="pending",
                signal_id=signal_id,
            ))

            dual_leg_config = (strategy.get("rules") or {}).get("dual_leg", {})
            if dual_leg_config.get("enabled"):
                t = asyncio.create_task(
                    _execute_dual_leg(
                        strategy,
                        signal,
                        tenant_id,
                        redis,
                        dual_leg_config,
                    )
                )
            else:
                t = asyncio.create_task(
                    _place_live_order(
                        strategy["broker_connection_id"],
                        tenant_id,
                        strategy["id"],
                        signal,
                        redis,
                    )
                )
            logger.info(
                "live_order_started",
                strategy_id=strategy["id"],
                strategy=strategy.get("name"),
                symbol=signal.symbol,
                action=signal.action,
                dual_leg=bool(dual_leg_config.get("enabled")),
            )
            live_tasks.append(t)
            live_task_indices.append(idx)

        else:
            # "log" mode — signal recorded, no execution
            results.append(SignalResult(
                strategy_id=strategy["id"],
                rule_result="passed",
                parsed_signal=signal.model_dump(mode="json"),
                execution_result=None,
            ))

    # Phase 2: run live orders and paper trades concurrently
    all_tasks = live_tasks + paper_tasks
    all_indices = live_task_indices + paper_task_indices
    is_live = [True] * len(live_tasks) + [False] * len(paper_tasks)

    if all_tasks:
        all_results = await asyncio.gather(*all_tasks, return_exceptions=True)
        for idx, task_result, live in zip(all_indices, all_results, is_live):
            if isinstance(task_result, Exception):
                results[idx].execution_result = "error"
                results[idx].execution_detail = {"error": str(task_result)}
            elif live:
                execution_result, execution_detail = task_result
                results[idx].execution_result = execution_result
                results[idx].execution_detail = execution_detail
            else:
                # paper result
                results[idx].execution_result = task_result.execution_result
                results[idx].execution_detail = task_result.execution_detail
                if task_result.execution_result == "filled":
                    signal_data = results[idx].parsed_signal or {}
                    await update_position_count(
                        redis,
                        results[idx].strategy_id,
                        signal_data.get("action", ""),
                    )
                    await increment_signals_today(redis, results[idx].strategy_id)

    return results


# ---------------------------------------------------------------------------
# ARQ background task — used only by the recovery cron path
# ---------------------------------------------------------------------------

async def execute_live_order_task(ctx: dict, job_payload: dict) -> dict:
    """ARQ task: place a live broker order and update the WebhookSignal log.

    This task is only invoked by the recover_queued_signals cron.
    Normal webhook execution calls _place_live_order directly (synchronously).
    """
    _token = trace_id_var.set(job_payload.get("trace_id", ""))
    try:
        return await _execute_live_order(ctx, job_payload)
    finally:
        trace_id_var.reset(_token)


async def _execute_live_order(ctx: dict, job_payload: dict) -> dict:
    strategy_id = job_payload["strategy_id"]
    broker_connection_id = job_payload["broker_connection_id"]
    tenant_id = uuid.UUID(job_payload["tenant_id"])
    signal_data = job_payload["signal"]
    webhook_signal_id = uuid.UUID(job_payload["webhook_signal_id"])

    signal = StandardSignal(**{
        k: (Decimal(str(v)) if k in ("quantity", "price", "trigger_price", "take_profit", "stop_loss") and v is not None else v)
        for k, v in signal_data.items()
    })

    logger.info(
        "live_order_task_start",
        strategy_id=strategy_id,
        webhook_signal_id=str(webhook_signal_id),
        symbol=signal.symbol,
        action=signal.action,
        order_type=signal.order_type,
    )

    redis = ctx.get("redis")
    execution_result, execution_detail = await _place_live_order(
        broker_connection_id, tenant_id, strategy_id, signal, redis
    )

    # Update WebhookSignal log record
    async with async_session_factory() as session:
        ws_result = await session.execute(
            select(WebhookSignal).where(WebhookSignal.id == webhook_signal_id)
        )
        ws = ws_result.scalar_one_or_none()
        if ws:
            ws.execution_result = execution_result
            ws.execution_detail = execution_detail
            await session.commit()

    return {"execution_result": execution_result}


# ---------------------------------------------------------------------------
# Recovery cron — re-enqueue stuck "queued" signals
# ---------------------------------------------------------------------------

async def recover_queued_signals(ctx: dict) -> None:
    """Cron task: find WebhookSignals stuck in 'queued' state and re-enqueue them.

    A signal can get stuck if the ARQ worker was down when the job was first
    enqueued and the job expired from Redis before the worker came back up.
    Re-enqueueing uses the same _job_id so if the original job is still in
    the queue it won't be duplicated.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=3)
    arq_redis = ctx.get("redis")
    if arq_redis is None:
        return

    async with async_session_factory() as session:
        # Atomically mark matching signals as "recovering" to prevent concurrent
        # cron runs from double-enqueuing the same signal.
        result = await session.execute(
            select(WebhookSignal, Strategy)
            .join(Strategy, WebhookSignal.strategy_id == Strategy.id)
            .where(
                WebhookSignal.execution_result.in_(["queued", "recovering"]),
                WebhookSignal.received_at < cutoff,
                Strategy.mode == "live",
                Strategy.broker_connection_id.isnot(None),
            )
        )
        rows = result.all()
        if not rows:
            return

        signal_ids = [ws.id for ws, _ in rows]
        await session.execute(
            update(WebhookSignal)
            .where(WebhookSignal.id.in_(signal_ids))
            .values(execution_result="recovering")
        )
        await session.commit()

    recovered = 0
    for ws, strategy in rows:
        if ws.parsed_signal is None:
            logger.warning("recover_queued_signals: signal %s has no parsed_signal, skipping", ws.id)
            continue
        job_payload = {
            "strategy_id": str(strategy.id),
            "broker_connection_id": str(strategy.broker_connection_id),
            "tenant_id": str(ws.tenant_id),
            "signal": ws.parsed_signal,
            "webhook_signal_id": str(ws.id),
            "trace_id": f"recovery:{str(ws.id)[:8]}",
        }
        job_id = f"live-order:{ws.id}"
        await arq_redis.enqueue_job(
            "execute_live_order_task",
            job_payload,
            _job_id=job_id,
        )
        recovered += 1
        logger.info("recover_queued_signals: re-enqueued signal %s (job %s)", ws.id, job_id)

    if recovered:
        logger.info("recover_queued_signals: re-enqueued %d stuck signal(s)", recovered)
