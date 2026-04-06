# Broker Detail Page Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/brokers/[id]` page showing exchange-level positions, open orders, order history, and summary stats aggregated across all deployments using a given broker connection.

**Architecture:** Four new backend endpoints on the existing `/api/v1/brokers/{id}/` router aggregate data from `deployment_states` and `deployment_trades` tables. The frontend adds a detail page at `app/(dashboard)/brokers/[id]/page.tsx` with four new components, and the existing broker list page gets clickable cards linking to the detail page.

**Tech Stack:** FastAPI + SQLAlchemy async (backend), Next.js + Chakra UI v2 + SWR (frontend), pytest-asyncio + httpx (backend tests), Jest + React Testing Library (frontend tests).

---

## File Map

**Create:**
- `frontend/app/(dashboard)/brokers/[id]/page.tsx` — detail page
- `frontend/components/brokers/BrokerStatsBar.tsx`
- `frontend/components/brokers/BrokerPositionsTable.tsx`
- `frontend/components/brokers/BrokerOrdersTable.tsx`
- `frontend/components/brokers/BrokerTradesTable.tsx`
- `frontend/__tests__/components/BrokerStatsBar.test.tsx`
- `frontend/__tests__/components/BrokerPositionsTable.test.tsx`
- `frontend/__tests__/components/BrokerOrdersTable.test.tsx`
- `frontend/__tests__/components/BrokerTradesTable.test.tsx`
- `frontend/__tests__/pages/broker-detail.test.tsx`

**Modify:**
- `backend/app/brokers/schemas.py` — add 3 response schemas
- `backend/app/brokers/router.py` — add 4 endpoints
- `backend/tests/test_broker_connections.py` — add tests for new endpoints
- `frontend/lib/api/types.ts` — add BrokerStats, BrokerPosition, BrokerOrder
- `frontend/lib/hooks/useApi.ts` — add 4 hooks
- `frontend/app/(dashboard)/brokers/page.tsx` — wrap cards with Link

---

### Task 1: Backend schemas

**Files:**
- Modify: `backend/app/brokers/schemas.py`

- [ ] **Step 1: Add the three new Pydantic models**

Open `backend/app/brokers/schemas.py` and append:

```python
class BrokerStatsResponse(BaseModel):
    active_deployments: int
    total_realized_pnl: float
    win_rate: float
    total_trades: int


class BrokerPositionResponse(BaseModel):
    deployment_id: str
    deployment_name: str
    symbol: str
    side: str           # "LONG" or "SHORT"
    quantity: float
    avg_entry_price: float
    unrealized_pnl: float


class BrokerOrderResponse(BaseModel):
    order_id: str
    deployment_id: str
    deployment_name: str
    symbol: str
    action: str
    quantity: float
    order_type: str
    price: float | None
    created_at: str | None
```

- [ ] **Step 2: Verify import compiles**

```bash
cd backend && .venv/bin/python -c "from app.brokers.schemas import BrokerStatsResponse, BrokerPositionResponse, BrokerOrderResponse; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/brokers/schemas.py
git commit -m "feat: add broker detail response schemas"
```

---

### Task 2: Backend endpoints + tests

**Files:**
- Modify: `backend/app/brokers/router.py`
- Modify: `backend/tests/test_broker_connections.py`

#### Step 1: Write failing tests first

- [ ] **Step 1: Add tests to `backend/tests/test_broker_connections.py`**

Append to the file (after existing tests):

```python
import uuid as uuid_mod
from app.db.models import StrategyCode, StrategyCodeVersion, StrategyDeployment, DeploymentState, DeploymentTrade
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session_factory
from datetime import datetime, UTC


async def _create_broker_with_live_deployment(client, headers, has_position=True):
    """Helper: creates broker + strategy + live deployment + state. Returns (broker_id, deployment_id)."""
    broker_resp = await client.post(
        "/api/v1/brokers",
        json={"broker_type": "exchange1", "credentials": {"api_key": "k", "private_key": "p"}},
        headers=headers,
    )
    broker_id = broker_resp.json()["id"]

    async with async_session_factory() as session:
        # Create strategy code
        code = StrategyCode(
            id=uuid_mod.uuid4(),
            tenant_id=uuid_mod.UUID(headers["X-Tenant-Id"]) if "X-Tenant-Id" in headers else uuid_mod.uuid4(),
            name="Test Strategy",
        )
        session.add(code)
        await session.flush()

        version = StrategyCodeVersion(
            id=uuid_mod.uuid4(),
            strategy_code_id=code.id,
            version=1,
            code="def run(): pass",
            entrypoint="run",
        )
        session.add(version)
        await session.flush()

        dep = StrategyDeployment(
            id=uuid_mod.uuid4(),
            tenant_id=code.tenant_id,
            strategy_code_id=code.id,
            strategy_code_version_id=version.id,
            mode="live",
            status="running",
            symbol="BTCUSDT",
            exchange="EXCHANGE1",
            product_type="FUTURES",
            interval="1h",
            broker_connection_id=uuid_mod.UUID(broker_id),
        )
        session.add(dep)
        await session.flush()

        position = {"quantity": 0.05, "avg_entry_price": 83200.0, "unrealized_pnl": 124.5} if has_position else None
        state = DeploymentState(
            deployment_id=dep.id,
            tenant_id=code.tenant_id,
            position=position,
            open_orders=[{"id": "ord1", "action": "BUY", "quantity": 0.1, "order_type": "LIMIT", "price": 82000.0}],
            portfolio={},
            user_state={},
        )
        session.add(state)

        trade = DeploymentTrade(
            id=uuid_mod.uuid4(),
            tenant_id=code.tenant_id,
            deployment_id=dep.id,
            order_id="ord0",
            action="BUY",
            quantity=0.05,
            order_type="market",
            status="filled",
            fill_price=83000.0,
            fill_quantity=0.05,
            realized_pnl=100.0,
            created_at=datetime.now(UTC),
        )
        session.add(trade)
        await session.commit()

        return broker_id, str(dep.id)


@pytest.mark.asyncio
async def test_get_broker_stats_with_data(client):
    tokens = await create_authenticated_user(client, email="stats0@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Manually create broker + deployment + state + trade
    broker_resp = await client.post(
        "/api/v1/brokers",
        json={"broker_type": "exchange1", "credentials": {"api_key": "k", "private_key": "p"}},
        headers=headers,
    )
    broker_id = broker_resp.json()["id"]

    # Create the needed DB records directly
    async with async_session_factory() as session:
        me_resp = await client.get("/api/v1/auth/me", headers=headers)
        tenant_id = uuid_mod.UUID(me_resp.json()["id"])

        code = StrategyCode(id=uuid_mod.uuid4(), tenant_id=tenant_id, name="My Strat")
        session.add(code)
        await session.flush()
        version = StrategyCodeVersion(
            id=uuid_mod.uuid4(), strategy_code_id=code.id, version=1, code="pass", entrypoint="run"
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

        code = StrategyCode(id=uuid_mod.uuid4(), tenant_id=tenant_id, name="BTC Strat")
        session.add(code)
        await session.flush()
        version = StrategyCodeVersion(
            id=uuid_mod.uuid4(), strategy_code_id=code.id, version=1, code="pass", entrypoint="run"
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

        code = StrategyCode(id=uuid_mod.uuid4(), tenant_id=tenant_id, name="ETH Strat")
        session.add(code)
        await session.flush()
        version = StrategyCodeVersion(
            id=uuid_mod.uuid4(), strategy_code_id=code.id, version=1, code="pass", entrypoint="run"
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

        code = StrategyCode(id=uuid_mod.uuid4(), tenant_id=tenant_id, name="SOL Strat")
        session.add(code)
        await session.flush()
        version = StrategyCodeVersion(
            id=uuid_mod.uuid4(), strategy_code_id=code.id, version=1, code="pass", entrypoint="run"
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
    # Patch tenant_id into helper — use auth token's user_id
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_broker_connections.py::test_get_broker_stats_empty tests/test_broker_connections.py::test_get_broker_stats_404 -v
```

