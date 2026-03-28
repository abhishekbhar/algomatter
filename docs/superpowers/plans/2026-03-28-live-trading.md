# Live Trading Section Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Live Trading command center and deployment detail page with trade tracking, manual order controls, live metrics, and backtest comparison.

**Architecture:** New `DeploymentTrade` table records every order dispatched. `order_router.dispatch_orders()` writes trade rows on each dispatch. New endpoints expose trades, positions, metrics, and comparison data. Frontend uses SWR polling to show a cross-deployment command center and per-deployment detail view.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Pydantic v2, Next.js 14 App Router, Chakra UI v2, SWR

**Spec:** `docs/superpowers/specs/2026-03-28-live-trading-design.md`

---

## File Structure

### Backend — Create
| File | Responsibility |
|------|---------------|
| `backend/app/db/migrations/versions/XXXX_add_deployment_trade.py` | Alembic migration for DeploymentTrade table + RLS |
| `backend/app/deployments/trade_service.py` | Trade business logic: PnL calculation, live metrics, comparison, aggregate stats |
| `backend/tests/test_live_trading.py` | Tests for all new endpoints and trade service |

### Backend — Modify
| File | Changes |
|------|---------|
| `backend/app/db/models.py` | Add `DeploymentTrade` model, add `trades` relationship on `StrategyDeployment` |
| `backend/app/deployments/schemas.py` | Add 8 new Pydantic schemas, add `strategy_name` to `DeploymentResponse` |
| `backend/app/deployments/router.py` | Add 8 new endpoints, modify `stop_all_deployments`, modify `_deployment_to_response` |
| `backend/app/strategy_runner/order_router.py` | Write `DeploymentTrade` rows in `dispatch_orders()` |

### Frontend — Create
| File | Responsibility |
|------|---------------|
| `frontend/components/live-trading/AggregateStats.tsx` | 4 stat cards for command center header |
| `frontend/components/live-trading/LiveDeploymentCard.tsx` | Deployment card for command center grid |
| `frontend/components/live-trading/KillSwitchButton.tsx` | Red stop-all button with confirm modal |
| `frontend/components/live-trading/PositionCard.tsx` | Current position + close button |
| `frontend/components/live-trading/PendingOrdersList.tsx` | Open orders with cancel buttons |
| `frontend/components/live-trading/TradeHistoryTable.tsx` | Paginated trade table |
| `frontend/components/live-trading/ManualOrderModal.tsx` | Place manual order form |
| `frontend/components/live-trading/MetricsGrid.tsx` | 2×4 metric stat cards |
| `frontend/components/live-trading/ComparisonTable.tsx` | Backtest vs live side-by-side |
| `frontend/app/(dashboard)/live-trading/page.tsx` | Command center page |
| `frontend/app/(dashboard)/live-trading/[deploymentId]/page.tsx` | Deployment detail page |

### Frontend — Modify
| File | Changes |
|------|---------|
| `frontend/lib/api/types.ts` | Add 6 new interfaces, add `strategy_name` to `Deployment` |
| `frontend/lib/hooks/useApi.ts` | Add 6 new hooks |
| `frontend/components/layout/Sidebar.tsx` | Add "Live Trading" nav item |

---

## Task 1: DeploymentTrade DB Model

**Files:**
- Modify: `backend/app/db/models.py`
- Test: `backend/tests/test_live_trading.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_live_trading.py`:

```python
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
)


@pytest.mark.asyncio
async def test_deployment_trade_model_create(db_session):
    """DeploymentTrade can be created and queried."""
    tenant_id = uuid.uuid4()

    # Create prerequisite strategy + deployment
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest backend/tests/test_live_trading.py::test_deployment_trade_model_create -v`
Expected: FAIL — `ImportError: cannot import name 'DeploymentTrade' from 'app.db.models'`

- [ ] **Step 3: Add DeploymentTrade model to models.py**

Add after the `DeploymentLog` class (after line 376 in `backend/app/db/models.py`):

```python
class DeploymentTrade(Base):
    __tablename__ = "deployment_trades"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("strategy_deployments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[str] = mapped_column(String(32), nullable=False)
    broker_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric, nullable=False)
    order_type: Mapped[str] = mapped_column(String(10), nullable=False)
    price: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    trigger_price: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    fill_price: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    fill_quantity: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="submitted")
    is_manual: Mapped[bool] = mapped_column(default=False)
    realized_pnl: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    filled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    deployment: Mapped["StrategyDeployment"] = relationship(back_populates="trades")
```

Also add the `trades` relationship on `StrategyDeployment` (after `state` relationship, around line 336):

```python
    trades: Mapped[list["DeploymentTrade"]] = relationship(
        back_populates="deployment", passive_deletes=True
    )
```

