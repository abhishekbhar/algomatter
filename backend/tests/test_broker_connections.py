import pytest
from tests.conftest import create_authenticated_user


@pytest.mark.asyncio
async def test_create_broker_connection(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["broker_type"] == "zerodha"
    assert "credentials" not in data  # credentials must not be in response
    assert "id" in data
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_list_broker_connections(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    resp = await client.get("/api/v1/brokers", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_delete_broker_connection(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    create_resp = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    conn_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/brokers/{conn_id}", headers=headers)
    assert resp.status_code == 204

    # Verify it's gone
    list_resp = await client.get("/api/v1/brokers", headers=headers)
    assert len(list_resp.json()) == 0


@pytest.mark.asyncio
async def test_rls_isolation_broker_connections(client):
    # User A creates a connection
    tokens_a = await create_authenticated_user(client, email="a@test.com")
    headers_a = {"Authorization": f"Bearer {tokens_a['access_token']}"}
    await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers_a,
    )

    # User B should not see it
    tokens_b = await create_authenticated_user(client, email="b@test.com")
    headers_b = {"Authorization": f"Bearer {tokens_b['access_token']}"}
    resp = await client.get("/api/v1/brokers", headers=headers_b)
    assert resp.status_code == 200
    assert len(resp.json()) == 0


import uuid as uuid_mod
from app.db.models import StrategyCode, StrategyCodeVersion, StrategyDeployment, DeploymentState, DeploymentTrade
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session_factory
from datetime import datetime, UTC


@pytest.mark.asyncio
async def test_get_broker_stats_with_data(client):
    tokens = await create_authenticated_user(client, email="stats0@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    broker_resp = await client.post(
        "/api/v1/brokers",
        json={"broker_type": "exchange1", "credentials": {"api_key": "k", "private_key": "p"}},
        headers=headers,
    )
    broker_id = broker_resp.json()["id"]

    async with async_session_factory() as session:
        me_resp = await client.get("/api/v1/auth/me", headers=headers)
        tenant_id = uuid_mod.UUID(me_resp.json()["id"])

        code = StrategyCode(id=uuid_mod.uuid4(), tenant_id=tenant_id, name="My Strat", code="pass")
        session.add(code)
        await session.flush()
        version = StrategyCodeVersion(
            id=uuid_mod.uuid4(), tenant_id=tenant_id, strategy_code_id=code.id, version=1, code="pass"
        )
        session.add(version)
        await session.flush()
        dep = StrategyDeployment(
            id=uuid_mod.uuid4(), tenant_id=tenant_id,
            strategy_code_id=code.id, strategy_code_version_id=version.id,
            mode="live", status="running", symbol="BTCUSDT",
            exchange="EXCHANGE1", product_type="FUTURES", interval="1h",
            broker_connection_id=uuid_mod.UUID(broker_id),
        )
        session.add(dep)
        await session.flush()
        state = DeploymentState(
            deployment_id=dep.id, tenant_id=tenant_id,
            position={"quantity": 0.05, "avg_entry_price": 83200.0, "unrealized_pnl": 124.5},
            open_orders=[{"id": "o1", "action": "BUY", "quantity": 0.1, "order_type": "LIMIT", "price": 82000.0}],
            portfolio={}, user_state={},
        )
        session.add(state)
        trade = DeploymentTrade(
            id=uuid_mod.uuid4(), tenant_id=tenant_id, deployment_id=dep.id,
            order_id="ord0", action="BUY", quantity=0.05, order_type="market",
            status="filled", fill_price=83000.0, fill_quantity=0.05,
            realized_pnl=100.0, created_at=datetime.now(UTC),
        )
        session.add(trade)
        await session.commit()

    resp = await client.get(f"/api/v1/brokers/{broker_id}/stats", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_deployments"] == 1
    assert data["total_trades"] == 1
    assert data["total_realized_pnl"] == 100.0
    assert data["win_rate"] == 1.0


@pytest.mark.asyncio
async def test_get_broker_positions_with_data(client):
    tokens = await create_authenticated_user(client, email="pos0@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    broker_resp = await client.post(
        "/api/v1/brokers",
        json={"broker_type": "exchange1", "credentials": {"api_key": "k", "private_key": "p"}},
        headers=headers,
    )
    broker_id = broker_resp.json()["id"]

    async with async_session_factory() as session:
        me_resp = await client.get("/api/v1/auth/me", headers=headers)
        tenant_id = uuid_mod.UUID(me_resp.json()["id"])

        code = StrategyCode(id=uuid_mod.uuid4(), tenant_id=tenant_id, name="BTC Strat", code="pass")
        session.add(code)
        await session.flush()
        version = StrategyCodeVersion(
            id=uuid_mod.uuid4(), tenant_id=tenant_id, strategy_code_id=code.id, version=1, code="pass"
        )
        session.add(version)
        await session.flush()
        dep = StrategyDeployment(
            id=uuid_mod.uuid4(), tenant_id=tenant_id,
            strategy_code_id=code.id, strategy_code_version_id=version.id,
            mode="live", status="running", symbol="BTCUSDT",
            exchange="EXCHANGE1", product_type="FUTURES", interval="1h",
            broker_connection_id=uuid_mod.UUID(broker_id),
        )
        session.add(dep)
        await session.flush()
        state = DeploymentState(
            deployment_id=dep.id, tenant_id=tenant_id,
            position={"quantity": 0.05, "avg_entry_price": 83200.0, "unrealized_pnl": 124.5},
            open_orders=[], portfolio={}, user_state={},
        )
        session.add(state)
        await session.commit()

    resp = await client.get(f"/api/v1/brokers/{broker_id}/positions", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "BTCUSDT"
    assert data[0]["side"] == "LONG"
    assert data[0]["deployment_name"] == "BTC Strat"
    assert data[0]["quantity"] == 0.05


@pytest.mark.asyncio
async def test_get_broker_orders_with_data(client):
    tokens = await create_authenticated_user(client, email="ord0@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    broker_resp = await client.post(
        "/api/v1/brokers",
        json={"broker_type": "exchange1", "credentials": {"api_key": "k", "private_key": "p"}},
        headers=headers,
    )
    broker_id = broker_resp.json()["id"]

    async with async_session_factory() as session:
        me_resp = await client.get("/api/v1/auth/me", headers=headers)
        tenant_id = uuid_mod.UUID(me_resp.json()["id"])

        code = StrategyCode(id=uuid_mod.uuid4(), tenant_id=tenant_id, name="ETH Strat", code="pass")
        session.add(code)
        await session.flush()
        version = StrategyCodeVersion(
            id=uuid_mod.uuid4(), tenant_id=tenant_id, strategy_code_id=code.id, version=1, code="pass"
        )
        session.add(version)
        await session.flush()
        dep = StrategyDeployment(
            id=uuid_mod.uuid4(), tenant_id=tenant_id,
            strategy_code_id=code.id, strategy_code_version_id=version.id,
            mode="live", status="running", symbol="ETHUSDT",
            exchange="EXCHANGE1", product_type="FUTURES", interval="1h",
            broker_connection_id=uuid_mod.UUID(broker_id),
        )
        session.add(dep)
        await session.flush()
        state = DeploymentState(
            deployment_id=dep.id, tenant_id=tenant_id,
            position=None,
            open_orders=[{"id": "o1", "action": "SELL", "quantity": 0.5, "order_type": "LIMIT", "price": 3200.0}],
            portfolio={}, user_state={},
        )
        session.add(state)
        await session.commit()

    resp = await client.get(f"/api/v1/brokers/{broker_id}/orders", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "ETHUSDT"
    assert data[0]["action"] == "SELL"
    assert data[0]["deployment_name"] == "ETH Strat"


@pytest.mark.asyncio
async def test_get_broker_trades_with_data(client):
    tokens = await create_authenticated_user(client, email="trd0@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    broker_resp = await client.post(
        "/api/v1/brokers",
        json={"broker_type": "exchange1", "credentials": {"api_key": "k", "private_key": "p"}},
        headers=headers,
    )
    broker_id = broker_resp.json()["id"]

    async with async_session_factory() as session:
        me_resp = await client.get("/api/v1/auth/me", headers=headers)
        tenant_id = uuid_mod.UUID(me_resp.json()["id"])

        code = StrategyCode(id=uuid_mod.uuid4(), tenant_id=tenant_id, name="SOL Strat", code="pass")
        session.add(code)
        await session.flush()
        version = StrategyCodeVersion(
            id=uuid_mod.uuid4(), tenant_id=tenant_id, strategy_code_id=code.id, version=1, code="pass"
        )
        session.add(version)
        await session.flush()
        dep = StrategyDeployment(
            id=uuid_mod.uuid4(), tenant_id=tenant_id,
            strategy_code_id=code.id, strategy_code_version_id=version.id,
            mode="live", status="running", symbol="SOLUSDT",
            exchange="EXCHANGE1", product_type="FUTURES", interval="1h",
            broker_connection_id=uuid_mod.UUID(broker_id),
        )
        session.add(dep)
        await session.flush()
        trade = DeploymentTrade(
            id=uuid_mod.uuid4(), tenant_id=tenant_id, deployment_id=dep.id,
            order_id="ord1", action="BUY", quantity=2.0, order_type="market",
            status="filled", fill_price=142.0, fill_quantity=2.0,
            realized_pnl=6.0, created_at=datetime.now(UTC),
        )
        session.add(trade)
        await session.commit()

    resp = await client.get(f"/api/v1/brokers/{broker_id}/trades", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["trades"]) == 1
    assert data["trades"][0]["symbol"] == "SOLUSDT"
    assert data["trades"][0]["strategy_name"] == "SOL Strat"
    assert data["trades"][0]["realized_pnl"] == 6.0


@pytest.mark.asyncio
async def test_get_broker_stats_empty(client):
    tokens = await create_authenticated_user(client, email="stats1@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    broker_resp = await client.post(
        "/api/v1/brokers",
        json={"broker_type": "exchange1", "credentials": {"api_key": "k", "private_key": "p"}},
        headers=headers,
    )
    broker_id = broker_resp.json()["id"]
    resp = await client.get(f"/api/v1/brokers/{broker_id}/stats", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_deployments"] == 0
    assert data["total_trades"] == 0
    assert data["win_rate"] == 0.0


@pytest.mark.asyncio
async def test_get_broker_stats_404(client):
    tokens = await create_authenticated_user(client, email="stats2@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = await client.get(f"/api/v1/brokers/{uuid_mod.uuid4()}/stats", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_broker_positions(client):
    tokens = await create_authenticated_user(client, email="pos1@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    broker_resp = await client.post(
        "/api/v1/brokers",
        json={"broker_type": "exchange1", "credentials": {"api_key": "k", "private_key": "p"}},
        headers=headers,
    )
    broker_id = broker_resp.json()["id"]

    resp = await client.get(f"/api/v1/brokers/{broker_id}/positions", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_broker_positions_404(client):
    tokens = await create_authenticated_user(client, email="pos2@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = await client.get(f"/api/v1/brokers/{uuid_mod.uuid4()}/positions", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_broker_orders_empty(client):
    tokens = await create_authenticated_user(client, email="ord1@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    broker_resp = await client.post(
        "/api/v1/brokers",
        json={"broker_type": "exchange1", "credentials": {"api_key": "k", "private_key": "p"}},
        headers=headers,
    )
    broker_id = broker_resp.json()["id"]
    resp = await client.get(f"/api/v1/brokers/{broker_id}/orders", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_broker_orders_404(client):
    tokens = await create_authenticated_user(client, email="ord2@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = await client.get(f"/api/v1/brokers/{uuid_mod.uuid4()}/orders", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_broker_trades_empty(client):
    tokens = await create_authenticated_user(client, email="trd1@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    broker_resp = await client.post(
        "/api/v1/brokers",
        json={"broker_type": "exchange1", "credentials": {"api_key": "k", "private_key": "p"}},
        headers=headers,
    )
    broker_id = broker_resp.json()["id"]
    resp = await client.get(f"/api/v1/brokers/{broker_id}/trades", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["trades"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_get_broker_trades_404(client):
    tokens = await create_authenticated_user(client, email="trd2@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = await client.get(f"/api/v1/brokers/{uuid_mod.uuid4()}/trades", headers=headers)
    assert resp.status_code == 404