Expected: FAIL with `404 Not Found` (endpoints don't exist yet).

#### Step 3: Implement the four endpoints

- [ ] **Step 3: Update imports in `backend/app/brokers/router.py`**

Replace the top of the file imports section:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user, get_session, get_tenant_session
from app.brokers.schemas import (
    BrokerConnectionResponse,
    BrokerOrderResponse,
    BrokerPositionResponse,
    BrokerStatsResponse,
    CreateBrokerConnectionRequest,
)
from app.crypto.encryption import encrypt_credentials
from app.db.models import (
    BrokerConnection,
    DeploymentTrade,
    DeploymentState,
    ExchangeInstrument,
    StrategyDeployment,
)
from app.deployments.schemas import DeploymentTradeResponse, TradesResponse
from app.deployments.router import _trade_to_response
```

- [ ] **Step 4: Add the 4 new endpoints at the end of `backend/app/brokers/router.py`**

```python
def _get_broker_or_404(connection_id, tenant_id):
    """Returns a select() for the broker — call scalar_one_or_none() and raise 404 if None."""
    return (
        select(BrokerConnection)
        .where(
            BrokerConnection.id == connection_id,
            BrokerConnection.tenant_id == tenant_id,
        )
    )


@router.get("/{connection_id}/stats", response_model=BrokerStatsResponse)
async def get_broker_stats(
    connection_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    conn = await session.scalar(_get_broker_or_404(connection_id, tenant_id))
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broker connection not found")

    # Active deployments
    active = await session.scalar(
        select(func.count(StrategyDeployment.id)).where(
            StrategyDeployment.broker_connection_id == connection_id,
            StrategyDeployment.tenant_id == tenant_id,
            StrategyDeployment.mode == "live",
            StrategyDeployment.status == "running",
        )
    ) or 0

    # Deployment IDs for this broker
    dep_id_rows = await session.execute(
        select(StrategyDeployment.id).where(
            StrategyDeployment.broker_connection_id == connection_id,
            StrategyDeployment.tenant_id == tenant_id,
        )
    )
    dep_ids = [r[0] for r in dep_id_rows.all()]

    if not dep_ids:
        return BrokerStatsResponse(active_deployments=active, total_realized_pnl=0.0, win_rate=0.0, total_trades=0)

    # Trade stats — only filled trades
    trades_result = await session.execute(
        select(DeploymentTrade.realized_pnl).where(
            DeploymentTrade.deployment_id.in_(dep_ids),
            DeploymentTrade.status == "filled",
        )
    )
    pnl_values = [float(row[0]) for row in trades_result.all() if row[0] is not None]
    total_trades_result = await session.scalar(
        select(func.count(DeploymentTrade.id)).where(
            DeploymentTrade.deployment_id.in_(dep_ids),
            DeploymentTrade.status == "filled",
        )
    ) or 0

    total_pnl = sum(pnl_values)
    winning = sum(1 for p in pnl_values if p > 0)
    win_rate = (winning / len(pnl_values)) if pnl_values else 0.0

    return BrokerStatsResponse(
        active_deployments=active,
        total_realized_pnl=round(total_pnl, 4),
        win_rate=round(win_rate, 4),
        total_trades=total_trades_result,
    )


@router.get("/{connection_id}/positions", response_model=list[BrokerPositionResponse])
async def get_broker_positions(
    connection_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    conn = await session.scalar(_get_broker_or_404(connection_id, tenant_id))
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broker connection not found")

    deps_result = await session.execute(
        select(StrategyDeployment)
        .where(
            StrategyDeployment.broker_connection_id == connection_id,
            StrategyDeployment.tenant_id == tenant_id,
            StrategyDeployment.mode == "live",
            StrategyDeployment.status == "running",
        )
        .options(
            selectinload(StrategyDeployment.strategy_code),
            selectinload(StrategyDeployment.state),
        )
    )
    deps = deps_result.scalars().all()

    positions = []
    for dep in deps:
        if dep.state is None or dep.state.position is None:
            continue
        pos = dep.state.position
        qty = float(pos.get("quantity", 0))
        if qty == 0:
            continue
        positions.append(
            BrokerPositionResponse(
                deployment_id=str(dep.id),
                deployment_name=dep.strategy_code.name if dep.strategy_code else "",
                symbol=dep.symbol,
                side="LONG" if qty > 0 else "SHORT",
                quantity=abs(qty),
                avg_entry_price=float(pos.get("avg_entry_price", 0)),
                unrealized_pnl=float(pos.get("unrealized_pnl", 0)),
            )
        )
    return positions


@router.get("/{connection_id}/orders", response_model=list[BrokerOrderResponse])
async def get_broker_orders(
    connection_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    conn = await session.scalar(_get_broker_or_404(connection_id, tenant_id))
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broker connection not found")

    deps_result = await session.execute(
        select(StrategyDeployment)
        .where(
            StrategyDeployment.broker_connection_id == connection_id,
            StrategyDeployment.tenant_id == tenant_id,
            StrategyDeployment.mode == "live",
            StrategyDeployment.status == "running",
        )
        .options(
            selectinload(StrategyDeployment.strategy_code),
            selectinload(StrategyDeployment.state),
        )
    )
    deps = deps_result.scalars().all()

    orders = []
    for dep in deps:
        if dep.state is None:
            continue
        dep_name = dep.strategy_code.name if dep.strategy_code else ""
        for order in (dep.state.open_orders or []):
            orders.append(
                BrokerOrderResponse(
                    order_id=str(order.get("id", "")),
                    deployment_id=str(dep.id),
                    deployment_name=dep_name,
                    symbol=dep.symbol,
                    action=str(order.get("action", "")),
                    quantity=float(order.get("quantity", 0)),
                    order_type=str(order.get("order_type", "MARKET")),
                    price=float(order["price"]) if order.get("price") is not None else None,
                    created_at=order.get("created_at"),
                )
            )
    return orders


@router.get("/{connection_id}/trades", response_model=TradesResponse)
async def get_broker_trades(
    connection_id: uuid.UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    conn = await session.scalar(_get_broker_or_404(connection_id, tenant_id))
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broker connection not found")

    dep_id_rows = await session.execute(
        select(StrategyDeployment.id).where(
            StrategyDeployment.broker_connection_id == connection_id,
            StrategyDeployment.tenant_id == tenant_id,
        )
    )
    dep_ids = [r[0] for r in dep_id_rows.all()]

    if not dep_ids:
        return TradesResponse(trades=[], total=0, offset=offset, limit=limit)

    base_q = select(DeploymentTrade).where(DeploymentTrade.deployment_id.in_(dep_ids))
    total = await session.scalar(select(func.count()).select_from(base_q.subquery())) or 0

    trades_result = await session.execute(
        base_q
        .order_by(DeploymentTrade.created_at.desc())
        .offset(offset)
        .limit(limit)
        .options(
            selectinload(DeploymentTrade.deployment).selectinload(StrategyDeployment.strategy_code)
        )
    )
    trades = trades_result.scalars().all()

    return TradesResponse(
        trades=[
            _trade_to_response(
                t,
                t.deployment.strategy_code.name if t.deployment and t.deployment.strategy_code else "",
                t.deployment.symbol if t.deployment else "",
            )
            for t in trades
        ],
        total=total,
        offset=offset,
        limit=limit,
    )
```

- [ ] **Step 5: Run all broker tests**

```bash
cd backend && .venv/bin/pytest tests/test_broker_connections.py -v
```

Expected: All tests pass (including the 8 new ones).

- [ ] **Step 6: Commit**

```bash
git add backend/app/brokers/router.py backend/tests/test_broker_connections.py
git commit -m "feat: add broker detail API endpoints (stats, positions, orders, trades)"
```

---

### Task 3: Frontend types + hooks

**Files:**
- Modify: `frontend/lib/api/types.ts`
- Modify: `frontend/lib/hooks/useApi.ts`

- [ ] **Step 1: Add types to `frontend/lib/api/types.ts`**

Append before the final line of the file:

```ts
// Broker Detail
export interface BrokerStats {
  active_deployments: number;
  total_realized_pnl: number;
  win_rate: number;
  total_trades: number;
}

export interface BrokerPosition {
  deployment_id: string;
  deployment_name: string;
  symbol: string;
  side: "LONG" | "SHORT";
  quantity: number;
  avg_entry_price: number;
  unrealized_pnl: number;
}

export interface BrokerOrder {
  order_id: string;
  deployment_id: string;
  deployment_name: string;
  symbol: string;
  action: string;
  quantity: number;
  order_type: string;
  price: number | null;
  created_at: string | null;
}
```

- [ ] **Step 2: Add hooks to `frontend/lib/hooks/useApi.ts`**

At the top of the file, add `BrokerStats`, `BrokerPosition`, `BrokerOrder` to the existing type imports block:

```ts
import type {
  // ... existing imports ...
  BrokerStats,
  BrokerPosition,
  BrokerOrder,
} from "@/lib/api/types";
```

Then append at the bottom of the file:

```ts
export function useBrokerStats(id: string | undefined) {
  return useApiGet<BrokerStats>(
    id ? `/api/v1/brokers/${id}/stats` : null,
    { refreshInterval: 30000 }
  );
}

export function useBrokerPositions(id: string | undefined) {
  return useApiGet<BrokerPosition[]>(
    id ? `/api/v1/brokers/${id}/positions` : null,
    { refreshInterval: 5000 }
  );
}

export function useBrokerOrders(id: string | undefined) {
  return useApiGet<BrokerOrder[]>(
    id ? `/api/v1/brokers/${id}/orders` : null,
    { refreshInterval: 5000 }
  );
}

export function useBrokerTrades(id: string | undefined, offset = 0, limit = 50) {
  return useApiGet<TradesResponse>(
    id ? `/api/v1/brokers/${id}/trades?offset=${offset}&limit=${limit}` : null
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/api/types.ts frontend/lib/hooks/useApi.ts
git commit -m "feat: add broker detail types and SWR hooks"
```

---

### Task 4: Clickable broker cards

**Files:**
- Modify: `frontend/app/(dashboard)/brokers/page.tsx`
- Modify: `frontend/__tests__/pages/brokers.test.tsx`

- [ ] **Step 1: Write failing test**

Add to `frontend/__tests__/pages/brokers.test.tsx`:

```tsx
it("broker card links to detail page", () => {
  (useApiModule.useBrokers as jest.Mock).mockReturnValue({
    data: [{ id: "broker-123", broker_type: "exchange1", is_active: true, connected_at: "2026-01-01" }],
    isLoading: false, mutate: jest.fn(),
  });
  render(<ChakraProvider><BrokersPage /></ChakraProvider>);
  const link = screen.getByRole("link", { name: /exchange1/i });
  expect(link).toHaveAttribute("href", "/brokers/broker-123");
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm test -- --testPathPattern=brokers --no-coverage 2>&1 | tail -20
```

Expected: FAIL — no link element found.

- [ ] **Step 3: Wrap broker cards in `frontend/app/(dashboard)/brokers/page.tsx`**

Add `Link` import at the top:

```tsx
import Link from "next/link";
```

Then wrap each `<Card>` with a Link — replace:

```tsx
<Card key={broker.id}>
```

with:

```tsx
<Link key={broker.id} href={`/brokers/${broker.id}`} style={{ textDecoration: "none" }}>
<Card _hover={{ borderColor: "blue.400", cursor: "pointer" }} transition="border-color 0.15s">
```

and close with `</Card></Link>` (remove `key` from Card since it moves to Link).

- [ ] **Step 4: Run tests**

```bash
cd frontend && npm test -- --testPathPattern=brokers --no-coverage 2>&1 | tail -20
```

Expected: All 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/(dashboard)/brokers/page.tsx frontend/__tests__/pages/brokers.test.tsx
git commit -m "feat: make broker cards link to detail page"
```

---

### Task 5: BrokerStatsBar component

**Files:**
- Create: `frontend/components/brokers/BrokerStatsBar.tsx`
- Create: `frontend/__tests__/components/BrokerStatsBar.test.tsx`

- [ ] **Step 1: Write failing test**

Create `frontend/__tests__/components/BrokerStatsBar.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { BrokerStatsBar } from "@/components/brokers/BrokerStatsBar";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");

describe("BrokerStatsBar", () => {
  it("renders all 4 stat labels", () => {
    (useApiModule.useBrokerStats as jest.Mock).mockReturnValue({
      data: { active_deployments: 3, total_realized_pnl: 2340.5, win_rate: 0.64, total_trades: 142 },
      isLoading: false,
    });
    render(<ChakraProvider><BrokerStatsBar brokerId="b1" /></ChakraProvider>);
    expect(screen.getByText(/active deployments/i)).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText(/total.*p.*l/i)).toBeInTheDocument();
    expect(screen.getByText(/win rate/i)).toBeInTheDocument();
    expect(screen.getByText(/total trades/i)).toBeInTheDocument();
    expect(screen.getByText("142")).toBeInTheDocument();
  });

  it("renders loading skeleton when data is undefined", () => {
    (useApiModule.useBrokerStats as jest.Mock).mockReturnValue({ data: undefined, isLoading: true });
    render(<ChakraProvider><BrokerStatsBar brokerId="b1" /></ChakraProvider>);
    // Should not crash — skeletons rendered
    expect(screen.queryByText("Active Deployments")).not.toBeInTheDocument();
  });

  it("formats positive P&L in green", () => {
    (useApiModule.useBrokerStats as jest.Mock).mockReturnValue({
      data: { active_deployments: 1, total_realized_pnl: 500.0, win_rate: 0.5, total_trades: 10 },
      isLoading: false,
    });
    render(<ChakraProvider><BrokerStatsBar brokerId="b1" /></ChakraProvider>);
    expect(screen.getByText(/\+\$500/)).toBeInTheDocument();
  });

  it("formats negative P&L", () => {
    (useApiModule.useBrokerStats as jest.Mock).mockReturnValue({
      data: { active_deployments: 0, total_realized_pnl: -200.0, win_rate: 0.3, total_trades: 5 },
      isLoading: false,
    });
    render(<ChakraProvider><BrokerStatsBar brokerId="b1" /></ChakraProvider>);
    expect(screen.getByText(/-\$200/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm test -- --testPathPattern=BrokerStatsBar --no-coverage 2>&1 | tail -10
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `frontend/components/brokers/BrokerStatsBar.tsx`**

```tsx
"use client";
import { SimpleGrid, Stat, StatLabel, StatNumber, Skeleton, useColorModeValue } from "@chakra-ui/react";
import { useBrokerStats } from "@/lib/hooks/useApi";

interface Props {
  brokerId: string;
}

function formatPnl(pnl: number): string {
  const sign = pnl >= 0 ? "+" : "-";
  return `${sign}$${Math.abs(pnl).toFixed(2)}`;
}

export function BrokerStatsBar({ brokerId }: Props) {
  const { data: stats, isLoading } = useBrokerStats(brokerId);
  const cardBg = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");
  const pnlColor = stats && stats.total_realized_pnl >= 0 ? "green.400" : "red.400";

  if (isLoading || !stats) {
    return (
      <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4} mb={6}>
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} height="80px" borderRadius="md" />
        ))}
      </SimpleGrid>
    );
  }

  return (
    <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4} mb={6}>
      <Stat bg={cardBg} borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
        <StatLabel>Active Deployments</StatLabel>
        <StatNumber>{stats.active_deployments}</StatNumber>
      </Stat>
      <Stat bg={cardBg} borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
        <StatLabel>Total Realized P&L</StatLabel>
        <StatNumber color={pnlColor}>{formatPnl(stats.total_realized_pnl)}</StatNumber>
      </Stat>
      <Stat bg={cardBg} borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
        <StatLabel>Win Rate</StatLabel>
        <StatNumber>{(stats.win_rate * 100).toFixed(1)}%</StatNumber>
      </Stat>
      <Stat bg={cardBg} borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
        <StatLabel>Total Trades</StatLabel>
        <StatNumber>{stats.total_trades}</StatNumber>
      </Stat>
    </SimpleGrid>
  );
}
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npm test -- --testPathPattern=BrokerStatsBar --no-coverage 2>&1 | tail -10
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/brokers/BrokerStatsBar.tsx frontend/__tests__/components/BrokerStatsBar.test.tsx
git commit -m "feat: add BrokerStatsBar component"
```

---

### Task 6: BrokerPositionsTable component

**Files:**
- Create: `frontend/components/brokers/BrokerPositionsTable.tsx`
- Create: `frontend/__tests__/components/BrokerPositionsTable.test.tsx`

- [ ] **Step 1: Write failing test**

Create `frontend/__tests__/components/BrokerPositionsTable.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { BrokerPositionsTable } from "@/components/brokers/BrokerPositionsTable";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");
jest.mock("@/lib/api/client", () => ({ apiClient: jest.fn() }));

const mockPosition = {
  deployment_id: "dep-1",
  deployment_name: "BTC Strategy",
  symbol: "BTCUSDT",
  side: "LONG" as const,
  quantity: 0.05,
  avg_entry_price: 83200,
  unrealized_pnl: 124.5,
};

describe("BrokerPositionsTable", () => {
  it("renders position row", () => {
    (useApiModule.useBrokerPositions as jest.Mock).mockReturnValue({
      data: [mockPosition], isLoading: false,
    });
    render(<ChakraProvider><BrokerPositionsTable brokerId="b1" /></ChakraProvider>);
    expect(screen.getByText("BTCUSDT")).toBeInTheDocument();
    expect(screen.getByText("LONG")).toBeInTheDocument();
    expect(screen.getByText("BTC Strategy")).toBeInTheDocument();
    expect(screen.getByText(/\+\$124/)).toBeInTheDocument();
  });

  it("renders empty state when no positions", () => {
    (useApiModule.useBrokerPositions as jest.Mock).mockReturnValue({ data: [], isLoading: false });
    render(<ChakraProvider><BrokerPositionsTable brokerId="b1" /></ChakraProvider>);
    expect(screen.getByText(/no open positions/i)).toBeInTheDocument();
  });

  it("renders Close button per row", () => {
    (useApiModule.useBrokerPositions as jest.Mock).mockReturnValue({
      data: [mockPosition], isLoading: false,
    });
    render(<ChakraProvider><BrokerPositionsTable brokerId="b1" /></ChakraProvider>);
    expect(screen.getByRole("button", { name: /close/i })).toBeInTheDocument();
  });

  it("renders SHORT side in red", () => {
    (useApiModule.useBrokerPositions as jest.Mock).mockReturnValue({
      data: [{ ...mockPosition, side: "SHORT" as const, unrealized_pnl: -18 }],
      isLoading: false,
    });
    render(<ChakraProvider><BrokerPositionsTable brokerId="b1" /></ChakraProvider>);
    expect(screen.getByText("SHORT")).toBeInTheDocument();
    expect(screen.getByText(/-\$18/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm test -- --testPathPattern=BrokerPositionsTable --no-coverage 2>&1 | tail -10
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `frontend/components/brokers/BrokerPositionsTable.tsx`**

```tsx
"use client";
import { useState } from "react";
import {
  Box, Table, Thead, Tbody, Tr, Th, Td, Badge, Button, Text, useToast,
  useColorModeValue,
} from "@chakra-ui/react";
import { useBrokerPositions } from "@/lib/hooks/useApi";
import { apiClient } from "@/lib/api/client";
import { mutate } from "swr";

interface Props {
  brokerId: string;
}

function formatPnl(pnl: number): string {
  const sign = pnl >= 0 ? "+" : "-";
  return `${sign}$${Math.abs(pnl).toFixed(2)}`;
}

export function BrokerPositionsTable({ brokerId }: Props) {
  const { data: positions, isLoading } = useBrokerPositions(brokerId);
  const [closingId, setClosingId] = useState<string | null>(null);
  const toast = useToast();
  const borderColor = useColorModeValue("gray.200", "gray.700");

  async function handleClose(deploymentId: string, side: "LONG" | "SHORT", quantity: number) {
    setClosingId(deploymentId);
    try {
      await apiClient(`/api/v1/deployments/${deploymentId}/manual-order`, {
        method: "POST",
        body: JSON.stringify({
          action: side === "LONG" ? "SELL" : "BUY",
          quantity,
          order_type: "market",
        }),
      });
      toast({ title: "Close order placed", status: "success", duration: 3000 });
      mutate(`/api/v1/brokers/${brokerId}/positions`);
    } catch {
      toast({ title: "Failed to place close order", status: "error", duration: 3000 });
    } finally {
      setClosingId(null);
    }
  }

  if (isLoading) return <Box py={4}><Text color="gray.500">Loading...</Text></Box>;
  if (!positions || positions.length === 0) {
    return <Box py={8} textAlign="center"><Text color="gray.500">No open positions</Text></Box>;
  }

  return (
    <Box overflowX="auto">
      <Table size="sm" variant="simple">
        <Thead>
          <Tr>
            <Th>Symbol</Th>
            <Th>Side</Th>
            <Th isNumeric>Qty</Th>
            <Th isNumeric>Avg Entry</Th>
            <Th isNumeric>Unrealized P&L</Th>
            <Th>Strategy</Th>
            <Th />
          </Tr>
        </Thead>
        <Tbody>
          {positions.map((pos) => (
            <Tr key={pos.deployment_id} borderBottomWidth={1} borderColor={borderColor}>
              <Td fontWeight="semibold">{pos.symbol}</Td>
              <Td>
                <Badge colorScheme={pos.side === "LONG" ? "green" : "red"}>{pos.side}</Badge>
              </Td>
              <Td isNumeric>{pos.quantity}</Td>
              <Td isNumeric>${pos.avg_entry_price.toLocaleString()}</Td>
              <Td isNumeric color={pos.unrealized_pnl >= 0 ? "green.400" : "red.400"}>
                {formatPnl(pos.unrealized_pnl)}
              </Td>
              <Td color="gray.500" fontSize="sm">{pos.deployment_name}</Td>
              <Td>
                <Button
                  size="xs"
                  colorScheme="red"
                  variant="ghost"
                  isLoading={closingId === pos.deployment_id}
                  onClick={() => handleClose(pos.deployment_id, pos.side, pos.quantity)}
                >
                  Close
                </Button>
              </Td>
            </Tr>
          ))}
        </Tbody>
      </Table>
    </Box>
  );
}
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npm test -- --testPathPattern=BrokerPositionsTable --no-coverage 2>&1 | tail -10
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/brokers/BrokerPositionsTable.tsx frontend/__tests__/components/BrokerPositionsTable.test.tsx
git commit -m "feat: add BrokerPositionsTable component"
```

---

### Task 7: BrokerOrdersTable component

**Files:**
- Create: `frontend/components/brokers/BrokerOrdersTable.tsx`
- Create: `frontend/__tests__/components/BrokerOrdersTable.test.tsx`

- [ ] **Step 1: Write failing test**

Create `frontend/__tests__/components/BrokerOrdersTable.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { BrokerOrdersTable } from "@/components/brokers/BrokerOrdersTable";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");

const mockOrder = {
  order_id: "ord-1",
  deployment_id: "dep-1",
  deployment_name: "BTC Strategy",
  symbol: "BTCUSDT",
  action: "BUY",
  quantity: 0.1,
  order_type: "LIMIT",
  price: 82000,
  created_at: "2026-04-06T10:00:00Z",
};

describe("BrokerOrdersTable", () => {
  it("renders order row", () => {
    (useApiModule.useBrokerOrders as jest.Mock).mockReturnValue({ data: [mockOrder], isLoading: false });
    render(<ChakraProvider><BrokerOrdersTable brokerId="b1" /></ChakraProvider>);
    expect(screen.getByText("BTCUSDT")).toBeInTheDocument();
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.getByText("LIMIT")).toBeInTheDocument();
    expect(screen.getByText("BTC Strategy")).toBeInTheDocument();
  });

  it("renders empty state when no orders", () => {
    (useApiModule.useBrokerOrders as jest.Mock).mockReturnValue({ data: [], isLoading: false });
    render(<ChakraProvider><BrokerOrdersTable brokerId="b1" /></ChakraProvider>);
    expect(screen.getByText(/no open orders/i)).toBeInTheDocument();
  });

  it("shows MKT for market orders with no price", () => {
    (useApiModule.useBrokerOrders as jest.Mock).mockReturnValue({
      data: [{ ...mockOrder, order_type: "MARKET", price: null }],
      isLoading: false,
    });
    render(<ChakraProvider><BrokerOrdersTable brokerId="b1" /></ChakraProvider>);
    expect(screen.getByText("MKT")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm test -- --testPathPattern=BrokerOrdersTable --no-coverage 2>&1 | tail -10
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `frontend/components/brokers/BrokerOrdersTable.tsx`**

```tsx
"use client";
import { Box, Table, Thead, Tbody, Tr, Th, Td, Badge, Text } from "@chakra-ui/react";
import { useBrokerOrders } from "@/lib/hooks/useApi";
import { formatDate } from "@/lib/utils/formatters";

interface Props {
  brokerId: string;
}

export function BrokerOrdersTable({ brokerId }: Props) {
  const { data: orders, isLoading } = useBrokerOrders(brokerId);

  if (isLoading) return <Box py={4}><Text color="gray.500">Loading...</Text></Box>;
  if (!orders || orders.length === 0) {
    return <Box py={8} textAlign="center"><Text color="gray.500">No open orders</Text></Box>;
  }

  return (
    <Box overflowX="auto">
      <Table size="sm" variant="simple">
        <Thead>
          <Tr>
            <Th>Time</Th>
            <Th>Symbol</Th>
            <Th>Action</Th>
            <Th isNumeric>Qty</Th>
            <Th>Type</Th>
            <Th isNumeric>Price</Th>
            <Th>Strategy</Th>
          </Tr>
        </Thead>
        <Tbody>
          {orders.map((order) => (
            <Tr key={order.order_id}>
              <Td fontSize="xs" color="gray.500">{order.created_at ? formatDate(order.created_at) : "—"}</Td>
              <Td fontWeight="semibold">{order.symbol}</Td>
              <Td>
                <Badge colorScheme={order.action === "BUY" ? "green" : "red"}>{order.action}</Badge>
              </Td>
              <Td isNumeric>{order.quantity}</Td>
              <Td>{order.order_type}</Td>
              <Td isNumeric>{order.price != null ? `$${order.price.toLocaleString()}` : "MKT"}</Td>
              <Td color="gray.500" fontSize="sm">{order.deployment_name}</Td>
            </Tr>
          ))}
        </Tbody>
      </Table>
    </Box>
  );
}
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npm test -- --testPathPattern=BrokerOrdersTable --no-coverage 2>&1 | tail -10
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/brokers/BrokerOrdersTable.tsx frontend/__tests__/components/BrokerOrdersTable.test.tsx
git commit -m "feat: add BrokerOrdersTable component"
```

---

### Task 8: BrokerTradesTable component

**Files:**
- Create: `frontend/components/brokers/BrokerTradesTable.tsx`
- Create: `frontend/__tests__/components/BrokerTradesTable.test.tsx`

- [ ] **Step 1: Write failing test**

Create `frontend/__tests__/components/BrokerTradesTable.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { BrokerTradesTable } from "@/components/brokers/BrokerTradesTable";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");

const mockTrade = {
  id: "t1", deployment_id: "dep-1", order_id: "o1", broker_order_id: null,
  action: "BUY", quantity: 0.05, order_type: "market", price: null,
  trigger_price: null, fill_price: 83000, fill_quantity: 0.05,
  status: "filled", is_manual: false, realized_pnl: 100,
  created_at: "2026-04-06T09:00:00Z", filled_at: "2026-04-06T09:00:01Z",
  strategy_name: "BTC Strategy", symbol: "BTCUSDT",
};

describe("BrokerTradesTable", () => {
  it("renders trade row", () => {
    (useApiModule.useBrokerTrades as jest.Mock).mockReturnValue({
      data: { trades: [mockTrade], total: 1, offset: 0, limit: 50 },
      isLoading: false,
    });
    render(<ChakraProvider><BrokerTradesTable brokerId="b1" /></ChakraProvider>);
    expect(screen.getByText("BTCUSDT")).toBeInTheDocument();
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.getByText("BTC Strategy")).toBeInTheDocument();
    expect(screen.getByText(/\+\$100/)).toBeInTheDocument();
  });

  it("renders empty state when no trades", () => {
    (useApiModule.useBrokerTrades as jest.Mock).mockReturnValue({
      data: { trades: [], total: 0, offset: 0, limit: 50 }, isLoading: false,
    });
    render(<ChakraProvider><BrokerTradesTable brokerId="b1" /></ChakraProvider>);
    expect(screen.getByText(/no trades/i)).toBeInTheDocument();
  });

  it("shows — for null P&L", () => {
    (useApiModule.useBrokerTrades as jest.Mock).mockReturnValue({
      data: { trades: [{ ...mockTrade, realized_pnl: null }], total: 1, offset: 0, limit: 50 },
      isLoading: false,
    });
    render(<ChakraProvider><BrokerTradesTable brokerId="b1" /></ChakraProvider>);
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("renders pagination controls when total > limit", () => {
    (useApiModule.useBrokerTrades as jest.Mock).mockReturnValue({
      data: { trades: [mockTrade], total: 100, offset: 0, limit: 50 },
      isLoading: false,
    });
    render(<ChakraProvider><BrokerTradesTable brokerId="b1" /></ChakraProvider>);
    expect(screen.getByRole("button", { name: /next/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm test -- --testPathPattern=BrokerTradesTable --no-coverage 2>&1 | tail -10
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `frontend/components/brokers/BrokerTradesTable.tsx`**

```tsx
"use client";
import { useState } from "react";
import {
  Box, Table, Thead, Tbody, Tr, Th, Td, Badge, Text, HStack, Button, Flex,
} from "@chakra-ui/react";
import { useBrokerTrades } from "@/lib/hooks/useApi";
import { formatDate } from "@/lib/utils/formatters";

interface Props {
  brokerId: string;
}

const PAGE_SIZE = 50;

function formatPnl(pnl: number | null): string {
  if (pnl === null) return "—";
  const sign = pnl >= 0 ? "+" : "-";
  return `${sign}$${Math.abs(pnl).toFixed(2)}`;
}

export function BrokerTradesTable({ brokerId }: Props) {
  const [offset, setOffset] = useState(0);
  const { data, isLoading } = useBrokerTrades(brokerId, offset, PAGE_SIZE);

  if (isLoading) return <Box py={4}><Text color="gray.500">Loading...</Text></Box>;
  if (!data || data.trades.length === 0) {
    return <Box py={8} textAlign="center"><Text color="gray.500">No trades recorded</Text></Box>;
  }

  const { trades, total } = data;
  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;

  return (
    <Box>
      <Box overflowX="auto">
        <Table size="sm" variant="simple">
          <Thead>
            <Tr>
              <Th>Time</Th>
              <Th>Symbol</Th>
              <Th>Action</Th>
              <Th isNumeric>Qty</Th>
              <Th isNumeric>Fill Price</Th>
              <Th isNumeric>P&L</Th>
              <Th>Strategy</Th>
              <Th>Status</Th>
            </Tr>
          </Thead>
          <Tbody>
            {trades.map((t) => (
              <Tr key={t.id}>
                <Td fontSize="xs" color="gray.500">{formatDate(t.created_at)}</Td>
                <Td fontWeight="semibold">{t.symbol}</Td>
                <Td>
                  <Badge colorScheme={t.action === "BUY" ? "green" : "red"}>{t.action}</Badge>
                </Td>
                <Td isNumeric>{t.quantity}</Td>
                <Td isNumeric>{t.fill_price != null ? `$${t.fill_price.toLocaleString()}` : "—"}</Td>
                <Td isNumeric color={t.realized_pnl == null ? undefined : t.realized_pnl >= 0 ? "green.400" : "red.400"}>
                  {formatPnl(t.realized_pnl)}
                </Td>
                <Td color="gray.500" fontSize="sm">{t.strategy_name}</Td>
                <Td><Badge variant="subtle">{t.status}</Badge></Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </Box>

      {total > PAGE_SIZE && (
        <Flex justify="space-between" align="center" mt={3} px={1}>
          <Text fontSize="sm" color="gray.500">
            {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
          </Text>
          <HStack>
            <Button size="xs" onClick={() => setOffset(offset - PAGE_SIZE)} isDisabled={!canPrev}>
              Prev
            </Button>
            <Button size="xs" onClick={() => setOffset(offset + PAGE_SIZE)} isDisabled={!canNext}>
              Next
            </Button>
          </HStack>
        </Flex>
      )}
    </Box>
  );
}
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npm test -- --testPathPattern=BrokerTradesTable --no-coverage 2>&1 | tail -10
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/brokers/BrokerTradesTable.tsx frontend/__tests__/components/BrokerTradesTable.test.tsx
git commit -m "feat: add BrokerTradesTable component"
```

---

### Task 9: Broker detail page

**Files:**
- Create: `frontend/app/(dashboard)/brokers/[id]/page.tsx`
- Create: `frontend/__tests__/pages/broker-detail.test.tsx`

- [ ] **Step 1: Write failing test**

Create `frontend/__tests__/pages/broker-detail.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import BrokerDetailPage from "@/app/(dashboard)/brokers/[id]/page";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
  useParams: () => ({ id: "broker-abc" }),
}));
jest.mock("@/components/brokers/BrokerStatsBar", () => ({
  BrokerStatsBar: () => <div data-testid="stats-bar" />,
}));
jest.mock("@/components/brokers/BrokerPositionsTable", () => ({
  BrokerPositionsTable: () => <div data-testid="positions-table" />,
}));
jest.mock("@/components/brokers/BrokerOrdersTable", () => ({
  BrokerOrdersTable: () => <div data-testid="orders-table" />,
}));
jest.mock("@/components/brokers/BrokerTradesTable", () => ({
  BrokerTradesTable: () => <div data-testid="trades-table" />,
}));

describe("BrokerDetailPage", () => {
  beforeEach(() => {
    (useApiModule.useBrokers as jest.Mock).mockReturnValue({
      data: [{ id: "broker-abc", broker_type: "exchange1", is_active: true, connected_at: "2026-01-01" }],
      isLoading: false,
    });
    (useApiModule.useBrokerPositions as jest.Mock).mockReturnValue({ data: [], isLoading: false });
    (useApiModule.useBrokerOrders as jest.Mock).mockReturnValue({ data: [], isLoading: false });
  });

  it("renders broker name in heading", () => {
    render(<ChakraProvider><BrokerDetailPage /></ChakraProvider>);
    expect(screen.getByText(/exchange1/i)).toBeInTheDocument();
  });

  it("renders stats bar", () => {
    render(<ChakraProvider><BrokerDetailPage /></ChakraProvider>);
    expect(screen.getByTestId("stats-bar")).toBeInTheDocument();
  });

  it("renders tab labels", () => {
    render(<ChakraProvider><BrokerDetailPage /></ChakraProvider>);
    expect(screen.getByRole("tab", { name: /positions/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /open orders/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /order history/i })).toBeInTheDocument();
  });

  it("renders back link to /brokers", () => {
    render(<ChakraProvider><BrokerDetailPage /></ChakraProvider>);
    expect(screen.getByRole("link", { name: /brokers/i })).toHaveAttribute("href", "/brokers");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm test -- --testPathPattern=broker-detail --no-coverage 2>&1 | tail -10
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `frontend/app/(dashboard)/brokers/[id]/page.tsx`**

```tsx
"use client";
import {
  Box, Flex, Heading, Text, Tab, TabList, TabPanel, TabPanels, Tabs, Badge,
} from "@chakra-ui/react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useBrokers, useBrokerPositions, useBrokerOrders } from "@/lib/hooks/useApi";
import { BrokerStatsBar } from "@/components/brokers/BrokerStatsBar";
import { BrokerPositionsTable } from "@/components/brokers/BrokerPositionsTable";
import { BrokerOrdersTable } from "@/components/brokers/BrokerOrdersTable";
import { BrokerTradesTable } from "@/components/brokers/BrokerTradesTable";

export default function BrokerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: brokers } = useBrokers();
  const { data: positions } = useBrokerPositions(id);
  const { data: orders } = useBrokerOrders(id);

  const broker = brokers?.find((b) => b.id === id);
  const positionCount = positions?.length ?? 0;
  const orderCount = orders?.length ?? 0;

  return (
    <Box>
      <Flex align="center" gap={2} mb={1}>
        <Link href="/brokers">
          <Text fontSize="sm" color="blue.400">← Brokers</Text>
        </Link>
      </Flex>

      <Flex align="center" gap={3} mb={6}>
        <Heading size="lg">{broker?.broker_type ?? id}</Heading>
        {broker && (
          <Badge colorScheme={broker.is_active ? "green" : "gray"}>
            {broker.is_active ? "Connected" : "Inactive"}
          </Badge>
        )}
      </Flex>

      <BrokerStatsBar brokerId={id} />

      <Tabs colorScheme="blue" isLazy>
        <TabList>
          <Tab>
            Positions{positionCount > 0 && (
              <Badge ml={2} colorScheme="blue" variant="subtle">{positionCount}</Badge>
            )}
          </Tab>
          <Tab>
            Open Orders{orderCount > 0 && (
              <Badge ml={2} colorScheme="blue" variant="subtle">{orderCount}</Badge>
            )}
          </Tab>
          <Tab>Order History</Tab>
        </TabList>
        <TabPanels>
          <TabPanel px={0}>
            <BrokerPositionsTable brokerId={id} />
          </TabPanel>
          <TabPanel px={0}>
            <BrokerOrdersTable brokerId={id} />
          </TabPanel>
          <TabPanel px={0}>
            <BrokerTradesTable brokerId={id} />
          </TabPanel>
        </TabPanels>
      </Tabs>
    </Box>
  );
}
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npm test -- --testPathPattern=broker-detail --no-coverage 2>&1 | tail -10
```

Expected: 4 tests pass.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
cd frontend && npm test --no-coverage 2>&1 | tail -20
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/(dashboard)/brokers/[id]/page.tsx frontend/__tests__/pages/broker-detail.test.tsx
git commit -m "feat: add broker detail page wiring all components"
```

---

## Done

All backend endpoints tested, all frontend components tested, broker cards clickable. The feature is ready to deploy via `/deploy frontend` (backend also needs deploying for the new API endpoints).
