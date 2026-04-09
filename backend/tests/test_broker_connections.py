import uuid as uuid_mod
from datetime import datetime, UTC

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.brokers.schemas import (
    CreateBrokerConnectionRequest,
    UpdateBrokerConnectionRequest,
)
from app.db.models import (
    DeploymentState,
    DeploymentTrade,
    Strategy,
    StrategyCode,
    StrategyCodeVersion,
    StrategyDeployment,
)
from app.db.session import async_session_factory
from tests.conftest import create_authenticated_user


@pytest.mark.asyncio
async def test_create_broker_connection(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "label": "Create Test",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["broker_type"] == "zerodha"
    assert data["label"] == "Create Test"
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
            "label": "List Test",
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
            "label": "Delete Test",
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
            "label": "RLS A",
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


@pytest.mark.asyncio
async def test_get_broker_stats_with_data(client):
    tokens = await create_authenticated_user(client, email="stats0@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    broker_resp = await client.post(
        "/api/v1/brokers",
        json={"broker_type": "exchange1", "label": "Stats With Data", "credentials": {"api_key": "k", "private_key": "p"}},
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
        json={"broker_type": "exchange1", "label": "Positions With Data", "credentials": {"api_key": "k", "private_key": "p"}},
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
        json={"broker_type": "exchange1", "label": "Orders With Data", "credentials": {"api_key": "k", "private_key": "p"}},
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
        json={"broker_type": "exchange1", "label": "Trades With Data", "credentials": {"api_key": "k", "private_key": "p"}},
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
        json={"broker_type": "exchange1", "label": "Stats Empty", "credentials": {"api_key": "k", "private_key": "p"}},
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
        json={"broker_type": "exchange1", "label": "Positions Empty", "credentials": {"api_key": "k", "private_key": "p"}},
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
        json={"broker_type": "exchange1", "label": "Orders Empty", "credentials": {"api_key": "k", "private_key": "p"}},
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
        json={"broker_type": "exchange1", "label": "Trades Empty", "credentials": {"api_key": "k", "private_key": "p"}},
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


@pytest.mark.asyncio
async def test_rls_isolation_broker_detail_endpoints(client):
    """User B cannot access User A's broker stats/positions/orders/trades."""
    tokens_a = await create_authenticated_user(client, email="rls_a@test.com")
    headers_a = {"Authorization": f"Bearer {tokens_a['access_token']}"}
    broker_resp = await client.post(
        "/api/v1/brokers",
        json={"broker_type": "exchange1", "label": "RLS Detail A", "credentials": {"api_key": "k", "private_key": "p"}},
        headers=headers_a,
    )
    broker_id = broker_resp.json()["id"]

    tokens_b = await create_authenticated_user(client, email="rls_b@test.com")
    headers_b = {"Authorization": f"Bearer {tokens_b['access_token']}"}

    for endpoint in ["stats", "positions", "orders", "trades"]:
        resp = await client.get(f"/api/v1/brokers/{broker_id}/{endpoint}", headers=headers_b)
        assert resp.status_code == 404, f"Expected 404 for {endpoint}, got {resp.status_code}"


@pytest.mark.asyncio
async def test_create_broker_connection_returns_422_without_label(client):
    tokens = await create_authenticated_user(client, email="nolabel@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_broker_connection_trims_label(client):
    tokens = await create_authenticated_user(client, email="trim@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "label": "   Padded   ",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["label"] == "Padded"


@pytest.mark.asyncio
async def test_create_broker_connection_duplicate_label_returns_409(client):
    tokens = await create_authenticated_user(client, email="dup@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    payload = {
        "broker_type": "zerodha",
        "label": "Duplicate",
        "credentials": {"api_key": "xxx", "api_secret": "yyy"},
    }
    first = await client.post("/api/v1/brokers", json=payload, headers=headers)
    assert first.status_code == 201

    second = await client.post("/api/v1/brokers", json=payload, headers=headers)
    assert second.status_code == 409
    assert "already exists" in second.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_broker_connection_same_label_different_tenants_ok(client):
    tokens_a = await create_authenticated_user(client, email="tenant_a@test.com")
    tokens_b = await create_authenticated_user(client, email="tenant_b@test.com")
    payload = {
        "broker_type": "zerodha",
        "label": "Shared Name",
        "credentials": {"api_key": "xxx", "api_secret": "yyy"},
    }
    resp_a = await client.post(
        "/api/v1/brokers",
        json=payload,
        headers={"Authorization": f"Bearer {tokens_a['access_token']}"},
    )
    resp_b = await client.post(
        "/api/v1/brokers",
        json=payload,
        headers={"Authorization": f"Bearer {tokens_b['access_token']}"},
    )
    assert resp_a.status_code == 201
    assert resp_b.status_code == 201


@pytest.mark.asyncio
async def test_list_broker_connections_includes_label(client):
    tokens = await create_authenticated_user(client, email="listlabel@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "label": "Main Account",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    resp = await client.get("/api/v1/brokers", headers=headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["label"] == "Main Account"


@pytest.mark.asyncio
async def test_patch_broker_connection_renames_label(client):
    tokens = await create_authenticated_user(client, email="rename@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    create = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "label": "Original",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    conn_id = create.json()["id"]

    resp = await client.patch(
        f"/api/v1/brokers/{conn_id}",
        json={"label": "Renamed"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == conn_id
    assert body["label"] == "Renamed"
    assert "credentials" not in body


@pytest.mark.asyncio
async def test_patch_broker_connection_trims_label(client):
    tokens = await create_authenticated_user(client, email="rename_trim@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    create = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "label": "Pre-trim",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    conn_id = create.json()["id"]

    resp = await client.patch(
        f"/api/v1/brokers/{conn_id}",
        json={"label": "   Post-trim   "},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["label"] == "Post-trim"


@pytest.mark.asyncio
async def test_patch_broker_connection_rejects_blank_label(client):
    tokens = await create_authenticated_user(client, email="rename_blank@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    create = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "label": "Blank Source",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    conn_id = create.json()["id"]

    resp = await client.patch(
        f"/api/v1/brokers/{conn_id}",
        json={"label": "   "},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_broker_connection_rename_to_existing_returns_409(client):
    tokens = await create_authenticated_user(client, email="rename_conflict@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "label": "Taken",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    other = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "label": "Other",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    other_id = other.json()["id"]

    resp = await client.patch(
        f"/api/v1/brokers/{other_id}",
        json={"label": "Taken"},
        headers=headers,
    )
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_patch_broker_connection_rename_to_own_current_label_is_ok(client):
    tokens = await create_authenticated_user(client, email="rename_self@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    create = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "label": "Self",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers,
    )
    conn_id = create.json()["id"]

    resp = await client.patch(
        f"/api/v1/brokers/{conn_id}",
        json={"label": "Self"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["label"] == "Self"


@pytest.mark.asyncio
async def test_patch_broker_connection_not_found_returns_404(client):
    tokens = await create_authenticated_user(client, email="rename_missing@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = await client.patch(
        "/api/v1/brokers/00000000-0000-0000-0000-000000000000",
        json={"label": "Nope"},
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_broker_connection_other_tenant_returns_404(client):
    tokens_a = await create_authenticated_user(client, email="cross_a@test.com")
    tokens_b = await create_authenticated_user(client, email="cross_b@test.com")
    headers_a = {"Authorization": f"Bearer {tokens_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {tokens_b['access_token']}"}

    create_a = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "zerodha",
            "label": "A's broker",
            "credentials": {"api_key": "xxx", "api_secret": "yyy"},
        },
        headers=headers_a,
    )
    a_id = create_a.json()["id"]

    resp = await client.patch(
        f"/api/v1/brokers/{a_id}",
        json={"label": "Hijacked"},
        headers=headers_b,
    )
    assert resp.status_code == 404


# -----------------------------------------------------------------------------
# validate_label — schema-layer unit tests
# -----------------------------------------------------------------------------

def _valid_creds():
    return {"api_key": "k", "api_secret": "s"}


def test_create_schema_requires_label():
    with pytest.raises(ValidationError):
        CreateBrokerConnectionRequest(broker_type="zerodha", credentials=_valid_creds())


def test_create_schema_rejects_blank_label():
    with pytest.raises(ValidationError):
        CreateBrokerConnectionRequest(
            broker_type="zerodha", label="   ", credentials=_valid_creds()
        )


def test_create_schema_rejects_too_long_label():
    with pytest.raises(ValidationError):
        CreateBrokerConnectionRequest(
            broker_type="zerodha", label="x" * 41, credentials=_valid_creds()
        )


def test_create_schema_trims_whitespace():
    req = CreateBrokerConnectionRequest(
        broker_type="zerodha", label="  Main  ", credentials=_valid_creds()
    )
    assert req.label == "Main"


def test_update_schema_requires_label():
    with pytest.raises(ValidationError):
        UpdateBrokerConnectionRequest()  # type: ignore[call-arg]


def test_update_schema_rejects_blank_label():
    with pytest.raises(ValidationError):
        UpdateBrokerConnectionRequest(label="")


def test_update_schema_rejects_too_long_label():
    with pytest.raises(ValidationError):
        UpdateBrokerConnectionRequest(label="y" * 41)


def test_update_schema_trims_whitespace():
    req = UpdateBrokerConnectionRequest(label="  My Account  ")
    assert req.label == "My Account"


@pytest.mark.asyncio
async def test_delete_broker_cascades_deployments(client):
    """Deleting a broker should cascade-delete linked strategy_deployments."""
    tokens = await create_authenticated_user(client, email="cascade_dep@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    broker_resp = await client.post(
        "/api/v1/brokers",
        json={"broker_type": "exchange1", "label": "Cascade Dep", "credentials": {"api_key": "k", "private_key": "p"}},
        headers=headers,
    )
    broker_id = broker_resp.json()["id"]

    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    tenant_id = uuid_mod.UUID(me_resp.json()["id"])
    async with async_session_factory() as session:
        code = StrategyCode(id=uuid_mod.uuid4(), tenant_id=tenant_id, name="CascadeStrat", code="pass")
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
        dep_id = dep.id
        await session.commit()

    resp = await client.delete(f"/api/v1/brokers/{broker_id}", headers=headers)
    assert resp.status_code == 204

    async with async_session_factory() as session:
        result = await session.execute(
            select(StrategyDeployment).where(StrategyDeployment.id == dep_id)
        )
        assert result.scalar_one_or_none() is None, "deployment should be cascade-deleted"


@pytest.mark.asyncio
async def test_delete_broker_nulls_strategy_broker_connection(client):
    """Deleting a broker should SET NULL on Strategy.broker_connection_id."""
    tokens = await create_authenticated_user(client, email="setnull@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    broker_resp = await client.post(
        "/api/v1/brokers",
        json={"broker_type": "exchange1", "label": "SetNull", "credentials": {"api_key": "k", "private_key": "p"}},
        headers=headers,
    )
    broker_id = broker_resp.json()["id"]

    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    tenant_id = uuid_mod.UUID(me_resp.json()["id"])
    async with async_session_factory() as session:
        strat = Strategy(
            id=uuid_mod.uuid4(), tenant_id=tenant_id,
            name="NullTest", mode="live",
            broker_connection_id=uuid_mod.UUID(broker_id),
        )
        session.add(strat)
        strat_id = strat.id
        await session.commit()

    resp = await client.delete(f"/api/v1/brokers/{broker_id}", headers=headers)
    assert resp.status_code == 204

    async with async_session_factory() as session:
        result = await session.execute(select(Strategy).where(Strategy.id == strat_id))
        strat = result.scalar_one_or_none()
        assert strat is not None, "strategy should still exist"
        assert strat.broker_connection_id is None, "broker_connection_id should be NULL"


@pytest.mark.asyncio
async def test_delete_broker_cascades_manual_trades(client):
    """Deleting a broker should cascade-delete linked manual_trades."""
    from decimal import Decimal

    tokens = await create_authenticated_user(client, email="cascade_mt@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    broker_resp = await client.post(
        "/api/v1/brokers",
        json={"broker_type": "exchange1", "label": "Cascade MT", "credentials": {"api_key": "k", "private_key": "p"}},
        headers=headers,
    )
    broker_id = broker_resp.json()["id"]

    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    tenant_id = uuid_mod.UUID(me_resp.json()["id"])

    from app.db.models import ManualTrade
    async with async_session_factory() as session:
        trade = ManualTrade(
            id=uuid_mod.uuid4(),
            tenant_id=tenant_id,
            broker_connection_id=uuid_mod.UUID(broker_id),
            symbol="BTCUSDT",
            exchange="EXCHANGE1",
            product_type="FUTURES",
            action="BUY",
            quantity=1,
            order_type="MARKET",
            status="filled",
        )
        session.add(trade)
        trade_id = trade.id
        await session.commit()

    resp = await client.delete(f"/api/v1/brokers/{broker_id}", headers=headers)
    assert resp.status_code == 204

    async with async_session_factory() as session:
        result = await session.execute(
            select(ManualTrade).where(ManualTrade.id == trade_id)
        )
        assert result.scalar_one_or_none() is None, "manual trade should be cascade-deleted"
