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