Add `Numeric` to the imports from sqlalchemy if not already present.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest backend/tests/test_live_trading.py::test_deployment_trade_model_create -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/models.py backend/tests/test_live_trading.py
git commit -m "feat: add DeploymentTrade model for structured trade records"
```

---

## Task 2: Alembic Migration

**Files:**
- Create: `backend/app/db/migrations/versions/XXXX_add_deployment_trade.py`

- [ ] **Step 1: Generate migration**

Run: `cd backend && .venv/bin/python -m alembic revision --autogenerate -m "add_deployment_trade"`

This will create a migration file. Verify it contains:
- `op.create_table("deployment_trades", ...)` with all columns
- `op.create_index` for `tenant_id` and `deployment_id`

- [ ] **Step 2: Add RLS policy to migration**

Edit the generated migration's `upgrade()` to add after the table creation:

```python
    op.execute("ALTER TABLE deployment_trades ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON deployment_trades
        USING (tenant_id = current_setting('app.current_tenant')::uuid)
    """)
```

And in `downgrade()`, add before `op.drop_table`:

```python
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON deployment_trades")
    op.execute("ALTER TABLE deployment_trades DISABLE ROW LEVEL SECURITY")
```

- [ ] **Step 3: Verify migration runs**

Run: `cd backend && .venv/bin/python -m alembic upgrade head`
Then: `cd backend && .venv/bin/python -m alembic downgrade -1`
Then: `cd backend && .venv/bin/python -m alembic upgrade head`
Expected: No errors on upgrade/downgrade/upgrade cycle.

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/migrations/versions/
git commit -m "feat: add Alembic migration for deployment_trades table with RLS"
```

---

## Task 3: Pydantic Schemas + DeploymentResponse.strategy_name

**Files:**
- Modify: `backend/app/deployments/schemas.py`
- Modify: `backend/app/deployments/router.py`
- Test: `backend/tests/test_live_trading.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_live_trading.py`:

```python
from tests.conftest import create_authenticated_user


async def _create_strategy_and_deployment(client, tokens, db_session, *, mode="paper", status="running"):
    """Helper: create a hosted strategy + deployment, return (strategy, deployment) dicts."""
    # Create strategy via API
    resp = await client.post(
        "/api/v1/hosted-strategies",
        json={"name": "SMA Bot", "description": "test", "code": "class Strategy:\n  pass", "entrypoint": "Strategy"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 201
    strategy = resp.json()

    # Create deployment via API
    resp = await client.post(
        f"/api/v1/hosted-strategies/{strategy['id']}/deployments",
        json={"mode": mode, "symbol": "BTCUSDT", "exchange": "exchange1", "interval": "5m"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 201
    deployment = resp.json()

    # Set status directly in DB if needed
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


@pytest.mark.asyncio
async def test_deployment_response_includes_strategy_name(client, db_session):
    """DeploymentResponse should include strategy_name field."""
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest backend/tests/test_live_trading.py::test_deployment_response_includes_strategy_name -v`
Expected: FAIL — `assert "strategy_name" in data`

- [ ] **Step 3: Add strategy_name to DeploymentResponse**

In `backend/app/deployments/schemas.py`, add `strategy_name: str` to `DeploymentResponse` (after `id` field):

```python
class DeploymentResponse(BaseModel):
    id: str
    strategy_name: str
    strategy_code_id: str
    # ... rest unchanged
```

- [ ] **Step 4: Add all new schemas to schemas.py**

Append to `backend/app/deployments/schemas.py`:

```python
class ManualOrderRequest(BaseModel):
    action: str
    quantity: float
    order_type: str = "market"
    price: float | None = None
    trigger_price: float | None = None


class CancelOrderRequest(BaseModel):
    order_id: str


class DeploymentTradeResponse(BaseModel):
    id: str
    deployment_id: str
    order_id: str
    broker_order_id: str | None
    action: str
    quantity: float
    order_type: str
    price: float | None
    trigger_price: float | None
    fill_price: float | None
    fill_quantity: float | None
    status: str
    is_manual: bool
    realized_pnl: float | None
    created_at: str
    filled_at: str | None
    strategy_name: str
    symbol: str


class TradesResponse(BaseModel):
    trades: list[DeploymentTradeResponse]
    total: int
    offset: int
    limit: int


class RecentTradesResponse(BaseModel):
    trades: list[DeploymentTradeResponse]
    total: int


class PositionResponse(BaseModel):
    deployment_id: str
    position: dict | None
    portfolio: dict
    open_orders: list  # Full order objects from DeploymentState
    open_orders_count: int
    total_realized_pnl: float


class MetricsResponse(BaseModel):
    total_return: float
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    total_trades: int
    avg_trade_pnl: float
    best_trade: float | None
    worst_trade: float | None


class ComparisonResponse(BaseModel):
    backtest: dict
    current: dict
    deltas: dict
    backtest_deployment_id: str
    promotion_chain: list[str]


class AggregateStatsResponse(BaseModel):
    total_deployed_capital: float
    aggregate_pnl: float
    aggregate_pnl_pct: float
    active_deployments: int
    todays_trades: int


class StopAllResponse(BaseModel):
    deployments: list[DeploymentResponse]
    orders_cancelled: int
```

- [ ] **Step 5: Update _deployment_to_response and imports in router.py**

In `backend/app/deployments/router.py`:

1. Add `selectinload` import: `from sqlalchemy.orm import selectinload`
2. Add `strategy_name` to `_deployment_to_response()`:

```python
def _deployment_to_response(dep: StrategyDeployment) -> DeploymentResponse:
    return DeploymentResponse(
        id=str(dep.id),
        strategy_name=dep.strategy_code.name if dep.strategy_code else "",
        strategy_code_id=str(dep.strategy_code_id),
        # ... rest unchanged
    )
```

3. In every query that returns deployments, add `.options(selectinload(StrategyDeployment.strategy_code))`. This affects these functions:
   - `list_strategy_deployments` (the query at ~line 100)
   - `list_all_deployments` (the query at ~line 125)
   - `get_deployment` (the query at ~line 145)
   - `pause_deployment`, `resume_deployment`, `stop_deployment` (their initial queries)
   - `stop_all_deployments` (the query at ~line 418)
   - `promote_deployment` (the query at ~line 468)

For example, change:
```python
select(StrategyDeployment).where(...)
```
to:
```python
select(StrategyDeployment).where(...).options(selectinload(StrategyDeployment.strategy_code))
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/bin/python -m pytest backend/tests/test_live_trading.py::test_deployment_response_includes_strategy_name -v`
Expected: PASS

- [ ] **Step 7: Run existing deployment tests to verify no regressions**

Run: `.venv/bin/python -m pytest backend/tests/test_deployments_router.py -v`
Expected: All existing tests PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/deployments/schemas.py backend/app/deployments/router.py backend/tests/test_live_trading.py
git commit -m "feat: add strategy_name to DeploymentResponse + new live trading schemas"
```

---

## Task 4: Trade Service Module

**Files:**
- Create: `backend/app/deployments/trade_service.py`
- Test: `backend/tests/test_live_trading.py`

- [ ] **Step 1: Write failing tests for trade service**

Add to `backend/tests/test_live_trading.py`:

```python
from app.deployments.trade_service import compute_live_metrics, compute_pnl, build_equity_curve


def test_compute_pnl_closing_long():
    """PnL for selling to close a long position."""
    pnl = compute_pnl(action="SELL", fill_price=110.0, fill_quantity=2.0, avg_entry_price=100.0)
    assert pnl == 20.0


def test_compute_pnl_closing_short():
    """PnL for buying to close a short position."""
    pnl = compute_pnl(action="BUY", fill_price=90.0, fill_quantity=2.0, avg_entry_price=100.0)
    assert pnl == 20.0


def test_compute_pnl_opening_position():
    """No PnL when opening a position (no avg_entry_price)."""
    pnl = compute_pnl(action="BUY", fill_price=100.0, fill_quantity=1.0, avg_entry_price=None)
    assert pnl is None


def test_compute_live_metrics_with_trades():
    """Compute metrics from filled trades."""
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
    """Metrics with no trades returns sensible defaults."""
    result = compute_live_metrics([], initial_capital=1000.0)
    assert result["total_trades"] == 0
    assert result["best_trade"] is None
    assert result["worst_trade"] is None
    assert result["win_rate"] == 0.0


def test_build_equity_curve():
    """Equity curve from sequential PnLs."""
    pnls = [10.0, -5.0, 20.0]
    curve = build_equity_curve(pnls, initial_capital=1000.0)
    assert len(curve) == 4  # initial + 3 trades
    assert curve[0]["equity"] == 1000.0
    assert curve[1]["equity"] == 1010.0
    assert curve[2]["equity"] == 1005.0
    assert curve[3]["equity"] == 1025.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest backend/tests/test_live_trading.py -k "compute_pnl or compute_live_metrics or build_equity_curve" -v`
Expected: FAIL — `ImportError: cannot import name 'compute_live_metrics' from 'app.deployments.trade_service'`

- [ ] **Step 3: Implement trade_service.py**

Create `backend/app/deployments/trade_service.py`:

```python
"""Trade business logic for live trading features."""

from __future__ import annotations

from app.analytics.metrics import compute_metrics


def compute_pnl(
    action: str,
    fill_price: float,
    fill_quantity: float,
    avg_entry_price: float | None,
) -> float | None:
    """Compute realized PnL for a position-closing trade.

    Returns None if avg_entry_price is None (opening trade).
    """
    if avg_entry_price is None:
        return None
    if action == "SELL":
        return (fill_price - avg_entry_price) * fill_quantity
    elif action == "BUY":
        return (avg_entry_price - fill_price) * fill_quantity
    return None


def compute_live_metrics(trades: list[dict], initial_capital: float) -> dict:
    """Compute live performance metrics from filled trade PnLs.

    Each trade dict must have a "pnl" key.
    Uses compute_metrics() for base metrics, then adds best/worst trade separately.
    """
    total_trades = len(trades)

    if total_trades == 0:
        return {
            "total_return": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "total_trades": 0,
            "avg_trade_pnl": 0.0,
            "best_trade": None,
            "worst_trade": None,
        }

    # Build equity curve for compute_metrics
    equity_curve = build_equity_curve(
        [t["pnl"] for t in trades], initial_capital
    )

    base = compute_metrics(trades, equity_curve, initial_capital)

    # Add best/worst trade (not in compute_metrics)
    pnls = [t["pnl"] for t in trades]
    base["best_trade"] = max(pnls)
    base["worst_trade"] = min(pnls)

    return base


def build_equity_curve(pnls: list[float], initial_capital: float) -> list[dict]:
    """Build equity curve from sequential PnL values."""
    curve = [{"equity": initial_capital}]
    running = initial_capital
    for pnl in pnls:
        running += pnl
        curve.append({"equity": running})
    return curve
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest backend/tests/test_live_trading.py -k "compute_pnl or compute_live_metrics or build_equity_curve" -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/deployments/trade_service.py backend/tests/test_live_trading.py
git commit -m "feat: add trade service with PnL calculation and live metrics"
```

---

## Task 5: order_router DeploymentTrade Integration

**Files:**
- Modify: `backend/app/strategy_runner/order_router.py`
- Test: `backend/tests/test_live_trading.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_live_trading.py`:

```python
from unittest.mock import AsyncMock, patch

from app.strategy_runner.order_router import dispatch_orders
from app.db.models import DeploymentTrade


@pytest.mark.asyncio
async def test_dispatch_orders_creates_trade_record(db_session):
    """dispatch_orders() should create a DeploymentTrade row for each order."""
    tenant_id = uuid.uuid4()

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

    orders = [
        {"id": "order1", "action": "buy", "quantity": 1.0, "order_type": "market"},
    ]

    results = await dispatch_orders(orders, dep, db_session)
    await db_session.commit()

    assert len(results) == 1
    assert results[0]["status"] == "submitted"

    # Verify DeploymentTrade was created
    trade_result = await db_session.execute(
        select(DeploymentTrade).where(DeploymentTrade.deployment_id == dep.id)
    )
    trade = trade_result.scalar_one()
    assert trade.order_id == "order1"
    assert trade.action == "BUY"
    assert trade.status == "filled"  # paper mode fills immediately
    assert trade.fill_price is not None or trade.status == "filled"


@pytest.mark.asyncio
async def test_dispatch_orders_rejected_no_trade_record(db_session):
    """Rejected orders (unsupported type) still get a trade record with rejected status."""
    tenant_id = uuid.uuid4()

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

    orders = [
        {"id": "order2", "action": "buy", "quantity": 1.0, "order_type": "stop"},
    ]

    results = await dispatch_orders(orders, dep, db_session)
    await db_session.commit()

    assert results[0]["status"] == "rejected"

    trade_result = await db_session.execute(
        select(DeploymentTrade).where(DeploymentTrade.deployment_id == dep.id)
    )
    trade = trade_result.scalar_one()
    assert trade.status == "rejected"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest backend/tests/test_live_trading.py -k "dispatch_orders" -v`
Expected: FAIL — no DeploymentTrade rows found

- [ ] **Step 3: Modify dispatch_orders to write DeploymentTrade**

Update `backend/app/strategy_runner/order_router.py`:

```python
import logging
from datetime import datetime, timezone

from app.db.models import StrategyDeployment, DeploymentTrade

logger = logging.getLogger(__name__)

ORDER_TYPE_MAP = {
    "market": "MARKET",
    "limit": "LIMIT",
    "stop": "SL-M",
    "stop_limit": "SL",
}

EXCHANGE1_UNSUPPORTED = {"stop", "stop_limit"}


def translate_order(order: dict, deployment: StrategyDeployment) -> dict | None:
    """Translate strategy order to broker format."""
    order_type = order.get("order_type", "market")

    if deployment.exchange == "exchange1" and order_type in EXCHANGE1_UNSUPPORTED:
        logger.warning(f"Exchange1 does not support {order_type} orders, rejecting")
        return None

    return {
        "symbol": deployment.symbol,
        "exchange": deployment.exchange,
        "product_type": deployment.product_type,
        "action": order["action"].upper(),
        "quantity": order["quantity"],
        "order_type": ORDER_TYPE_MAP.get(order_type, "MARKET"),
        "price": order.get("price"),
        "trigger_price": order.get("trigger_price"),
    }


async def dispatch_orders(orders: list[dict], deployment: StrategyDeployment, session) -> list[dict]:
    """Route orders to the appropriate broker and record DeploymentTrade rows."""
    results = []
    for order in orders:
        order_type_raw = order.get("order_type", "market")
        translated = translate_order(order, deployment)

        # Create trade record for every order attempt
        trade = DeploymentTrade(
            tenant_id=deployment.tenant_id,
            deployment_id=deployment.id,
            order_id=order["id"],
            action=order["action"].upper(),
            quantity=order["quantity"],
            order_type=ORDER_TYPE_MAP.get(order_type_raw, "MARKET"),
            price=order.get("price"),
            trigger_price=order.get("trigger_price"),
            status="submitted",
            is_manual=False,
        )
        session.add(trade)

        if translated is None:
            trade.status = "rejected"
            results.append({"order_id": order["id"], "status": "rejected", "reason": "unsupported_order_type"})
            continue

        if deployment.mode == "paper":
            # Paper mode: immediate simulated fill
            trade.status = "filled"
            trade.fill_quantity = order["quantity"]
            trade.filled_at = datetime.now(timezone.utc)
            results.append({"order_id": order["id"], "status": "submitted", "broker_order": translated})
        elif deployment.mode == "live":
            try:
                from app.crypto.encryption import decrypt_credentials
                from app.brokers.factory import get_broker
                from app.db.models import BrokerConnection

                bc = await session.get(BrokerConnection, deployment.broker_connection_id)
                if not bc:
                    trade.status = "rejected"
                    results.append({"order_id": order["id"], "status": "rejected", "reason": "broker_not_found"})
                    continue

                credentials = decrypt_credentials(bc.tenant_id, bc.credentials)
                broker = await get_broker(bc.broker_type, credentials)
                try:
                    broker_result = await broker.place_order(translated)
                    trade.status = "filled"
                    trade.fill_price = broker_result.get("fill_price")
                    trade.fill_quantity = broker_result.get("fill_quantity")
                    trade.broker_order_id = broker_result.get("order_id")
                    trade.filled_at = datetime.now(timezone.utc)
                    results.append({"order_id": order["id"], "status": "submitted", "broker_result": broker_result})
                finally:
                    await broker.close()
            except Exception as e:
                logger.error(f"Failed to dispatch order: {e}")
                trade.status = "failed"
                results.append({"order_id": order["id"], "status": "failed", "reason": str(e)})

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest backend/tests/test_live_trading.py -k "dispatch_orders" -v`
Expected: All PASS

- [ ] **Step 5: Run existing strategy runner tests**

Run: `.venv/bin/python -m pytest backend/tests/test_strategy_runner.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/strategy_runner/order_router.py backend/tests/test_live_trading.py
git commit -m "feat: write DeploymentTrade records in dispatch_orders"
```

---

## Task 6: Read-Only Trade Endpoints (trades, position, recent-trades)

**Files:**
- Modify: `backend/app/deployments/router.py`
- Test: `backend/tests/test_live_trading.py`

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_live_trading.py`:

```python
@pytest.mark.asyncio
async def test_get_trades_endpoint(client, db_session):
    """GET /api/v1/deployments/{id}/trades returns paginated trades."""
    tokens = await create_authenticated_user(client)
    strategy, deployment = await _create_strategy_and_deployment(client, tokens, db_session)

    # Insert trade directly
    dep_id = uuid.UUID(deployment["id"])
    from sqlalchemy import update
    from app.db.models import StrategyDeployment
    result = await db_session.execute(
        select(StrategyDeployment).where(StrategyDeployment.id == dep_id)
    )
    dep = result.scalar_one()

    trade = DeploymentTrade(
        tenant_id=dep.tenant_id,
        deployment_id=dep.id,
        order_id="t1",
        action="BUY",
        quantity=1.0,
        order_type="MARKET",
        status="filled",
        is_manual=False,
    )
    db_session.add(trade)
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/deployments/{deployment['id']}/trades",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "trades" in data
    assert "total" in data
    assert data["total"] == 1
    assert data["trades"][0]["order_id"] == "t1"
    assert "strategy_name" in data["trades"][0]
    assert "symbol" in data["trades"][0]


@pytest.mark.asyncio
async def test_get_position_endpoint(client, db_session):
    """GET /api/v1/deployments/{id}/position returns position info."""
    tokens = await create_authenticated_user(client)
    strategy, deployment = await _create_strategy_and_deployment(client, tokens, db_session)

    # Create DeploymentState
    dep_id = uuid.UUID(deployment["id"])
    result = await db_session.execute(
        select(StrategyDeployment).where(StrategyDeployment.id == dep_id)
    )
    dep = result.scalar_one()

    state = DeploymentState(
        deployment_id=dep.id,
        tenant_id=dep.tenant_id,
        position={"quantity": 1.0, "avg_entry_price": 100.0, "unrealized_pnl": 5.0},
        portfolio={"balance": 10000, "equity": 10005, "available_margin": 9000},
        open_orders=[{"id": "o1"}],
    )
    db_session.add(state)
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
    assert data["total_realized_pnl"] == 0.0  # no filled trades yet


@pytest.mark.asyncio
async def test_recent_trades_endpoint(client, db_session):
    """GET /api/v1/deployments/recent-trades returns cross-deployment trades."""
    tokens = await create_authenticated_user(client)
    strategy, deployment = await _create_strategy_and_deployment(client, tokens, db_session)

    dep_id = uuid.UUID(deployment["id"])
    result = await db_session.execute(
        select(StrategyDeployment).where(StrategyDeployment.id == dep_id)
    )
    dep = result.scalar_one()

    trade = DeploymentTrade(
        tenant_id=dep.tenant_id,
        deployment_id=dep.id,
        order_id="rt1",
        action="BUY",
        quantity=1.0,
        order_type="MARKET",
        status="filled",
        is_manual=False,
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest backend/tests/test_live_trading.py -k "test_get_trades or test_get_position or test_recent_trades" -v`
Expected: FAIL — 404 (endpoints don't exist yet)

- [ ] **Step 3: Add trade response helper to router.py**

Add helper function and imports to `backend/app/deployments/router.py`:

```python
# Add to imports at top:
from app.db.models import DeploymentTrade
from app.deployments.schemas import (
    # ... existing imports ...
    DeploymentTradeResponse,
    TradesResponse,
    RecentTradesResponse,
    PositionResponse,
)

def _trade_to_response(trade: DeploymentTrade, strategy_name: str, symbol: str) -> DeploymentTradeResponse:
    return DeploymentTradeResponse(
        id=str(trade.id),
        deployment_id=str(trade.deployment_id),
        order_id=trade.order_id,
        broker_order_id=trade.broker_order_id,
        action=trade.action,
        quantity=float(trade.quantity),
        order_type=trade.order_type,
        price=float(trade.price) if trade.price is not None else None,
        trigger_price=float(trade.trigger_price) if trade.trigger_price is not None else None,
        fill_price=float(trade.fill_price) if trade.fill_price is not None else None,
        fill_quantity=float(trade.fill_quantity) if trade.fill_quantity is not None else None,
        status=trade.status,
        is_manual=trade.is_manual,
        realized_pnl=float(trade.realized_pnl) if trade.realized_pnl is not None else None,
        created_at=trade.created_at.isoformat() if trade.created_at else "",
        filled_at=trade.filled_at.isoformat() if trade.filled_at else None,
        strategy_name=strategy_name,
        symbol=symbol,
    )
```

- [ ] **Step 4: Add GET trades endpoint**

Add to `backend/app/deployments/router.py`:

```python
@router.get(
    "/api/v1/deployments/{deployment_id}/trades",
    response_model=TradesResponse,
)
async def get_deployment_trades(
    deployment_id: uuid.UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    is_manual: bool | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyDeployment)
        .where(StrategyDeployment.id == deployment_id, StrategyDeployment.tenant_id == tenant_id)
        .options(selectinload(StrategyDeployment.strategy_code))
    )
    dep = result.scalar_one_or_none()
    if not dep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")

    query = select(DeploymentTrade).where(
        DeploymentTrade.deployment_id == deployment_id,
        DeploymentTrade.tenant_id == tenant_id,
    )
    if is_manual is not None:
        query = query.where(DeploymentTrade.is_manual == is_manual)

    count_result = await session.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    result = await session.execute(
        query.order_by(DeploymentTrade.created_at.desc()).offset(offset).limit(limit)
    )
    trades = result.scalars().all()

    strategy_name = dep.strategy_code.name if dep.strategy_code else ""
    return TradesResponse(
        trades=[_trade_to_response(t, strategy_name, dep.symbol) for t in trades],
        total=total,
        offset=offset,
        limit=limit,
    )
```

- [ ] **Step 5: Add GET position endpoint**

```python
@router.get(
    "/api/v1/deployments/{deployment_id}/position",
    response_model=PositionResponse,
)
async def get_deployment_position(
    deployment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyDeployment).where(
            StrategyDeployment.id == deployment_id, StrategyDeployment.tenant_id == tenant_id
        )
    )
    dep = result.scalar_one_or_none()
    if not dep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")

    state = await session.get(DeploymentState, deployment_id)

    # Sum realized PnL from trades
    pnl_result = await session.execute(
        select(func.coalesce(func.sum(DeploymentTrade.realized_pnl), 0)).where(
            DeploymentTrade.deployment_id == deployment_id,
            DeploymentTrade.tenant_id == tenant_id,
            DeploymentTrade.realized_pnl.isnot(None),
        )
    )
    total_realized_pnl = float(pnl_result.scalar() or 0)

    open_orders = state.open_orders if state and state.open_orders else []
    return PositionResponse(
        deployment_id=str(deployment_id),
        position=state.position if state else None,
        portfolio=state.portfolio if state else {},
        open_orders=open_orders,
        open_orders_count=len(open_orders),
        total_realized_pnl=total_realized_pnl,
    )
```

- [ ] **Step 6: Add GET recent-trades endpoint**

**Important:** This endpoint must be registered BEFORE `/{deployment_id}/...` routes to avoid FastAPI treating "recent-trades" as a UUID. Place it near the top of the route declarations, or use a separate prefix.

```python
@router.get(
    "/api/v1/deployments/recent-trades",
    response_model=RecentTradesResponse,
)
async def get_recent_trades(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])

    count_result = await session.execute(
        select(func.count()).where(DeploymentTrade.tenant_id == tenant_id)
    )
    total = count_result.scalar() or 0

    result = await session.execute(
        select(DeploymentTrade)
        .where(DeploymentTrade.tenant_id == tenant_id)
        .order_by(DeploymentTrade.created_at.desc())
        .limit(limit)
    )
    trades = result.scalars().all()

    # Batch-load deployment info for strategy names
    dep_ids = {t.deployment_id for t in trades}
    if dep_ids:
        dep_result = await session.execute(
            select(StrategyDeployment)
            .where(StrategyDeployment.id.in_(dep_ids))
            .options(selectinload(StrategyDeployment.strategy_code))
        )
        deps = {d.id: d for d in dep_result.scalars().all()}
    else:
        deps = {}

    trade_responses = []
    for t in trades:
        dep = deps.get(t.deployment_id)
        name = dep.strategy_code.name if dep and dep.strategy_code else ""
        symbol = dep.symbol if dep else ""
        trade_responses.append(_trade_to_response(t, name, symbol))

    return RecentTradesResponse(trades=trade_responses, total=total)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest backend/tests/test_live_trading.py -k "test_get_trades or test_get_position or test_recent_trades" -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/deployments/router.py backend/tests/test_live_trading.py
git commit -m "feat: add trades, position, and recent-trades endpoints"
```

---

## Task 7: Metrics, Comparison, and Aggregate Stats Endpoints

**Files:**
- Modify: `backend/app/deployments/router.py`
- Test: `backend/tests/test_live_trading.py`

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_live_trading.py`:

```python
@pytest.mark.asyncio
async def test_get_metrics_endpoint(client, db_session):
    """GET /api/v1/deployments/{id}/metrics returns computed metrics."""
    tokens = await create_authenticated_user(client)
    strategy, deployment = await _create_strategy_and_deployment(client, tokens, db_session)

    dep_id = uuid.UUID(deployment["id"])
    result = await db_session.execute(
        select(StrategyDeployment).where(StrategyDeployment.id == dep_id)
    )
    dep = result.scalar_one()

    # Add a filled trade with PnL
    trade = DeploymentTrade(
        tenant_id=dep.tenant_id,
        deployment_id=dep.id,
        order_id="m1",
        action="SELL",
        quantity=1.0,
        order_type="MARKET",
        status="filled",
        is_manual=False,
        realized_pnl=50.0,
        fill_price=110.0,
        fill_quantity=1.0,
    )
    db_session.add(trade)
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/deployments/{deployment['id']}/metrics",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_trades"] == 1
    assert data["best_trade"] == 50.0
    assert data["worst_trade"] == 50.0


@pytest.mark.asyncio
async def test_get_aggregate_stats_endpoint(client, db_session):
    """GET /api/v1/deployments/aggregate-stats returns aggregate stats."""
    tokens = await create_authenticated_user(client)
    strategy, deployment = await _create_strategy_and_deployment(client, tokens, db_session)

    resp = await client.get(
        "/api/v1/deployments/aggregate-stats",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total_deployed_capital" in data
    assert "aggregate_pnl" in data
    assert "active_deployments" in data
    assert "todays_trades" in data


@pytest.mark.asyncio
async def test_get_comparison_no_promotion_chain(client, db_session):
    """GET /api/v1/deployments/{id}/comparison returns 404 when no backtest in chain."""
    tokens = await create_authenticated_user(client)
    strategy, deployment = await _create_strategy_and_deployment(client, tokens, db_session)

    resp = await client.get(
        f"/api/v1/deployments/{deployment['id']}/comparison",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest backend/tests/test_live_trading.py -k "test_get_metrics or test_get_aggregate or test_get_comparison" -v`
Expected: FAIL — 404 / endpoints don't exist

- [ ] **Step 3: Add imports to router.py**

```python
from app.deployments.schemas import (
    # ... existing + previously added ...
    MetricsResponse,
    ComparisonResponse,
    AggregateStatsResponse,
)
from app.deployments.trade_service import compute_live_metrics, build_equity_curve
```

- [ ] **Step 4: Add GET metrics endpoint**

```python
@router.get(
    "/api/v1/deployments/{deployment_id}/metrics",
    response_model=MetricsResponse,
)
async def get_deployment_metrics(
    deployment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyDeployment).where(
            StrategyDeployment.id == deployment_id, StrategyDeployment.tenant_id == tenant_id
        )
    )
    dep = result.scalar_one_or_none()
    if not dep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")

    # For completed backtests, return stored metrics
    if dep.mode == "backtest" and dep.status == "completed":
        sr_result = await session.execute(
            select(StrategyResult).where(
                StrategyResult.deployment_id == deployment_id,
                StrategyResult.tenant_id == tenant_id,
            ).order_by(StrategyResult.created_at.desc()).limit(1)
        )
        sr = sr_result.scalar_one_or_none()
        if sr and sr.metrics:
            return MetricsResponse(
                **sr.metrics,
                best_trade=None,
                worst_trade=None,
            )

    # For paper/live: compute from DeploymentTrade
    result = await session.execute(
        select(DeploymentTrade).where(
            DeploymentTrade.deployment_id == deployment_id,
            DeploymentTrade.tenant_id == tenant_id,
            DeploymentTrade.status == "filled",
            DeploymentTrade.realized_pnl.isnot(None),
        ).order_by(DeploymentTrade.created_at.asc())
    )
    filled_trades = result.scalars().all()

    initial_capital = (dep.config or {}).get("initial_capital", 10000.0)
    trades_data = [{"pnl": float(t.realized_pnl)} for t in filled_trades]
    metrics = compute_live_metrics(trades_data, initial_capital)

    return MetricsResponse(**metrics)
```

- [ ] **Step 5: Add GET comparison endpoint**

```python
@router.get(
    "/api/v1/deployments/{deployment_id}/comparison",
    response_model=ComparisonResponse,
)
async def get_deployment_comparison(
    deployment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyDeployment).where(
            StrategyDeployment.id == deployment_id, StrategyDeployment.tenant_id == tenant_id
        )
    )
    dep = result.scalar_one_or_none()
    if not dep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")

    # Walk promotion chain to find backtest
    chain = [str(dep.id)]
    current = dep
    backtest_dep = None
    while current.promoted_from_id:
        result = await session.execute(
            select(StrategyDeployment).where(StrategyDeployment.id == current.promoted_from_id)
        )
        parent = result.scalar_one_or_none()
        if not parent:
            break
        chain.append(str(parent.id))
        if parent.mode == "backtest":
            backtest_dep = parent
            break
        current = parent

    if not backtest_dep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No backtest in promotion chain")

    # Get backtest metrics
    sr_result = await session.execute(
        select(StrategyResult).where(
            StrategyResult.deployment_id == backtest_dep.id,
            StrategyResult.tenant_id == tenant_id,
        ).order_by(StrategyResult.created_at.desc()).limit(1)
    )
    sr = sr_result.scalar_one_or_none()
    backtest_metrics = sr.metrics if sr and sr.metrics else {}

    # Get current live metrics
    trade_result = await session.execute(
        select(DeploymentTrade).where(
            DeploymentTrade.deployment_id == deployment_id,
            DeploymentTrade.tenant_id == tenant_id,
            DeploymentTrade.status == "filled",
            DeploymentTrade.realized_pnl.isnot(None),
        ).order_by(DeploymentTrade.created_at.asc())
    )
    filled_trades = trade_result.scalars().all()

    initial_capital = (dep.config or {}).get("initial_capital", 10000.0)
    trades_data = [{"pnl": float(t.realized_pnl)} for t in filled_trades]
    current_metrics = compute_live_metrics(trades_data, initial_capital)

    # Compute deltas
    deltas = {}
    for key in ["total_return", "win_rate", "profit_factor", "sharpe_ratio", "max_drawdown", "total_trades", "avg_trade_pnl"]:
        bt_val = backtest_metrics.get(key, 0)
        cur_val = current_metrics.get(key, 0)
        deltas[key] = cur_val - bt_val

    return ComparisonResponse(
        backtest=backtest_metrics,
        current=current_metrics,
        deltas=deltas,
        backtest_deployment_id=str(backtest_dep.id),
        promotion_chain=list(reversed(chain)),
    )
```

- [ ] **Step 6: Add GET aggregate-stats endpoint**

**Important:** Place this BEFORE `/{deployment_id}/...` routes.

```python
@router.get(
    "/api/v1/deployments/aggregate-stats",
    response_model=AggregateStatsResponse,
)
async def get_aggregate_stats(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])

    # Get all active deployments
    result = await session.execute(
        select(StrategyDeployment).where(
            StrategyDeployment.tenant_id == tenant_id,
            StrategyDeployment.status.in_(["running", "paused"]),
        )
    )
    active_deps = result.scalars().all()

    total_equity = 0.0
    total_capital = 0.0
    for dep in active_deps:
        state = await session.get(DeploymentState, dep.id)
        if state and state.portfolio:
            total_equity += state.portfolio.get("equity", 0)
        total_capital += (dep.config or {}).get("initial_capital", 0)

    aggregate_pnl = total_equity - total_capital if total_capital > 0 else 0
    aggregate_pnl_pct = (aggregate_pnl / total_capital * 100) if total_capital > 0 else 0

    # Count today's trades
    from datetime import date
    today_start = datetime(date.today().year, date.today().month, date.today().day, tzinfo=UTC)
    count_result = await session.execute(
        select(func.count()).where(
            DeploymentTrade.tenant_id == tenant_id,
            DeploymentTrade.created_at >= today_start,
        )
    )
    todays_trades = count_result.scalar() or 0

    return AggregateStatsResponse(
        total_deployed_capital=total_capital,
        aggregate_pnl=aggregate_pnl,
        aggregate_pnl_pct=aggregate_pnl_pct,
        active_deployments=len(active_deps),
        todays_trades=todays_trades,
    )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest backend/tests/test_live_trading.py -k "test_get_metrics or test_get_aggregate or test_get_comparison" -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/deployments/router.py backend/tests/test_live_trading.py
git commit -m "feat: add metrics, comparison, and aggregate stats endpoints"
```

---

## Task 8: Manual Order and Cancel Order Endpoints

**Files:**
- Modify: `backend/app/deployments/router.py`
- Test: `backend/tests/test_live_trading.py`

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_live_trading.py`:

```python
@pytest.mark.asyncio
async def test_manual_order_paper_mode(client, db_session):
    """POST manual-order creates trade with is_manual=true in paper mode."""
    tokens = await create_authenticated_user(client)
    strategy, deployment = await _create_strategy_and_deployment(client, tokens, db_session, mode="paper", status="running")

    # Create DeploymentState (required for running deployment)
    dep_id = uuid.UUID(deployment["id"])
    result = await db_session.execute(
        select(StrategyDeployment).where(StrategyDeployment.id == dep_id)
    )
    dep = result.scalar_one()
    state = DeploymentState(
        deployment_id=dep.id,
        tenant_id=dep.tenant_id,
        position=None,
        portfolio={"balance": 10000, "equity": 10000, "available_margin": 10000},
        open_orders=[],
    )
    db_session.add(state)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/deployments/{deployment['id']}/manual-order",
        json={"action": "buy", "quantity": 1.0, "order_type": "market"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_manual"] is True
    assert data["action"] == "BUY"
    assert data["status"] == "filled"


@pytest.mark.asyncio
async def test_manual_order_rejects_backtest(client, db_session):
    """Manual orders not allowed on backtests."""
    tokens = await create_authenticated_user(client)
    strategy, deployment = await _create_strategy_and_deployment(client, tokens, db_session, mode="backtest", status="running")

    resp = await client.post(
        f"/api/v1/deployments/{deployment['id']}/manual-order",
        json={"action": "buy", "quantity": 1.0},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_cancel_order_endpoint(client, db_session):
    """POST cancel-order cancels an open order."""
    tokens = await create_authenticated_user(client)
    strategy, deployment = await _create_strategy_and_deployment(client, tokens, db_session, mode="paper", status="running")

    dep_id = uuid.UUID(deployment["id"])
    result = await db_session.execute(
        select(StrategyDeployment).where(StrategyDeployment.id == dep_id)
    )
    dep = result.scalar_one()

    # Create state with open order
    state = DeploymentState(
        deployment_id=dep.id,
        tenant_id=dep.tenant_id,
        position=None,
        portfolio={"balance": 10000, "equity": 10000, "available_margin": 10000},
        open_orders=[{"id": "cancel_me", "action": "buy", "quantity": 1.0}],
    )
    db_session.add(state)

    # Create corresponding trade record
    trade = DeploymentTrade(
        tenant_id=dep.tenant_id,
        deployment_id=dep.id,
        order_id="cancel_me",
        action="BUY",
        quantity=1.0,
        order_type="LIMIT",
        status="submitted",
        is_manual=False,
    )
    db_session.add(trade)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/deployments/{deployment['id']}/cancel-order",
        json={"order_id": "cancel_me"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "cancelled"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest backend/tests/test_live_trading.py -k "test_manual_order or test_cancel_order" -v`
Expected: FAIL

- [ ] **Step 3: Add imports**

```python
from app.deployments.schemas import (
    # ... existing ...
    ManualOrderRequest,
    CancelOrderRequest,
    DeploymentTradeResponse,
)
from app.strategy_runner.order_router import translate_order, dispatch_orders, ORDER_TYPE_MAP
```

- [ ] **Step 4: Add POST manual-order endpoint**

```python
@router.post(
    "/api/v1/deployments/{deployment_id}/manual-order",
    response_model=DeploymentTradeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def place_manual_order(
    deployment_id: uuid.UUID,
    body: ManualOrderRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyDeployment)
        .where(StrategyDeployment.id == deployment_id, StrategyDeployment.tenant_id == tenant_id)
        .options(selectinload(StrategyDeployment.strategy_code))
    )
    dep = result.scalar_one_or_none()
    if not dep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")
    if dep.status not in ("running", "paused"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Deployment not active")
    if dep.mode == "backtest":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot place manual orders on backtests")

    order_type_mapped = ORDER_TYPE_MAP.get(body.order_type, "MARKET")

    trade = DeploymentTrade(
        tenant_id=tenant_id,
        deployment_id=dep.id,
        order_id=uuid.uuid4().hex[:16],
        action=body.action.upper(),
        quantity=body.quantity,
        order_type=order_type_mapped,
        price=body.price,
        trigger_price=body.trigger_price,
        status="submitted",
        is_manual=True,
    )

    if dep.mode == "paper":
        trade.status = "filled"
        trade.fill_quantity = body.quantity
        trade.filled_at = datetime.now(UTC)
    elif dep.mode == "live":
        # Handle broker dispatch directly (NOT via dispatch_orders, which would create a duplicate trade)
        translated = translate_order(
            {"action": body.action, "quantity": body.quantity, "order_type": body.order_type,
             "price": body.price, "trigger_price": body.trigger_price},
            dep,
        )
        if translated is None:
            trade.status = "rejected"
        else:
            try:
                from app.crypto.encryption import decrypt_credentials
                from app.brokers.factory import get_broker
                from app.db.models import BrokerConnection

                bc = await session.get(BrokerConnection, dep.broker_connection_id)
                if not bc:
                    trade.status = "rejected"
                else:
                    credentials = decrypt_credentials(bc.tenant_id, bc.credentials)
                    broker = await get_broker(bc.broker_type, credentials)
                    try:
                        broker_result = await broker.place_order(translated)
                        trade.fill_price = broker_result.get("fill_price")
                        trade.fill_quantity = broker_result.get("fill_quantity")
                        trade.broker_order_id = broker_result.get("order_id")
                        trade.status = "filled"
                        trade.filled_at = datetime.now(UTC)
                    finally:
                        await broker.close()
            except Exception:
                trade.status = "failed"

    session.add(trade)
    await session.commit()
    await session.refresh(trade)

    strategy_name = dep.strategy_code.name if dep.strategy_code else ""
    return _trade_to_response(trade, strategy_name, dep.symbol)
```

- [ ] **Step 5: Add POST cancel-order endpoint**

```python
@router.post(
    "/api/v1/deployments/{deployment_id}/cancel-order",
    response_model=DeploymentTradeResponse,
)
async def cancel_order(
    deployment_id: uuid.UUID,
    body: CancelOrderRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyDeployment)
        .where(StrategyDeployment.id == deployment_id, StrategyDeployment.tenant_id == tenant_id)
        .options(selectinload(StrategyDeployment.strategy_code))
    )
    dep = result.scalar_one_or_none()
    if not dep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")

    # Find trade record
    trade_result = await session.execute(
        select(DeploymentTrade).where(
            DeploymentTrade.deployment_id == deployment_id,
            DeploymentTrade.order_id == body.order_id,
            DeploymentTrade.tenant_id == tenant_id,
        )
    )
    trade = trade_result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found")

    # For live mode, call broker cancel
    if dep.mode == "live" and trade.broker_order_id:
        try:
            from app.crypto.encryption import decrypt_credentials
            from app.brokers.factory import get_broker
            from app.db.models import BrokerConnection

            bc = await session.get(BrokerConnection, dep.broker_connection_id)
            if bc:
                credentials = decrypt_credentials(bc.tenant_id, bc.credentials)
                broker = await get_broker(bc.broker_type, credentials)
                try:
                    await broker.cancel_order(trade.broker_order_id)
                finally:
                    await broker.close()
        except Exception:
            pass  # Best effort cancel

    trade.status = "cancelled"

    # Remove from open_orders in state
    state = await session.get(DeploymentState, deployment_id)
    if state and state.open_orders:
        state.open_orders = [o for o in state.open_orders if o.get("id") != body.order_id]

    await session.commit()
    await session.refresh(trade)

    strategy_name = dep.strategy_code.name if dep.strategy_code else ""
    return _trade_to_response(trade, strategy_name, dep.symbol)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest backend/tests/test_live_trading.py -k "test_manual_order or test_cancel_order" -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/deployments/router.py backend/tests/test_live_trading.py
git commit -m "feat: add manual order and cancel order endpoints"
```

---

## Task 9: Enhanced stop-all Endpoint

**Files:**
- Modify: `backend/app/deployments/router.py`
- Test: `backend/tests/test_live_trading.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_live_trading.py`:

```python
@pytest.mark.asyncio
async def test_stop_all_returns_stop_all_response(client, db_session):
    """POST /api/v1/deployments/stop-all returns StopAllResponse with orders_cancelled."""
    tokens = await create_authenticated_user(client)
    strategy, deployment = await _create_strategy_and_deployment(client, tokens, db_session)

    resp = await client.post(
        "/api/v1/deployments/stop-all",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "deployments" in data
    assert "orders_cancelled" in data
    assert isinstance(data["deployments"], list)
    assert isinstance(data["orders_cancelled"], int)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest backend/tests/test_live_trading.py::test_stop_all_returns_stop_all_response -v`
Expected: FAIL — response is a list, not dict with "deployments" key

- [ ] **Step 3: Modify stop_all_deployments**

Update the `stop_all_deployments` function in `backend/app/deployments/router.py`:

1. Change `response_model=list[DeploymentResponse]` to `response_model=StopAllResponse` (import `StopAllResponse`)
2. Add order cancellation logic and new response format:

```python
@router.post(
    "/api/v1/deployments/stop-all",
    response_model=StopAllResponse,
)
async def stop_all_deployments(
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyDeployment).where(
            StrategyDeployment.tenant_id == tenant_id,
            StrategyDeployment.status.in_(["pending", "running", "paused"]),
        ).options(selectinload(StrategyDeployment.strategy_code))
    )
    deployments = result.scalars().all()
    now = datetime.now(UTC)
    stopped_ids = []
    orders_cancelled = 0

    for dep in deployments:
        dep.status = "stopped"
        dep.stopped_at = now
        stopped_ids.append(str(dep.id))

        # Cancel open orders
        open_trade_result = await session.execute(
            select(DeploymentTrade).where(
                DeploymentTrade.deployment_id == dep.id,
                DeploymentTrade.status == "submitted",
            )
        )
        open_trades = open_trade_result.scalars().all()
        for trade in open_trades:
            trade.status = "cancelled"
            orders_cancelled += 1

    await session.commit()

    redis = request.app.state.redis
    for d_id in stopped_ids:
        await redis.publish(
            "strategy-runner:deployments",
            json.dumps({"action": "unregister", "deployment_id": d_id}),
        )

    stopped = []
    for dep in deployments:
        await session.refresh(dep)
        stopped.append(_deployment_to_response(dep))

    return StopAllResponse(deployments=stopped, orders_cancelled=orders_cancelled)
```

- [ ] **Step 4: Run test and existing tests**

Run: `.venv/bin/python -m pytest backend/tests/test_live_trading.py::test_stop_all_returns_stop_all_response -v`
Expected: PASS

Run: `.venv/bin/python -m pytest backend/tests/test_deployments_router.py -k "stop_all" -v`
Expected: FAIL — existing test expects list, now gets dict. Update the existing test to expect the new shape.

- [ ] **Step 5: Update existing stop-all test**

In `backend/tests/test_deployments_router.py`, find the `test_stop_all_deployments` test and update the assertions:

Change from:
```python
assert isinstance(data, list)
```
to:
```python
assert "deployments" in data
assert "orders_cancelled" in data
assert isinstance(data["deployments"], list)
```

- [ ] **Step 6: Run all deployment tests**

Run: `.venv/bin/python -m pytest backend/tests/test_deployments_router.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/deployments/router.py backend/tests/test_live_trading.py backend/tests/test_deployments_router.py
git commit -m "feat: enhance stop-all with order cancellation and StopAllResponse"
```

---

## Task 10: Run Full Backend Test Suite

- [ ] **Step 1: Run all backend tests**

Run: `.venv/bin/python -m pytest backend/tests/ -v`
Expected: All PASS

- [ ] **Step 2: Fix any failures**

If any tests fail, diagnose and fix. Common issues:
- Missing imports (selectinload, DeploymentTrade)
- Route ordering (static routes like `/recent-trades` and `/aggregate-stats` must be registered BEFORE `/{deployment_id}` routes)
- `strategy_name` assertion failures in existing tests (need to eagerly load strategy_code)

- [ ] **Step 3: Commit fixes if any**

```bash
git add -A
git commit -m "fix: resolve test suite issues from live trading integration"
```

---

## Task 11: Frontend Types and Hooks

**Files:**
- Modify: `frontend/lib/api/types.ts`
- Modify: `frontend/lib/hooks/useApi.ts`

- [ ] **Step 1: Add strategy_name to Deployment interface**

In `frontend/lib/api/types.ts`, add `strategy_name: string;` to the `Deployment` interface (after `id`):

```typescript
export interface Deployment {
  id: string;
  strategy_name: string;
  strategy_code_id: string;
  // ... rest unchanged
}
```

- [ ] **Step 2: Add new TypeScript interfaces**

Append to `frontend/lib/api/types.ts`:

```typescript
// Live Trading
export interface DeploymentTrade {
  id: string;
  deployment_id: string;
  order_id: string;
  broker_order_id: string | null;
  action: string;
  quantity: number;
  order_type: string;
  price: number | null;
  trigger_price: number | null;
  fill_price: number | null;
  fill_quantity: number | null;
  status: string;
  is_manual: boolean;
  realized_pnl: number | null;
  created_at: string;
  filled_at: string | null;
  strategy_name: string;
  symbol: string;
}

export interface TradesResponse {
  trades: DeploymentTrade[];
  total: number;
  offset: number;
  limit: number;
}

export interface RecentTradesResponse {
  trades: DeploymentTrade[];
  total: number;
}

export interface PositionInfo {
  deployment_id: string;
  position: { quantity: number; avg_entry_price: number; unrealized_pnl: number } | null;
  portfolio: { balance: number; equity: number; available_margin: number };
  open_orders: { id: string; action: string; quantity: number; order_type?: string; price?: number }[];
  open_orders_count: number;
  total_realized_pnl: number;
}

export interface LiveMetrics {
  total_return: number;
  win_rate: number;
  profit_factor: number;
  sharpe_ratio: number;
  max_drawdown: number;
  total_trades: number;
  avg_trade_pnl: number;
  best_trade: number | null;
  worst_trade: number | null;
}

export interface ComparisonData {
  backtest: LiveMetrics;
  current: LiveMetrics;
  deltas: Record<string, number>;
  backtest_deployment_id: string;
  promotion_chain: string[];
}

export interface AggregateStats {
  total_deployed_capital: number;
  aggregate_pnl: number;
  aggregate_pnl_pct: number;
  active_deployments: number;
  todays_trades: number;
}

export interface StopAllResponse {
  deployments: Deployment[];
  orders_cancelled: number;
}
```

- [ ] **Step 3: Add new hooks**

Append to `frontend/lib/hooks/useApi.ts`, adding the necessary type imports:

```typescript
// Live Trading
export function useAggregateStats() {
  return useApiGet<AggregateStats>("/api/v1/deployments/aggregate-stats", { refreshInterval: 2000 });
}

export function useRecentTrades(limit = 20) {
  return useApiGet<RecentTradesResponse>(
    `/api/v1/deployments/recent-trades?limit=${limit}`,
    { refreshInterval: 5000 }
  );
}

export function useDeploymentTrades(id: string | undefined, offset = 0, limit = 50) {
  return useApiGet<TradesResponse>(
    id ? `/api/v1/deployments/${id}/trades?offset=${offset}&limit=${limit}` : null,
    { refreshInterval: 5000 }
  );
}

export function useDeploymentPosition(id: string | undefined) {
  return useApiGet<PositionInfo>(id ? `/api/v1/deployments/${id}/position` : null, { refreshInterval: 2000 });
}

export function useDeploymentMetrics(id: string | undefined) {
  return useApiGet<LiveMetrics>(id ? `/api/v1/deployments/${id}/metrics` : null, { refreshInterval: 10000 });
}

export function useDeploymentComparison(id: string | undefined) {
  return useApiGet<ComparisonData | null>(id ? `/api/v1/deployments/${id}/comparison` : null);
}
```

Add the necessary imports at the top of `useApi.ts` from `types.ts`:

```typescript
import type {
  // ... existing imports ...
  AggregateStats,
  RecentTradesResponse,
  TradesResponse,
  PositionInfo,
  LiveMetrics,
  ComparisonData,
} from "../api/types";
```

- [ ] **Step 4: Verify TypeScript compilation**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/api/types.ts frontend/lib/hooks/useApi.ts
git commit -m "feat: add frontend types and hooks for live trading"
```

---

## Task 12: Frontend Command Center Components and Page

**Files:**
- Create: `frontend/components/live-trading/AggregateStats.tsx`
- Create: `frontend/components/live-trading/LiveDeploymentCard.tsx`
- Create: `frontend/components/live-trading/KillSwitchButton.tsx`
- Create: `frontend/app/(dashboard)/live-trading/page.tsx`

- [ ] **Step 1: Create AggregateStats component**

Create `frontend/components/live-trading/AggregateStats.tsx`:

```tsx
"use client";
import { SimpleGrid } from "@chakra-ui/react";
import { StatCard } from "@/components/shared/StatCard";
import type { AggregateStats as AggregateStatsType } from "@/lib/api/types";

interface Props {
  stats: AggregateStatsType | undefined;
}

export function AggregateStats({ stats }: Props) {
  return (
    <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
      <StatCard
        label="Deployed Capital"
        value={stats ? `₹${stats.total_deployed_capital.toLocaleString()}` : "—"}
      />
      <StatCard
        label="Total P&L"
        value={stats ? `${stats.aggregate_pnl >= 0 ? "+" : ""}₹${stats.aggregate_pnl.toFixed(2)}` : "—"}
      />
      <StatCard
        label="Active Deployments"
        value={stats?.active_deployments?.toString() ?? "—"}
      />
      <StatCard
        label="Today's Trades"
        value={stats?.todays_trades?.toString() ?? "—"}
      />
    </SimpleGrid>
  );
}
```

- [ ] **Step 2: Create LiveDeploymentCard component**

Create `frontend/components/live-trading/LiveDeploymentCard.tsx`:

```tsx
"use client";
import { Box, Text, HStack, VStack, useColorModeValue } from "@chakra-ui/react";
import { useRouter } from "next/navigation";
import { DeploymentBadge } from "@/components/shared/DeploymentBadge";
import type { Deployment } from "@/lib/api/types";
import type { PositionInfo } from "@/lib/api/types";

interface Props {
  deployment: Deployment;
  position?: PositionInfo;
}

export function LiveDeploymentCard({ deployment, position }: Props) {
  const router = useRouter();
  const bg = useColorModeValue("white", "gray.700");
  const borderColor = useColorModeValue("gray.200", "gray.600");
  const pnl = position?.total_realized_pnl ?? 0;

  return (
    <Box
      p={4}
      bg={bg}
      borderWidth="1px"
      borderColor={borderColor}
      borderRadius="md"
      cursor="pointer"
      _hover={{ shadow: "md" }}
      onClick={() => router.push(`/live-trading/${deployment.id}`)}
    >
      <VStack align="stretch" spacing={2}>
        <Text fontWeight="bold" fontSize="sm" noOfLines={1}>
          {deployment.strategy_name}
        </Text>
        <Text fontSize="xs" color="gray.500">{deployment.symbol}</Text>
        <HStack>
          <DeploymentBadge mode={deployment.mode} status={deployment.status} />
        </HStack>
        <Text
          fontSize="sm"
          fontWeight="semibold"
          color={pnl >= 0 ? "green.500" : "red.500"}
        >
          P&L: {pnl >= 0 ? "+" : ""}₹{pnl.toFixed(2)}
        </Text>
        <Text fontSize="xs" color="gray.500">
          {position?.open_orders_count ?? 0} open orders
        </Text>
      </VStack>
    </Box>
  );
}
```

- [ ] **Step 3: Create KillSwitchButton component**

Create `frontend/components/live-trading/KillSwitchButton.tsx`:

```tsx
"use client";
import { Button, useDisclosure } from "@chakra-ui/react";
import { ConfirmModal } from "@/components/shared/ConfirmModal";
import { apiClient } from "@/lib/api/client";

interface Props {
  onComplete?: () => void;
}

export function KillSwitchButton({ onComplete }: Props) {
  const { isOpen, onOpen, onClose } = useDisclosure();

  const handleConfirm = async () => {
    await apiClient.post("/api/v1/deployments/stop-all");
    onClose();
    onComplete?.();
  };

  return (
    <>
      <Button colorScheme="red" size="sm" onClick={onOpen}>
        Kill All
      </Button>
      <ConfirmModal
        isOpen={isOpen}
        onClose={onClose}
        onConfirm={handleConfirm}
        title="Stop All Deployments"
        message="This will stop ALL active deployments and cancel all open orders. Are you sure?"
      />
    </>
  );
}
```

- [ ] **Step 4: Create command center page**

Create `frontend/app/(dashboard)/live-trading/page.tsx`:

```tsx
"use client";
import { Box, Heading, HStack, SimpleGrid, Text, Table, Thead, Tbody, Tr, Th, Td, Badge } from "@chakra-ui/react";
import { useActiveDeployments, useAggregateStats, useRecentTrades, useDeploymentPosition } from "@/lib/hooks/useApi";
import { AggregateStats } from "@/components/live-trading/AggregateStats";
import { LiveDeploymentCard } from "@/components/live-trading/LiveDeploymentCard";
import { KillSwitchButton } from "@/components/live-trading/KillSwitchButton";
import { EmptyState } from "@/components/shared/EmptyState";
import type { Deployment } from "@/lib/api/types";

function DeploymentCardWithPosition({ deployment }: { deployment: Deployment }) {
  const { data: position } = useDeploymentPosition(deployment.id);
  return <LiveDeploymentCard deployment={deployment} position={position ?? undefined} />;
}

export default function LiveTradingPage() {
  const { data: deployments, mutate: refreshDeployments } = useActiveDeployments();
  const { data: stats, mutate: refreshStats } = useAggregateStats();
  const { data: recentTrades } = useRecentTrades(20);

  const handleKillComplete = () => {
    refreshDeployments();
    refreshStats();
  };

  return (
    <Box p={6}>
      <HStack justify="space-between" mb={6}>
        <Heading size="lg">Live Trading</Heading>
        <KillSwitchButton onComplete={handleKillComplete} />
      </HStack>

      <AggregateStats stats={stats ?? undefined} />

      <Heading size="md" mt={8} mb={4}>Active Deployments</Heading>
      {!deployments || deployments.length === 0 ? (
        <EmptyState message="No active deployments" />
      ) : (
        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
          {deployments.map((dep) => (
            <DeploymentCardWithPosition key={dep.id} deployment={dep} />
          ))}
        </SimpleGrid>
      )}

      <Heading size="md" mt={8} mb={4}>Recent Trades</Heading>
      {!recentTrades || recentTrades.trades.length === 0 ? (
        <EmptyState message="No trades yet" />
      ) : (
        <Box overflowX="auto">
          <Table size="sm">
            <Thead>
              <Tr>
                <Th>Time</Th>
                <Th>Strategy</Th>
                <Th>Symbol</Th>
                <Th>Action</Th>
                <Th isNumeric>Qty</Th>
                <Th isNumeric>Price</Th>
                <Th isNumeric>P&L</Th>
              </Tr>
            </Thead>
            <Tbody>
              {recentTrades.trades.map((trade) => (
                <Tr key={trade.id}>
                  <Td fontSize="xs">{new Date(trade.created_at).toLocaleTimeString()}</Td>
                  <Td fontSize="xs">{trade.strategy_name}</Td>
                  <Td fontSize="xs">{trade.symbol}</Td>
                  <Td>
                    <Badge colorScheme={trade.action === "BUY" ? "green" : "red"} size="sm">
                      {trade.action}
                    </Badge>
                  </Td>
                  <Td isNumeric fontSize="xs">{trade.quantity}</Td>
                  <Td isNumeric fontSize="xs">{trade.fill_price?.toFixed(2) ?? "—"}</Td>
                  <Td isNumeric fontSize="xs" color={
                    trade.realized_pnl == null ? "gray.500" :
                    trade.realized_pnl >= 0 ? "green.500" : "red.500"
                  }>
                    {trade.realized_pnl != null ? `${trade.realized_pnl >= 0 ? "+" : ""}${trade.realized_pnl.toFixed(2)}` : "—"}
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </Box>
      )}
    </Box>
  );
}
```

- [ ] **Step 5: Verify TypeScript compilation**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add frontend/components/live-trading/ frontend/app/\(dashboard\)/live-trading/
git commit -m "feat: add live trading command center page and components"
```

---

## Task 13: Frontend Detail Page Components and Page

**Files:**
- Create: `frontend/components/live-trading/PositionCard.tsx`
- Create: `frontend/components/live-trading/PendingOrdersList.tsx`
- Create: `frontend/components/live-trading/TradeHistoryTable.tsx`
- Create: `frontend/components/live-trading/ManualOrderModal.tsx`
- Create: `frontend/components/live-trading/MetricsGrid.tsx`
- Create: `frontend/components/live-trading/ComparisonTable.tsx`
- Create: `frontend/app/(dashboard)/live-trading/[deploymentId]/page.tsx`

- [ ] **Step 1: Create PositionCard**

Create `frontend/components/live-trading/PositionCard.tsx`:

```tsx
"use client";
import { Box, Text, VStack, HStack, Button, useColorModeValue } from "@chakra-ui/react";
import type { PositionInfo } from "@/lib/api/types";

interface Props {
  position: PositionInfo | undefined;
  onClosePosition?: () => void;
}

export function PositionCard({ position, onClosePosition }: Props) {
  const bg = useColorModeValue("white", "gray.700");
  const pos = position?.position;

  return (
    <Box p={4} bg={bg} borderWidth="1px" borderRadius="md">
      <Text fontWeight="bold" mb={2}>Position</Text>
      {!pos ? (
        <Text color="gray.500" fontSize="sm">No open position</Text>
      ) : (
        <VStack align="stretch" spacing={1}>
          <HStack justify="space-between">
            <Text fontSize="sm">Quantity</Text>
            <Text fontSize="sm" fontWeight="semibold">{pos.quantity}</Text>
          </HStack>
          <HStack justify="space-between">
            <Text fontSize="sm">Avg Entry</Text>
            <Text fontSize="sm">₹{pos.avg_entry_price.toFixed(2)}</Text>
          </HStack>
          <HStack justify="space-between">
            <Text fontSize="sm">Unrealized P&L</Text>
            <Text fontSize="sm" color={pos.unrealized_pnl >= 0 ? "green.500" : "red.500"}>
              {pos.unrealized_pnl >= 0 ? "+" : ""}₹{pos.unrealized_pnl.toFixed(2)}
            </Text>
          </HStack>
          {onClosePosition && (
            <Button size="xs" colorScheme="orange" mt={2} onClick={onClosePosition}>
              Close Position
            </Button>
          )}
        </VStack>
      )}
      {position && (
        <Text fontSize="xs" color="gray.500" mt={2}>
          Realized P&L: ₹{position.total_realized_pnl.toFixed(2)}
        </Text>
      )}
    </Box>
  );
}
```

- [ ] **Step 2: Create PendingOrdersList**

Create `frontend/components/live-trading/PendingOrdersList.tsx`:

```tsx
"use client";
import { Box, Text, VStack, HStack, IconButton, Button, Badge, useDisclosure } from "@chakra-ui/react";
import { MdClose } from "react-icons/md";
import { apiClient } from "@/lib/api/client";

interface PendingOrder {
  id: string;
  action: string;
  quantity: number;
  order_type?: string;
  price?: number;
}

interface Props {
  deploymentId: string;
  orders: PendingOrder[];
  onOrderCancelled?: () => void;
  onPlaceOrder?: () => void;
}

export function PendingOrdersList({ deploymentId, orders, onOrderCancelled, onPlaceOrder }: Props) {
  const handleCancel = async (orderId: string) => {
    await apiClient.post(`/api/v1/deployments/${deploymentId}/cancel-order`, { order_id: orderId });
    onOrderCancelled?.();
  };

  return (
    <Box p={4} borderWidth="1px" borderRadius="md">
      <HStack justify="space-between" mb={2}>
        <Text fontWeight="bold">Pending Orders</Text>
        <Button size="xs" colorScheme="blue" onClick={onPlaceOrder}>Place Order</Button>
      </HStack>
      {orders.length === 0 ? (
        <Text color="gray.500" fontSize="sm">No pending orders</Text>
      ) : (
        <VStack align="stretch" spacing={1}>
          {orders.map((order) => (
            <HStack key={order.id} justify="space-between" fontSize="xs">
              <HStack>
                <Badge colorScheme={order.action === "buy" ? "green" : "red"} size="sm">
                  {order.action.toUpperCase()}
                </Badge>
                <Text>{order.quantity} @ {order.price ?? "MKT"}</Text>
              </HStack>
              <IconButton
                aria-label="Cancel order"
                icon={<MdClose />}
                size="xs"
                variant="ghost"
                colorScheme="red"
                onClick={() => handleCancel(order.id)}
              />
            </HStack>
          ))}
        </VStack>
      )}
    </Box>
  );
}
```

- [ ] **Step 3: Create TradeHistoryTable**

Create `frontend/components/live-trading/TradeHistoryTable.tsx`:

```tsx
"use client";
import { Box, Table, Thead, Tbody, Tr, Th, Td, Badge, HStack, Button, Text } from "@chakra-ui/react";
import { useState } from "react";
import { useDeploymentTrades } from "@/lib/hooks/useApi";

const PAGE_SIZE = 20;

interface Props {
  deploymentId: string;
}

export function TradeHistoryTable({ deploymentId }: Props) {
  const [offset, setOffset] = useState(0);
  const { data } = useDeploymentTrades(deploymentId, offset, PAGE_SIZE);

  return (
    <Box>
      <Text fontWeight="bold" mb={2}>Trade History</Text>
      <Box overflowX="auto">
        <Table size="sm">
          <Thead>
            <Tr>
              <Th>Time</Th>
              <Th>Action</Th>
              <Th isNumeric>Qty</Th>
              <Th isNumeric>Price</Th>
              <Th isNumeric>P&L</Th>
              <Th>Status</Th>
            </Tr>
          </Thead>
          <Tbody>
            {data?.trades.map((t) => (
              <Tr key={t.id}>
                <Td fontSize="xs">{new Date(t.created_at).toLocaleTimeString()}</Td>
                <Td>
                  <HStack spacing={1}>
                    <Badge colorScheme={t.action === "BUY" ? "green" : "red"} size="sm">{t.action}</Badge>
                    {t.is_manual && <Badge colorScheme="purple" size="sm">Manual</Badge>}
                  </HStack>
                </Td>
                <Td isNumeric fontSize="xs">{t.quantity}</Td>
                <Td isNumeric fontSize="xs">{t.fill_price?.toFixed(2) ?? "—"}</Td>
                <Td isNumeric fontSize="xs" color={
                  t.realized_pnl == null ? "gray.500" :
                  t.realized_pnl >= 0 ? "green.500" : "red.500"
                }>
                  {t.realized_pnl != null ? t.realized_pnl.toFixed(2) : "—"}
                </Td>
                <Td><Badge size="sm">{t.status}</Badge></Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </Box>
      {data && data.total > PAGE_SIZE && (
        <HStack mt={2} justify="center">
          <Button size="xs" isDisabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
            Prev
          </Button>
          <Text fontSize="xs">{offset + 1}–{Math.min(offset + PAGE_SIZE, data.total)} of {data.total}</Text>
          <Button size="xs" isDisabled={offset + PAGE_SIZE >= data.total} onClick={() => setOffset(offset + PAGE_SIZE)}>
            Next
          </Button>
        </HStack>
      )}
    </Box>
  );
}
```

- [ ] **Step 4: Create ManualOrderModal**

Create `frontend/components/live-trading/ManualOrderModal.tsx`:

```tsx
"use client";
import {
  Modal, ModalOverlay, ModalContent, ModalHeader, ModalBody, ModalFooter, ModalCloseButton,
  Button, FormControl, FormLabel, Input, Select, HStack, useToast,
} from "@chakra-ui/react";
import { useState } from "react";
import { apiClient } from "@/lib/api/client";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  deploymentId: string;
  onOrderPlaced?: () => void;
}

export function ManualOrderModal({ isOpen, onClose, deploymentId, onOrderPlaced }: Props) {
  const [action, setAction] = useState("buy");
  const [quantity, setQuantity] = useState("");
  const [orderType, setOrderType] = useState("market");
  const [price, setPrice] = useState("");
  const [loading, setLoading] = useState(false);
  const toast = useToast();

  const handleSubmit = async () => {
    setLoading(true);
    try {
      await apiClient.post(`/api/v1/deployments/${deploymentId}/manual-order`, {
        action,
        quantity: parseFloat(quantity),
        order_type: orderType,
        price: price ? parseFloat(price) : null,
      });
      toast({ title: "Order placed", status: "success", duration: 2000 });
      onOrderPlaced?.();
      onClose();
    } catch {
      toast({ title: "Failed to place order", status: "error", duration: 3000 });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Place Manual Order</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <FormControl mb={3}>
            <FormLabel>Action</FormLabel>
            <Select value={action} onChange={(e) => setAction(e.target.value)}>
              <option value="buy">Buy</option>
              <option value="sell">Sell</option>
            </Select>
          </FormControl>
          <FormControl mb={3}>
            <FormLabel>Quantity</FormLabel>
            <Input type="number" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
          </FormControl>
          <FormControl mb={3}>
            <FormLabel>Order Type</FormLabel>
            <Select value={orderType} onChange={(e) => setOrderType(e.target.value)}>
              <option value="market">Market</option>
              <option value="limit">Limit</option>
            </Select>
          </FormControl>
          {orderType === "limit" && (
            <FormControl mb={3}>
              <FormLabel>Price</FormLabel>
              <Input type="number" value={price} onChange={(e) => setPrice(e.target.value)} />
            </FormControl>
          )}
        </ModalBody>
        <ModalFooter>
          <HStack>
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button colorScheme="blue" onClick={handleSubmit} isLoading={loading} isDisabled={!quantity}>
              Place Order
            </Button>
          </HStack>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
```

- [ ] **Step 5: Create MetricsGrid**

Create `frontend/components/live-trading/MetricsGrid.tsx`:

```tsx
"use client";
import { SimpleGrid } from "@chakra-ui/react";
import { StatCard } from "@/components/shared/StatCard";
import type { LiveMetrics } from "@/lib/api/types";

interface Props {
  metrics: LiveMetrics | undefined;
}

export function MetricsGrid({ metrics }: Props) {
  if (!metrics) return null;
  return (
    <SimpleGrid columns={{ base: 2, md: 4 }} spacing={3}>
      <StatCard label="Return" value={`${metrics.total_return.toFixed(2)}%`} />
      <StatCard label="Win Rate" value={`${metrics.win_rate.toFixed(1)}%`} />
      <StatCard label="Profit Factor" value={metrics.profit_factor.toFixed(2)} />
      <StatCard label="Sharpe" value={metrics.sharpe_ratio.toFixed(2)} />
      <StatCard label="Max Drawdown" value={`${metrics.max_drawdown.toFixed(2)}%`} />
      <StatCard label="Total Trades" value={metrics.total_trades.toString()} />
      <StatCard label="Best Trade" value={metrics.best_trade != null ? `₹${metrics.best_trade.toFixed(2)}` : "—"} />
      <StatCard label="Worst Trade" value={metrics.worst_trade != null ? `₹${metrics.worst_trade.toFixed(2)}` : "—"} />
    </SimpleGrid>
  );
}
```

- [ ] **Step 6: Create ComparisonTable**

Create `frontend/components/live-trading/ComparisonTable.tsx`:

```tsx
"use client";
import { Box, Table, Thead, Tbody, Tr, Th, Td, Text } from "@chakra-ui/react";
import type { ComparisonData } from "@/lib/api/types";

interface Props {
  comparison: ComparisonData | null | undefined;
}

const METRIC_LABELS: Record<string, string> = {
  total_return: "Return (%)",
  win_rate: "Win Rate (%)",
  profit_factor: "Profit Factor",
  sharpe_ratio: "Sharpe Ratio",
  max_drawdown: "Max Drawdown (%)",
  total_trades: "Total Trades",
  avg_trade_pnl: "Avg Trade P&L",
};

export function ComparisonTable({ comparison }: Props) {
  if (!comparison) return <Text color="gray.500" fontSize="sm">No backtest comparison available</Text>;

  return (
    <Box overflowX="auto">
      <Table size="sm">
        <Thead>
          <Tr>
            <Th>Metric</Th>
            <Th isNumeric>Backtest</Th>
            <Th isNumeric>Live</Th>
            <Th isNumeric>Delta</Th>
          </Tr>
        </Thead>
        <Tbody>
          {Object.entries(METRIC_LABELS).map(([key, label]) => {
            const bt = (comparison.backtest as Record<string, number>)[key] ?? 0;
            const live = (comparison.current as Record<string, number>)[key] ?? 0;
            const delta = comparison.deltas[key] ?? 0;
            return (
              <Tr key={key}>
                <Td fontSize="xs">{label}</Td>
                <Td isNumeric fontSize="xs">{typeof bt === "number" ? bt.toFixed(2) : bt}</Td>
                <Td isNumeric fontSize="xs">{typeof live === "number" ? live.toFixed(2) : live}</Td>
                <Td isNumeric fontSize="xs" color={delta >= 0 ? "green.500" : "red.500"}>
                  {delta >= 0 ? "+" : ""}{delta.toFixed(2)}
                </Td>
              </Tr>
            );
          })}
        </Tbody>
      </Table>
    </Box>
  );
}
```

- [ ] **Step 7: Create deployment detail page**

Create `frontend/app/(dashboard)/live-trading/[deploymentId]/page.tsx`:

```tsx
"use client";
import {
  Box, Heading, HStack, Grid, GridItem, Tabs, TabList, Tab, TabPanels, TabPanel, Button, useDisclosure,
} from "@chakra-ui/react";
import { useParams, useRouter } from "next/navigation";
import { useDeployment, useDeploymentPosition, useDeploymentMetrics, useDeploymentComparison, useDeploymentLogs } from "@/lib/hooks/useApi";
import { DeploymentBadge } from "@/components/shared/DeploymentBadge";
import { LogViewer } from "@/components/shared/LogViewer";
import { PositionCard } from "@/components/live-trading/PositionCard";
import { PendingOrdersList } from "@/components/live-trading/PendingOrdersList";
import { TradeHistoryTable } from "@/components/live-trading/TradeHistoryTable";
import { ManualOrderModal } from "@/components/live-trading/ManualOrderModal";
import { MetricsGrid } from "@/components/live-trading/MetricsGrid";
import { ComparisonTable } from "@/components/live-trading/ComparisonTable";
import { KillSwitchButton } from "@/components/live-trading/KillSwitchButton";
import { apiClient } from "@/lib/api/client";

export default function DeploymentDetailPage() {
  const { deploymentId } = useParams<{ deploymentId: string }>();
  const router = useRouter();
  const { data: deployment, mutate: refreshDeployment } = useDeployment(deploymentId);
  const { data: position, mutate: refreshPosition } = useDeploymentPosition(deploymentId);
  const { data: metrics } = useDeploymentMetrics(deploymentId);
  const { data: comparison } = useDeploymentComparison(deploymentId);
  const orderModal = useDisclosure();

  if (!deployment) return <Box p={6}>Loading...</Box>;

  const canPause = deployment.status === "running";
  const canResume = deployment.status === "paused";
  const canStop = deployment.status === "running" || deployment.status === "paused";

  const handleAction = async (action: string) => {
    await apiClient.post(`/api/v1/deployments/${deploymentId}/${action}`);
    refreshDeployment();
  };

  const handleClosePosition = async () => {
    if (!position?.position) return;
    const qty = Math.abs(position.position.quantity);
    const action = position.position.quantity > 0 ? "sell" : "buy";
    await apiClient.post(`/api/v1/deployments/${deploymentId}/manual-order`, {
      action, quantity: qty, order_type: "market",
    });
    refreshPosition();
  };

  const openOrders = position?.open_orders ?? [];

  return (
    <Box p={6}>
      <HStack justify="space-between" mb={4}>
        <HStack spacing={3}>
          <Heading size="md">{deployment.strategy_name}</Heading>
          <DeploymentBadge mode={deployment.mode} status={deployment.status} />
        </HStack>
        <HStack>
          {canPause && <Button size="sm" onClick={() => handleAction("pause")}>Pause</Button>}
          {canResume && <Button size="sm" colorScheme="green" onClick={() => handleAction("resume")}>Resume</Button>}
          {canStop && <Button size="sm" colorScheme="orange" onClick={() => handleAction("stop")}>Stop</Button>}
        </HStack>
      </HStack>

      <Grid templateColumns={{ base: "1fr", md: "1fr 1fr" }} gap={6}>
        <GridItem>
          <PositionCard position={position ?? undefined} onClosePosition={handleClosePosition} />
          <Box mt={4}>
            <PendingOrdersList
              deploymentId={deploymentId}
              orders={[]}
              onPlaceOrder={orderModal.onOpen}
              onOrderCancelled={refreshPosition}
            />
          </Box>
          <Box mt={4}>
            <TradeHistoryTable deploymentId={deploymentId} />
          </Box>
        </GridItem>

        <GridItem>
          <Tabs size="sm" variant="enclosed">
            <TabList>
              <Tab>Analytics</Tab>
              <Tab>Compare</Tab>
              <Tab>Logs</Tab>
            </TabList>
            <TabPanels>
              <TabPanel>
                <MetricsGrid metrics={metrics ?? undefined} />
              </TabPanel>
              <TabPanel>
                <ComparisonTable comparison={comparison} />
              </TabPanel>
              <TabPanel>
                <LogViewer deploymentId={deploymentId} />
              </TabPanel>
            </TabPanels>
          </Tabs>
        </GridItem>
      </Grid>

      <ManualOrderModal
        isOpen={orderModal.isOpen}
        onClose={orderModal.onClose}
        deploymentId={deploymentId}
        onOrderPlaced={refreshPosition}
      />
    </Box>
  );
}
```

- [ ] **Step 8: Verify TypeScript compilation**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 9: Commit**

```bash
git add frontend/components/live-trading/ frontend/app/\(dashboard\)/live-trading/
git commit -m "feat: add live trading detail page with position, trades, metrics, and manual orders"
```

---

## Task 14: Sidebar Navigation Update

**Files:**
- Modify: `frontend/components/layout/Sidebar.tsx`

- [ ] **Step 1: Add MdTrendingUp import and nav item**

In `frontend/components/layout/Sidebar.tsx`:

1. Add `MdTrendingUp` to the react-icons import
2. Add nav item after "Hosted Strategies" and before "Webhooks":

```typescript
const NAV_ITEMS = [
  { icon: MdDashboard, label: "Dashboard", href: "/" },
  { icon: MdShowChart, label: "Webhook Strategies", href: "/strategies" },
  { icon: MdCode, label: "Hosted Strategies", href: "/strategies/hosted" },
  { icon: MdTrendingUp, label: "Live Trading", href: "/live-trading" },
  { icon: MdWebhook, label: "Webhooks", href: "/webhooks" },
  // ... rest unchanged
];
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/components/layout/Sidebar.tsx
git commit -m "feat: add Live Trading to sidebar navigation"
```

---

## Task 15: Integration Smoke Test

- [ ] **Step 1: Run full backend test suite**

Run: `.venv/bin/python -m pytest backend/tests/ -v`
Expected: All PASS

- [ ] **Step 2: Run frontend type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Verify all route registrations**

Check that `backend/app/main.py` already includes `deployment_router` (it does — line 63). No changes needed since all new endpoints are on the same router.

- [ ] **Step 4: Verify static routes are registered before parameterized routes**

In `backend/app/deployments/router.py`, verify that these endpoints are defined BEFORE any `/{deployment_id}/...` endpoint:
- `GET /api/v1/deployments/recent-trades`
- `GET /api/v1/deployments/aggregate-stats`
- `POST /api/v1/deployments/stop-all`

If not, reorder them. FastAPI matches routes top-down, so `/deployments/recent-trades` must come before `/deployments/{deployment_id}`.

- [ ] **Step 5: Final commit if any fixes**

```bash
git add -A
git commit -m "fix: integration fixes for live trading feature"
```
