# backend/app/webhooks/executor.py
"""Webhook execution pipeline.

execute()                  — public entry point called from router
execute_live_order_task()  — ARQ background task for live broker orders
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.brokers.factory import get_broker
from app.crypto.encryption import decrypt_credentials
from app.db.models import BrokerConnection, PaperTradingSession, WebhookSignal
from app.db.session import async_session_factory
from app.paper_trading.engine import execute_paper_trade
from app.webhooks.mapper import apply_mapping
from app.webhooks.processor import (
    evaluate_rules,
    get_strategy_counts,
    increment_signals_today,
    update_position_count,
)
from app.webhooks.schemas import StandardSignal


@dataclass
class SignalResult:
    strategy_id: str
    rule_result: str
    rule_detail: str | None = None
    execution_result: str | None = None
    execution_detail: dict | None = None
    parsed_signal: dict | None = None


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


async def execute(
    strategies: list[dict],
    payload: dict,
    redis,
    session: AsyncSession,
    arq_redis,
    tenant_id: uuid.UUID | None = None,
) -> list[SignalResult]:
    """Process a webhook payload against a list of strategies.

    Paper trades are executed concurrently.
    Live orders are enqueued as ARQ background jobs.
    """
    results: list[SignalResult] = []
    paper_tasks: list[asyncio.Task] = []
    paper_task_indices: list[int] = []

    # Phase 1: map, evaluate rules, enqueue live jobs
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
            job_payload = {
                "strategy_id": strategy["id"],
                "broker_connection_id": strategy["broker_connection_id"],
                "tenant_id": str(tenant_id),
                "signal": signal.model_dump(mode="json"),
                "webhook_signal_id": str(signal_id),
            }
            await arq_redis.enqueue_job(
                "execute_live_order_task",
                job_payload,
                _job_id=f"live-order:{signal_id}",
            )
            await increment_signals_today(redis, strategy["id"])
            results.append(SignalResult(
                strategy_id=strategy["id"],
                rule_result="passed",
                parsed_signal=signal.model_dump(mode="json"),
                execution_result="queued",
                execution_detail={"job_id": f"live-order:{signal_id}"},
            ))

        else:
            # "log" mode — signal recorded, no execution
            results.append(SignalResult(
                strategy_id=strategy["id"],
                rule_result="passed",
                parsed_signal=signal.model_dump(mode="json"),
                execution_result=None,
            ))

    # Phase 2: run paper trades concurrently
    if paper_tasks:
        paper_results = await asyncio.gather(*paper_tasks, return_exceptions=True)
        for idx, paper_result in zip(paper_task_indices, paper_results):
            if isinstance(paper_result, Exception):
                results[idx].execution_result = "error"
                results[idx].execution_detail = {"error": str(paper_result)}
            else:
                results[idx].execution_result = paper_result.execution_result
                results[idx].execution_detail = paper_result.execution_detail
                # Update Redis position counter for successful paper trades
                if paper_result.execution_result == "filled":
                    signal_data = results[idx].parsed_signal or {}
                    await update_position_count(
                        redis,
                        results[idx].strategy_id,
                        signal_data.get("action", ""),
                    )
                    await increment_signals_today(redis, results[idx].strategy_id)

    return results


# ---------------------------------------------------------------------------
# ARQ background task — live broker order execution
# ---------------------------------------------------------------------------

async def execute_live_order_task(ctx: dict, job_payload: dict) -> dict:
    """ARQ task: place a live broker order and update the WebhookSignal log."""
    strategy_id = job_payload["strategy_id"]
    broker_connection_id = job_payload["broker_connection_id"]
    tenant_id = uuid.UUID(job_payload["tenant_id"])
    signal_data = job_payload["signal"]
    webhook_signal_id = uuid.UUID(job_payload["webhook_signal_id"])

    signal = StandardSignal(**{
        k: (Decimal(str(v)) if k in ("quantity", "price", "trigger_price", "take_profit", "stop_loss") and v is not None else v)
        for k, v in signal_data.items()
    })

    async with async_session_factory() as session:
        # Fetch broker connection
        bc_result = await session.execute(
            select(BrokerConnection).where(
                BrokerConnection.id == uuid.UUID(broker_connection_id),
                BrokerConnection.tenant_id == tenant_id,
            )
        )
        bc = bc_result.scalar_one_or_none()
        if not bc:
            return {"error": "broker_connection_not_found"}

        execution_result = "broker_error"
        execution_detail: dict = {}
        broker = None

        try:
            creds = decrypt_credentials(tenant_id, bc.credentials)
            broker = await get_broker(bc.broker_type, creds)

            from app.brokers.base import OrderRequest as BrokerOrderRequest
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
        except Exception as exc:
            execution_result = "broker_error"
            execution_detail = {"error": str(exc)}
        finally:
            if broker is not None:
                await broker.close()

        # Update WebhookSignal log record
        ws_result = await session.execute(
            select(WebhookSignal).where(WebhookSignal.id == webhook_signal_id)
        )
        ws = ws_result.scalar_one_or_none()
        if ws:
            ws.execution_result = execution_result
            ws.execution_detail = execution_detail
            await session.commit()

        # Update Redis position counter
        redis = ctx.get("redis")
        if redis and execution_result in ("filled", "accepted"):
            await update_position_count(redis, strategy_id, signal.action)

    return {"execution_result": execution_result}
