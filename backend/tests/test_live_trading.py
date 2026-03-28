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


## ─── dispatch_orders DeploymentTrade integration tests ──────────────────────


@pytest.mark.asyncio
async def test_dispatch_orders_creates_trade_record(db_session):
    """dispatch_orders() should create a DeploymentTrade row for paper orders."""
    from app.strategy_runner.order_router import dispatch_orders

    user = User(email="dispatch@test.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    tenant_id = user.id

    sc = StrategyCode(tenant_id=tenant_id, name="Test", description="", code="pass", entrypoint="Strategy", version=1)
    db_session.add(sc)
    await db_session.flush()

    scv = StrategyCodeVersion(tenant_id=tenant_id, strategy_code_id=sc.id, version=1, code="pass")
    db_session.add(scv)
    await db_session.flush()

    dep = StrategyDeployment(
        tenant_id=tenant_id, strategy_code_id=sc.id, strategy_code_version_id=scv.id,
        mode="paper", status="running", symbol="BTCUSDT", exchange="exchange1", interval="5m",
    )
    db_session.add(dep)
    await db_session.flush()

    orders = [{"id": "order1", "action": "buy", "quantity": 1.0, "order_type": "market"}]
    results = await dispatch_orders(orders, dep, db_session)
    await db_session.commit()

    assert len(results) == 1
    assert results[0]["status"] == "submitted"

    trade_result = await db_session.execute(
        select(DeploymentTrade).where(DeploymentTrade.deployment_id == dep.id)
    )
    trade = trade_result.scalar_one()
    assert trade.order_id == "order1"
    assert trade.action == "BUY"
    assert trade.status == "filled"  # paper mode fills immediately


@pytest.mark.asyncio
async def test_dispatch_orders_rejected_creates_trade_record(db_session):
    """Rejected orders (unsupported type) still get a trade record with rejected status."""
    from app.strategy_runner.order_router import dispatch_orders

    user = User(email="dispatch2@test.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    tenant_id = user.id

    sc = StrategyCode(tenant_id=tenant_id, name="Test", description="", code="pass", entrypoint="Strategy", version=1)
    db_session.add(sc)
    await db_session.flush()

    scv = StrategyCodeVersion(tenant_id=tenant_id, strategy_code_id=sc.id, version=1, code="pass")
    db_session.add(scv)
    await db_session.flush()

    dep = StrategyDeployment(
        tenant_id=tenant_id, strategy_code_id=sc.id, strategy_code_version_id=scv.id,
        mode="paper", status="running", symbol="BTCUSDT", exchange="exchange1", interval="5m",
    )
    db_session.add(dep)
    await db_session.flush()

    orders = [{"id": "order2", "action": "buy", "quantity": 1.0, "order_type": "stop"}]
    results = await dispatch_orders(orders, dep, db_session)
    await db_session.commit()

    assert results[0]["status"] == "rejected"

    trade_result = await db_session.execute(
        select(DeploymentTrade).where(DeploymentTrade.deployment_id == dep.id)
    )
    trade = trade_result.scalar_one()
    assert trade.status == "rejected"


## ─── Read-only trade endpoint tests ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_trades_endpoint(client, db_session):
    tokens = await create_authenticated_user(client)
    strategy, deployment = await _create_strategy_and_deployment(client, tokens, db_session)

    dep_id = uuid.UUID(deployment["id"])
    result = await db_session.execute(
        select(StrategyDeployment).where(StrategyDeployment.id == dep_id)
    )
    dep = result.scalar_one()

    trade = DeploymentTrade(
        tenant_id=dep.tenant_id, deployment_id=dep.id, order_id="t1",
        action="BUY", quantity=1.0, order_type="MARKET", status="filled", is_manual=False,
    )
    db_session.add(trade)
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/deployments/{deployment['id']}/trades",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["trades"][0]["order_id"] == "t1"
    assert "strategy_name" in data["trades"][0]
    assert "symbol" in data["trades"][0]


@pytest.mark.asyncio
async def test_get_position_endpoint(client, db_session):
    tokens = await create_authenticated_user(client)
    strategy, deployment = await _create_strategy_and_deployment(client, tokens, db_session)

    dep_id = uuid.UUID(deployment["id"])
    result = await db_session.execute(
        select(StrategyDeployment).where(StrategyDeployment.id == dep_id)
    )
    dep = result.scalar_one()

    # Update the existing DeploymentState created during deployment creation
    state_result = await db_session.execute(
        select(DeploymentState).where(DeploymentState.deployment_id == dep.id)
    )
    state = state_result.scalar_one()
    state.position = {"quantity": 1.0, "avg_entry_price": 100.0, "unrealized_pnl": 5.0}
    state.portfolio = {"balance": 10000, "equity": 10005, "available_margin": 9000}
    state.open_orders = [{"id": "o1"}]
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/deployments/{deployment['id']}/position",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["position"]["quantity"] == 1.0
    assert data["open_orders_count"] == 1
    assert len(data["open_orders"]) == 1


@pytest.mark.asyncio
async def test_recent_trades_endpoint(client, db_session):
    tokens = await create_authenticated_user(client)
    strategy, deployment = await _create_strategy_and_deployment(client, tokens, db_session)

    dep_id = uuid.UUID(deployment["id"])
    result = await db_session.execute(
        select(StrategyDeployment).where(StrategyDeployment.id == dep_id)
    )
    dep = result.scalar_one()

    trade = DeploymentTrade(
        tenant_id=dep.tenant_id, deployment_id=dep.id, order_id="rt1",
        action="BUY", quantity=1.0, order_type="MARKET", status="filled", is_manual=False,
    )
    db_session.add(trade)
    await db_session.commit()

    resp = await client.get(
        "/api/v1/deployments/recent-trades?limit=10",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["trades"]) >= 1
