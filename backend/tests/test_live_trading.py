"""Tests for Live Trading features — DeploymentTrade model and endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.db.models import (
    DeploymentTrade,
    StrategyCode,
    StrategyCodeVersion,
    StrategyDeployment,
    DeploymentState,
    User,
)
from tests.conftest import create_authenticated_user


@pytest.mark.asyncio
async def test_deployment_trade_model_create(db_session):
    """DeploymentTrade can be created and queried."""
    user = User(email="test@example.com", password_hash="fakehash")
    db_session.add(user)
    await db_session.flush()
    tenant_id = user.id

    sc = StrategyCode(
        tenant_id=tenant_id, name="Test", description="", code="pass", entrypoint="Strategy", version=1
    )
    db_session.add(sc)
    await db_session.flush()

    scv = StrategyCodeVersion(tenant_id=tenant_id, strategy_code_id=sc.id, version=1, code="pass")
    db_session.add(scv)
    await db_session.flush()

    dep = StrategyDeployment(
        tenant_id=tenant_id,
        strategy_code_id=sc.id,
        strategy_code_version_id=scv.id,
        mode="paper",
        status="running",
        symbol="BTCUSDT",
        exchange="exchange1",
        interval="5m",
    )
    db_session.add(dep)
    await db_session.flush()

    trade = DeploymentTrade(
        tenant_id=tenant_id,
        deployment_id=dep.id,
        order_id="abc123",
        action="BUY",
        quantity=1.0,
        order_type="MARKET",
        status="submitted",
        is_manual=False,
    )
    db_session.add(trade)
    await db_session.commit()

    result = await db_session.execute(
        select(DeploymentTrade).where(DeploymentTrade.deployment_id == dep.id)
    )
    row = result.scalar_one()
    assert row.order_id == "abc123"
    assert row.action == "BUY"
    assert row.status == "submitted"
    assert row.is_manual is False
    assert row.realized_pnl is None
    assert row.fill_price is None


async def _create_strategy_and_deployment(client, tokens, db_session, *, mode="paper", status="running"):
    """Helper: create a hosted strategy + deployment, return (strategy, deployment) dicts."""
    resp = await client.post(
        "/api/v1/hosted-strategies",
        json={"name": "SMA Bot", "description": "test", "code": "class Strategy:\n  pass", "entrypoint": "Strategy"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 201
    strategy = resp.json()

    resp = await client.post(
        f"/api/v1/hosted-strategies/{strategy['id']}/deployments",
        json={"mode": mode, "symbol": "BTCUSDT", "exchange": "exchange1", "interval": "5m"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 201
    deployment = resp.json()

    if status != "pending":
        from sqlalchemy import update
        from app.db.models import StrategyDeployment
        await db_session.execute(
            update(StrategyDeployment)
            .where(StrategyDeployment.id == uuid.UUID(deployment["id"]))
            .values(status=status, started_at=datetime.now(UTC))
        )
        await db_session.commit()

    return strategy, deployment


## ─── Trade Service (pure-function) tests ───────────────────────────────────


def test_compute_pnl_closing_long():
    from app.deployments.trade_service import compute_pnl

    pnl = compute_pnl(action="SELL", fill_price=110.0, fill_quantity=2.0, avg_entry_price=100.0)
    assert pnl == 20.0


def test_compute_pnl_closing_short():
    from app.deployments.trade_service import compute_pnl

    pnl = compute_pnl(action="BUY", fill_price=90.0, fill_quantity=2.0, avg_entry_price=100.0)
    assert pnl == 20.0


def test_compute_pnl_opening_position():
    from app.deployments.trade_service import compute_pnl

    pnl = compute_pnl(action="BUY", fill_price=100.0, fill_quantity=1.0, avg_entry_price=None)
    assert pnl is None


def test_compute_live_metrics_with_trades():
    from app.deployments.trade_service import compute_live_metrics

    trades = [
        {"pnl": 50.0},
        {"pnl": -20.0},
        {"pnl": 30.0},
        {"pnl": -10.0},
    ]
    result = compute_live_metrics(trades, initial_capital=1000.0)
    assert result["total_trades"] == 4
    assert result["win_rate"] == 50.0
    assert result["best_trade"] == 50.0
    assert result["worst_trade"] == -20.0
    assert result["avg_trade_pnl"] == 12.5


def test_compute_live_metrics_zero_trades():
    from app.deployments.trade_service import compute_live_metrics

    result = compute_live_metrics([], initial_capital=1000.0)
    assert result["total_trades"] == 0
    assert result["best_trade"] is None
    assert result["worst_trade"] is None
    assert result["win_rate"] == 0.0


def test_build_equity_curve():
    from app.deployments.trade_service import build_equity_curve

    pnls = [10.0, -5.0, 20.0]
    curve = build_equity_curve(pnls, initial_capital=1000.0)
    assert len(curve) == 4
    assert curve[0]["equity"] == 1000.0
    assert curve[1]["equity"] == 1010.0
    assert curve[2]["equity"] == 1005.0
    assert curve[3]["equity"] == 1025.0


## ─── Integration tests (async, DB-backed) ──────────────────────────────────


@pytest.mark.asyncio
async def test_deployment_response_includes_strategy_name(client, db_session):
    tokens = await create_authenticated_user(client)
    strategy, deployment = await _create_strategy_and_deployment(client, tokens, db_session)
    resp = await client.get(
        f"/api/v1/deployments/{deployment['id']}",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "strategy_name" in data
    assert data["strategy_name"] == "SMA Bot"
