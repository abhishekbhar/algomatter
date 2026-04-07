# Trading Terminal & Enhanced Manual Orders — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/trade` page with live charts, watchlist, and advanced order form for standalone manual crypto trading, plus upgrade the deployment manual order modal with TP/SL and sliders.

**Architecture:** New `/trade` page uses Binance public WebSocket for real-time price data and TradingView `lightweight-charts` for charting. Orders route through existing broker adapters. A new `ManualTrade` database table stores standalone trades separate from deployment trades. The existing `ManualOrderModal` on the deployment detail page gets TP/SL fields and percentage-based sliders.

**Tech Stack:** Next.js (React), Chakra UI, `lightweight-charts` (npm), Binance WebSocket API, FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL.

**Spec:** `docs/superpowers/specs/2026-04-06-trading-terminal-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `backend/app/manual_trades/__init__.py` | Package init |
| `backend/app/manual_trades/router.py` | POST/GET/cancel endpoints for standalone manual trades |
| `backend/app/manual_trades/schemas.py` | Pydantic request/response models |
| `backend/app/db/migrations/versions/xxxx_add_manual_trades.py` | Alembic migration |
| `frontend/app/(dashboard)/trade/page.tsx` | Trade page layout (3-column + bottom) |
| `frontend/components/trade/Watchlist.tsx` | Symbol list with live Binance prices |
| `frontend/components/trade/TradingChart.tsx` | TradingView lightweight-charts wrapper |
| `frontend/components/trade/OrderForm.tsx` | Full order form (spot/futures, sliders) |
| `frontend/components/trade/TradeHistory.tsx` | Open orders + trade history tabs |
| `frontend/components/trade/BrokerCapabilities.ts` | Hardcoded broker capability map |
| `frontend/lib/hooks/useBinanceWebSocket.ts` | WebSocket hook for ticker + kline streams |
| `frontend/lib/hooks/useManualTrades.ts` | SWR hooks for manual trade CRUD |
| `frontend/__tests__/components/trade/OrderForm.test.tsx` | Order form tests |
| `frontend/__tests__/components/trade/Watchlist.test.tsx` | Watchlist tests |
| `frontend/__tests__/components/trade/TradeHistory.test.tsx` | Trade history tests |
| `backend/tests/test_manual_trades.py` | Backend manual trades endpoint tests |

### Modified Files

| File | Change |
|------|--------|
| `backend/app/db/models.py` | Add `ManualTrade` model |
| `backend/app/main.py` | Register manual_trades router |
| `backend/app/brokers/router.py` | Add `GET /brokers/{id}/balance` endpoint |
| `backend/app/deployments/schemas.py` | Add `take_profit`, `stop_loss` to `ManualOrderRequest` |
| `backend/app/deployments/router.py` | Pass TP/SL through to broker, fix OrderResponse attribute access |
| `frontend/lib/api/types.ts` | Add `ManualTrade`, `BrokerBalance` types |
| `frontend/lib/hooks/useApi.ts` | Add `useBrokerBalance` hook |
| `frontend/components/layout/Sidebar.tsx` | Add "Trade" nav item |
| `frontend/components/live-trading/ManualOrderModal.tsx` | Add TP/SL, trigger price, sliders |

---

## Task 1: Backend — ManualTrade Model + Migration

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/app/db/migrations/versions/xxxx_add_manual_trades.py` (via autogenerate)

- [ ] **Step 1: Add ManualTrade model to models.py**

Add after the `DeploymentTrade` class (around line 425):

```python
class ManualTrade(Base):
    """Standalone manual trade — not tied to any deployment."""

    __tablename__ = "manual_trades"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    broker_connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("broker_connections.id"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    product_type: Mapped[str] = mapped_column(String(16), nullable=False)  # SPOT or FUTURES
    action: Mapped[str] = mapped_column(String(8), nullable=False)  # BUY or SELL
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)  # MARKET, LIMIT, SL, SL-M
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    trigger_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    leverage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position_model: Mapped[str | None] = mapped_column(String(16), nullable=True)  # isolated, cross
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    fill_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    fill_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="submitted")
    broker_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    broker_symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    filled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

Ensure these imports exist at the top of models.py: `Float`, `Integer`, `String` from `sqlalchemy`.

- [ ] **Step 2: Generate Alembic migration**

Run from `backend/`:
```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend
.venv/bin/alembic revision --autogenerate -m "add_manual_trades_table"
```

Expected: Creates a new migration file in `app/db/migrations/versions/`.

- [ ] **Step 3: Verify migration applies**

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend
.venv/bin/alembic upgrade head
```

Expected: Migration applies without errors, `manual_trades` table created.

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/models.py backend/app/db/migrations/versions/*add_manual_trades*
git commit -m "feat: add ManualTrade model and migration"
```

---

## Task 2: Backend — Manual Trades Schemas

**Files:**
- Create: `backend/app/manual_trades/__init__.py`
- Create: `backend/app/manual_trades/schemas.py`

- [ ] **Step 1: Create package init**

```python
# backend/app/manual_trades/__init__.py
```

(Empty file.)

- [ ] **Step 2: Create schemas**

```python
# backend/app/manual_trades/schemas.py
from pydantic import BaseModel


class PlaceManualTradeRequest(BaseModel):
    broker_connection_id: str
    symbol: str
    exchange: str
    product_type: str = "SPOT"  # SPOT or FUTURES
    action: str  # BUY or SELL
    quantity: float
    order_type: str = "MARKET"  # MARKET, LIMIT, SL, SL-M
    price: float | None = None
    trigger_price: float | None = None
    leverage: int | None = None
    position_model: str | None = None  # isolated, cross
    take_profit: float | None = None
    stop_loss: float | None = None


class ManualTradeResponse(BaseModel):
    id: str
    broker_connection_id: str
    symbol: str
    exchange: str
    product_type: str
    action: str
    quantity: float
    order_type: str
    price: float | None
    trigger_price: float | None
    leverage: int | None
    position_model: str | None
    take_profit: float | None
    stop_loss: float | None
    fill_price: float | None
    fill_quantity: float | None
    status: str
    broker_order_id: str | None
    created_at: str
    updated_at: str
    filled_at: str | None


class ManualTradesListResponse(BaseModel):
    trades: list[ManualTradeResponse]
    total: int
    offset: int
    limit: int
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/manual_trades/
git commit -m "feat: add manual trades Pydantic schemas"
```

---

## Task 3: Backend — Manual Trades Router

**Files:**
- Create: `backend/app/manual_trades/router.py`
- Modify: `backend/app/main.py` (register router)

- [ ] **Step 1: Create the router**

```python
# backend/app/manual_trades/router.py
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_tenant_session
from app.brokers.factory import get_broker
from app.brokers.base import OrderRequest
from app.crypto.encryption import decrypt_credentials
from app.db.models import BrokerConnection, ManualTrade
from app.manual_trades.schemas import (
    ManualTradeResponse,
    ManualTradesListResponse,
    PlaceManualTradeRequest,
)

router = APIRouter(prefix="/api/v1/trades", tags=["manual-trades"])


def _trade_to_response(t: ManualTrade) -> ManualTradeResponse:
    return ManualTradeResponse(
        id=str(t.id),
        broker_connection_id=str(t.broker_connection_id),
        symbol=t.symbol,
        exchange=t.exchange,
        product_type=t.product_type,
        action=t.action,
        quantity=t.quantity,
        order_type=t.order_type,
        price=t.price,
        trigger_price=t.trigger_price,
        leverage=t.leverage,
        position_model=t.position_model,
        take_profit=t.take_profit,
        stop_loss=t.stop_loss,
        fill_price=t.fill_price,
        fill_quantity=t.fill_quantity,
        status=t.status,
        broker_order_id=t.broker_order_id,
        created_at=t.created_at.isoformat() if t.created_at else "",
        updated_at=t.updated_at.isoformat() if t.updated_at else "",
        filled_at=t.filled_at.isoformat() if t.filled_at else None,
    )


@router.post(
    "/manual",
    response_model=ManualTradeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def place_manual_trade(
    body: PlaceManualTradeRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    broker_conn_id = uuid.UUID(body.broker_connection_id)

    # Validate broker connection belongs to tenant
    result = await session.execute(
        select(BrokerConnection).where(
            BrokerConnection.id == broker_conn_id,
            BrokerConnection.tenant_id == tenant_id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broker connection not found",
        )

    # Validate action
    action = body.action.upper()
    if action not in ("BUY", "SELL"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action must be BUY or SELL",
        )

    # Map order type
    order_type_map = {
        "market": "MARKET",
        "limit": "LIMIT",
        "stop": "SL-M",
        "stop_limit": "SL",
    }
    order_type = order_type_map.get(body.order_type.lower(), body.order_type.upper())

    # Create trade record
    trade = ManualTrade(
        tenant_id=tenant_id,
        broker_connection_id=broker_conn_id,
        symbol=body.symbol,
        exchange=body.exchange,
        product_type=body.product_type.upper(),
        action=action,
        quantity=body.quantity,
        order_type=order_type,
        price=body.price,
        trigger_price=body.trigger_price,
        leverage=body.leverage,
        position_model=body.position_model,
        take_profit=body.take_profit,
        stop_loss=body.stop_loss,
        status="submitted",
    )
    session.add(trade)

    # Build OrderRequest directly (not via translate_order — it drops TP/SL)
    order_req = OrderRequest(
        symbol=body.symbol,
        exchange=body.exchange,
        action=action,
        quantity=Decimal(str(body.quantity)),
        order_type=order_type,
        price=Decimal(str(body.price)) if body.price else Decimal("0"),
        product_type=body.product_type.upper()
        if body.product_type.upper() in ("FUTURES",)
        else "DELIVERY",
        trigger_price=Decimal(str(body.trigger_price)) if body.trigger_price else None,
        leverage=body.leverage,
        position_model=body.position_model,
        take_profit=Decimal(str(body.take_profit)) if body.take_profit else None,
        stop_loss=Decimal(str(body.stop_loss)) if body.stop_loss else None,
    )

    try:
        creds = decrypt_credentials(conn.tenant_id, conn.credentials)
        broker = await get_broker(conn.broker_type, creds)
        try:
            broker_result = await broker.place_order(order_req)

            # Use attribute access (OrderResponse is a Pydantic model, not a dict)
            trade.broker_order_id = broker_result.order_id
            trade.broker_symbol = body.symbol

            if broker_result.status == "filled":
                trade.status = "filled"
                trade.fill_price = (
                    float(broker_result.fill_price)
                    if broker_result.fill_price
                    else None
                )
                trade.fill_quantity = (
                    float(broker_result.fill_quantity)
                    if broker_result.fill_quantity
                    else None
                )
                trade.filled_at = datetime.now(UTC)
            elif broker_result.status == "open":
                trade.status = "open"
            elif broker_result.status == "rejected":
                trade.status = "rejected"
            else:
                trade.status = broker_result.status
        finally:
            await broker.close()
    except Exception as exc:
        trade.status = "failed"
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Broker error: {exc}",
        )

    await session.commit()
    await session.refresh(trade)
    return _trade_to_response(trade)


@router.get("/manual", response_model=ManualTradesListResponse)
async def list_manual_trades(
    offset: int = 0,
    limit: int = 50,
    symbol: str | None = None,
    status_filter: str | None = None,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])

    query = select(ManualTrade).where(ManualTrade.tenant_id == tenant_id)
    count_query = select(func.count(ManualTrade.id)).where(
        ManualTrade.tenant_id == tenant_id
    )

    if symbol:
        query = query.where(ManualTrade.symbol == symbol)
        count_query = count_query.where(ManualTrade.symbol == symbol)
    if status_filter:
        query = query.where(ManualTrade.status == status_filter)
        count_query = count_query.where(ManualTrade.status == status_filter)

    total = (await session.execute(count_query)).scalar() or 0
    result = await session.execute(
        query.order_by(ManualTrade.created_at.desc()).offset(offset).limit(limit)
    )
    trades = result.scalars().all()

    return ManualTradesListResponse(
        trades=[_trade_to_response(t) for t in trades],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.post("/manual/{trade_id}/cancel")
async def cancel_manual_trade(
    trade_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])

    result = await session.execute(
        select(ManualTrade).where(
            ManualTrade.id == trade_id,
            ManualTrade.tenant_id == tenant_id,
        )
    )
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found")
    if trade.status not in ("submitted", "open"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel trade with status '{trade.status}'",
        )

    if trade.broker_order_id:
        # Get broker connection to cancel on exchange
        conn_result = await session.execute(
            select(BrokerConnection).where(
                BrokerConnection.id == trade.broker_connection_id
            )
        )
        conn = conn_result.scalar_one_or_none()
        if conn:
            try:
                creds = decrypt_credentials(conn.tenant_id, conn.credentials)
                broker = await get_broker(conn.broker_type, creds)
                try:
                    # Binance Testnet needs symbol in _order_symbols map
                    # since broker instances are ephemeral (created per-request)
                    if trade.broker_symbol and hasattr(broker, "_order_symbols"):
                        broker._order_symbols[trade.broker_order_id] = trade.broker_symbol
                    await broker.cancel_order(trade.broker_order_id)
                finally:
                    await broker.close()
            except Exception:
                pass  # Best-effort cancel on exchange

    trade.status = "cancelled"
    await session.commit()
    return {"status": "cancelled"}
```

- [ ] **Step 2: Register router in main.py**

In `backend/app/main.py`, add after existing router includes:

```python
from app.manual_trades.router import router as manual_trades_router
app.include_router(manual_trades_router)
```

- [ ] **Step 3: Verify server starts**

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Check: `curl http://localhost:8000/docs` — should show new `/api/v1/trades/manual` endpoints.

- [ ] **Step 4: Commit**

```bash
git add backend/app/manual_trades/ backend/app/main.py
git commit -m "feat: add manual trades API endpoints"
```

---

## Task 4: Backend — Broker Balance Endpoint

**Files:**
- Modify: `backend/app/brokers/router.py`
- Modify: `backend/app/brokers/schemas.py`

- [ ] **Step 1: Add BrokerBalanceResponse schema**

In `backend/app/brokers/schemas.py`, add:

```python
class BrokerBalanceResponse(BaseModel):
    available: float
    total: float
```

- [ ] **Step 2: Add balance endpoint to broker router**

In `backend/app/brokers/router.py`, add this endpoint:

```python
from app.brokers.schemas import BrokerBalanceResponse

@router.get(
    "/{broker_connection_id}/balance",
    response_model=BrokerBalanceResponse,
)
async def get_broker_balance(
    broker_connection_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(BrokerConnection).where(
            BrokerConnection.id == broker_connection_id,
            BrokerConnection.tenant_id == tenant_id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Broker connection not found")

    creds = decrypt_credentials(conn.tenant_id, conn.credentials)
    broker = await get_broker(conn.broker_type, creds)
    try:
        balance = await broker.get_balance()
        return BrokerBalanceResponse(
            available=float(balance.available),
            total=float(balance.total),
        )
    finally:
        await broker.close()
```

Ensure these imports exist in the router file: `decrypt_credentials` from `app.crypto.encryption`, `get_broker` from `app.brokers.factory`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/brokers/router.py backend/app/brokers/schemas.py
git commit -m "feat: add broker balance endpoint"
```

---

## Task 5: Backend — Extend Deployment Manual Order with TP/SL

**Files:**
- Modify: `backend/app/deployments/schemas.py`
- Modify: `backend/app/deployments/router.py`

- [ ] **Step 1: Add TP/SL to ManualOrderRequest schema**

In `backend/app/deployments/schemas.py`, update `ManualOrderRequest`:

```python
class ManualOrderRequest(BaseModel):
    action: str
    quantity: float
    order_type: str = "market"
    price: float | None = None
    trigger_price: float | None = None
    take_profit: float | None = None
    stop_loss: float | None = None
```

- [ ] **Step 2: Update the manual order endpoint in router.py**

In `backend/app/deployments/router.py`, in the `place_manual_order` function, find the section where it builds the order for live mode broker dispatch. Update it to:

1. Include `take_profit` and `stop_loss` in the `OrderRequest` construction (build directly instead of using `translate_order`).
2. Fix the `broker_result` access to use attribute access (`.fill_price`) instead of dict access (`.get("fill_price")`).

The live mode section should construct `OrderRequest` like:

```python
order_req = OrderRequest(
    symbol=dep.symbol,
    exchange=dep.exchange,
    action=trade.action,
    quantity=Decimal(str(body.quantity)),
    order_type=trade.order_type,
    price=Decimal(str(body.price)) if body.price else Decimal("0"),
    product_type=dep.product_type,
    trigger_price=Decimal(str(body.trigger_price)) if body.trigger_price else None,
    take_profit=Decimal(str(body.take_profit)) if body.take_profit else None,
    stop_loss=Decimal(str(body.stop_loss)) if body.stop_loss else None,
)
```

And the result handling should use:

```python
trade.broker_order_id = broker_result.order_id
if broker_result.fill_price is not None:
    trade.fill_price = float(broker_result.fill_price)
if broker_result.fill_quantity is not None:
    trade.fill_quantity = float(broker_result.fill_quantity)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/deployments/schemas.py backend/app/deployments/router.py
git commit -m "feat: add TP/SL to deployment manual order endpoint"
```

---

## Task 6: Backend — Tests

**Files:**
- Create: `backend/tests/test_manual_trades.py`

- [ ] **Step 1: Write endpoint tests**

```python
# backend/tests/test_manual_trades.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
def mock_auth():
    """Mock authentication to return a test user."""
    with patch("app.auth.deps.get_current_user") as mock:
        mock.return_value = {"user_id": "00000000-0000-0000-0000-000000000001", "email": "test@test.com"}
        yield mock


@pytest.fixture
def mock_session():
    """Mock tenant session."""
    session = AsyncMock()
    with patch("app.auth.deps.get_tenant_session") as mock:
        mock.return_value = session
        yield session


@pytest.mark.asyncio
async def test_list_manual_trades_empty(mock_auth, mock_session):
    """GET /api/v1/trades/manual returns empty list when no trades."""
    # Mock the count query
    count_result = MagicMock()
    count_result.scalar.return_value = 0
    # Mock the trades query
    trades_result = MagicMock()
    trades_result.scalars.return_value.all.return_value = []

    mock_session.execute = AsyncMock(side_effect=[count_result, trades_result])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/trades/manual",
            headers={"Authorization": "Bearer fake"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["trades"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_place_manual_trade_missing_broker(mock_auth, mock_session):
    """POST /api/v1/trades/manual returns 404 for unknown broker connection."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=result)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/trades/manual",
            json={
                "broker_connection_id": "00000000-0000-0000-0000-000000000099",
                "symbol": "BTCUSDT",
                "exchange": "BINANCE",
                "action": "BUY",
                "quantity": 0.01,
            },
            headers={"Authorization": "Bearer fake"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cancel_nonexistent_trade(mock_auth, mock_session):
    """POST /api/v1/trades/manual/{id}/cancel returns 404 for missing trade."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=result)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/trades/manual/00000000-0000-0000-0000-000000000001/cancel",
            headers={"Authorization": "Bearer fake"},
        )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests**

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend
.venv/bin/pytest tests/test_manual_trades.py -v
```

Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_manual_trades.py
git commit -m "test: add manual trades endpoint tests"
```

---

## Task 7: Frontend — Types + API Hooks

**Files:**
- Modify: `frontend/lib/api/types.ts`
- Create: `frontend/lib/hooks/useManualTrades.ts`
- Modify: `frontend/lib/hooks/useApi.ts`

- [ ] **Step 1: Add types**

In `frontend/lib/api/types.ts`, add at the end:

```typescript
export interface ManualTrade {
  id: string;
  broker_connection_id: string;
  symbol: string;
  exchange: string;
  product_type: string;
  action: string;
  quantity: number;
  order_type: string;
  price: number | null;
  trigger_price: number | null;
  leverage: number | null;
  position_model: string | null;
  take_profit: number | null;
  stop_loss: number | null;
  fill_price: number | null;
  fill_quantity: number | null;
  status: string;
  broker_order_id: string | null;
  created_at: string;
  updated_at: string;
  filled_at: string | null;
}

export interface ManualTradesListResponse {
  trades: ManualTrade[];
  total: number;
  offset: number;
  limit: number;
}

export interface BrokerBalance {
  available: number;
  total: number;
}
```

- [ ] **Step 2: Create useManualTrades hook**

```typescript
// frontend/lib/hooks/useManualTrades.ts
import useSWR from "swr";
import { apiClient } from "@/lib/api/client";
import type { ManualTradesListResponse } from "@/lib/api/types";

function fetcher<T>(path: string): Promise<T> {
  return apiClient<T>(path);
}

export function useManualTrades(
  offset = 0,
  limit = 50,
  statusFilter?: string,
) {
  const params = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
  });
  if (statusFilter) params.set("status_filter", statusFilter);

  return useSWR<ManualTradesListResponse>(
    `/api/v1/trades/manual?${params}`,
    fetcher,
    { refreshInterval: 3000 },
  );
}

export function useOpenManualTrades() {
  return useManualTrades(0, 100, "open");
}
```

- [ ] **Step 3: Add useBrokerBalance hook to useApi.ts**

In `frontend/lib/hooks/useApi.ts`, add:

```typescript
export function useBrokerBalance(brokerConnectionId: string | null) {
  return useApiGet<{ available: number; total: number }>(
    brokerConnectionId ? `/api/v1/brokers/${brokerConnectionId}/balance` : null,
    { refreshInterval: 10000 },
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/api/types.ts frontend/lib/hooks/useManualTrades.ts frontend/lib/hooks/useApi.ts
git commit -m "feat: add manual trades types and API hooks"
```

---

## Task 8: Frontend — Binance WebSocket Hook

**Files:**
- Create: `frontend/lib/hooks/useBinanceWebSocket.ts`

- [ ] **Step 1: Create the hook**

```typescript
// frontend/lib/hooks/useBinanceWebSocket.ts
"use client";
import { useEffect, useRef, useCallback, useState } from "react";

const BINANCE_WS_URL = "wss://stream.binance.com:9443/stream";
const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000, 30000];

export interface TickerData {
  symbol: string;
  price: number;
  change24h: number;
  volume: number;
}

export interface KlineData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  isClosed: boolean;
}

type TickerCallback = (data: TickerData) => void;
type KlineCallback = (data: KlineData) => void;

export function useBinanceTickerStream(
  symbols: string[],
  onTicker: TickerCallback,
) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempt = useRef(0);
  const callbackRef = useRef(onTicker);
  callbackRef.current = onTicker;
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (symbols.length === 0) return;

    let destroyed = false;

    function connect() {
      if (destroyed) return;

      const streams = symbols
        .map((s) => `${s.toLowerCase()}@miniTicker`)
        .join("/");
      const ws = new WebSocket(`${BINANCE_WS_URL}?streams=${streams}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        reconnectAttempt.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.data) {
            const d = msg.data;
            callbackRef.current({
              symbol: d.s,
              price: parseFloat(d.c),
              change24h: parseFloat(d.P),
              volume: parseFloat(d.v),
            });
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        setConnected(false);
        if (!destroyed) {
          const delay =
            RECONNECT_DELAYS[
              Math.min(reconnectAttempt.current, RECONNECT_DELAYS.length - 1)
            ];
          reconnectAttempt.current += 1;
          setTimeout(connect, delay);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      destroyed = true;
      wsRef.current?.close();
    };
  }, [symbols.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  return { connected };
}

export function useBinanceKlineStream(
  symbol: string | null,
  interval: string,
  onKline: KlineCallback,
) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempt = useRef(0);
  const callbackRef = useRef(onKline);
  callbackRef.current = onKline;

  useEffect(() => {
    if (!symbol) return;

    let destroyed = false;

    function connect() {
      if (destroyed) return;

      const stream = `${symbol.toLowerCase()}@kline_${interval}`;
      const ws = new WebSocket(`${BINANCE_WS_URL}?streams=${stream}`);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectAttempt.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.data?.k) {
            const k = msg.data.k;
            callbackRef.current({
              time: Math.floor(k.t / 1000),
              open: parseFloat(k.o),
              high: parseFloat(k.h),
              low: parseFloat(k.l),
              close: parseFloat(k.c),
              volume: parseFloat(k.v),
              isClosed: k.x,
            });
          }
        } catch {
          // ignore
        }
      };

      ws.onclose = () => {
        if (!destroyed) {
          const delay =
            RECONNECT_DELAYS[
              Math.min(reconnectAttempt.current, RECONNECT_DELAYS.length - 1)
            ];
          reconnectAttempt.current += 1;
          setTimeout(connect, delay);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      destroyed = true;
      wsRef.current?.close();
    };
  }, [symbol, interval]); // eslint-disable-line react-hooks/exhaustive-deps
}

/**
 * Fetch historical klines from Binance REST API.
 */
export async function fetchBinanceKlines(
  symbol: string,
  interval: string,
  limit = 500,
): Promise<KlineData[]> {
  const url = `https://api.binance.com/api/v3/klines?symbol=${symbol}&interval=${interval}&limit=${limit}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Binance API error: ${res.status}`);
  const data = await res.json();
  return data.map(
    (k: (string | number)[]) =>
      ({
        time: Math.floor(Number(k[0]) / 1000),
        open: parseFloat(k[1] as string),
        high: parseFloat(k[2] as string),
        low: parseFloat(k[3] as string),
        close: parseFloat(k[4] as string),
        volume: parseFloat(k[5] as string),
        isClosed: true,
      }) as KlineData,
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/hooks/useBinanceWebSocket.ts
git commit -m "feat: add Binance WebSocket hooks for ticker and kline streams"
```

---

## Task 9: Frontend — Broker Capabilities

**Files:**
- Create: `frontend/components/trade/BrokerCapabilities.ts`

- [ ] **Step 1: Create capabilities map**

```typescript
// frontend/components/trade/BrokerCapabilities.ts
export interface BrokerCaps {
  spot: boolean;
  futures: boolean;
  orderTypes: string[];
  shortFutures: boolean;
}

export const BROKER_CAPABILITIES: Record<string, BrokerCaps> = {
  exchange1: {
    spot: true,
    futures: true,
    orderTypes: ["MARKET", "LIMIT"],
    shortFutures: false,
  },
  binance_testnet: {
    spot: true,
    futures: false,
    orderTypes: ["MARKET", "LIMIT", "SL", "SL-M"],
    shortFutures: false,
  },
};

export function getBrokerCaps(brokerType: string): BrokerCaps {
  return (
    BROKER_CAPABILITIES[brokerType] ?? {
      spot: true,
      futures: false,
      orderTypes: ["MARKET", "LIMIT"],
      shortFutures: false,
    }
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/trade/BrokerCapabilities.ts
git commit -m "feat: add broker capabilities map"
```

---

## Task 10: Frontend — TradingChart Component

**Files:**
- Create: `frontend/components/trade/TradingChart.tsx`

- [ ] **Step 1: Install lightweight-charts**

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/frontend
npm install lightweight-charts
```

- [ ] **Step 2: Create the component**

```typescript
// frontend/components/trade/TradingChart.tsx
"use client";
import { useEffect, useRef, useCallback, useState } from "react";
import { Box, Flex, Button, Text, Spinner } from "@chakra-ui/react";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  ColorType,
} from "lightweight-charts";
import {
  useBinanceKlineStream,
  fetchBinanceKlines,
  type KlineData,
} from "@/lib/hooks/useBinanceWebSocket";

const INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d"];

interface Props {
  symbol: string;
  price?: number;
  change24h?: number;
}

export function TradingChart({ symbol, price, change24h }: Props) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const [interval, setInterval_] = useState("15m");
  const [loading, setLoading] = useState(true);

  // Create chart on mount
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0f1118" },
        textColor: "#888",
      },
      grid: {
        vertLines: { color: "#1c1f2e" },
        horzLines: { color: "#1c1f2e" },
      },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: "#2a2d3a" },
      timeScale: { borderColor: "#2a2d3a", timeVisible: true },
    });
    chartRef.current = chart;

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });
    candleSeriesRef.current = candleSeries;

    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "",
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });
    volumeSeriesRef.current = volumeSeries;

    const resizeObserver = new ResizeObserver(() => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      }
    });
    resizeObserver.observe(chartContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, []);

  // Load historical data on symbol/interval change
  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    fetchBinanceKlines(symbol, interval)
      .then((klines) => {
        if (cancelled) return;
        if (candleSeriesRef.current && volumeSeriesRef.current) {
          candleSeriesRef.current.setData(
            klines.map((k) => ({
              time: k.time as any,
              open: k.open,
              high: k.high,
              low: k.low,
              close: k.close,
            })),
          );
          volumeSeriesRef.current.setData(
            klines.map((k) => ({
              time: k.time as any,
              value: k.volume,
              color:
                k.close >= k.open
                  ? "rgba(34,197,94,0.25)"
                  : "rgba(239,68,68,0.25)",
            })),
          );
          chartRef.current?.timeScale().fitContent();
        }
        setLoading(false);
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [symbol, interval]);

  // Real-time kline updates
  const handleKline = useCallback(
    (kline: KlineData) => {
      if (!candleSeriesRef.current || !volumeSeriesRef.current) return;
      candleSeriesRef.current.update({
        time: kline.time as any,
        open: kline.open,
        high: kline.high,
        low: kline.low,
        close: kline.close,
      });
      volumeSeriesRef.current.update({
        time: kline.time as any,
        value: kline.volume,
        color:
          kline.close >= kline.open
            ? "rgba(34,197,94,0.25)"
            : "rgba(239,68,68,0.25)",
      });
    },
    [],
  );

  useBinanceKlineStream(symbol, interval, handleKline);

  return (
    <Box flex="1" display="flex" flexDirection="column" minH={0}>
      {/* Toolbar */}
      <Flex
        align="center"
        justify="space-between"
        px={3}
        py={2}
        bg="#151822"
        borderBottom="1px solid #2a2d3a"
      >
        <Flex align="center" gap={3}>
          <Text fontWeight="bold" fontSize="md">
            {symbol}
          </Text>
          {price != null && (
            <Text
              fontWeight="semibold"
              color={change24h != null && change24h >= 0 ? "green.400" : "red.400"}
            >
              {price.toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </Text>
          )}
          {change24h != null && (
            <Text
              fontSize="sm"
              color={change24h >= 0 ? "green.400" : "red.400"}
            >
              {change24h >= 0 ? "+" : ""}
              {change24h.toFixed(2)}%
            </Text>
          )}
        </Flex>
        <Flex gap={1}>
          {INTERVALS.map((iv) => (
            <Button
              key={iv}
              size="xs"
              variant={iv === interval ? "solid" : "ghost"}
              colorScheme={iv === interval ? "blue" : "gray"}
              onClick={() => setInterval_(iv)}
            >
              {iv}
            </Button>
          ))}
        </Flex>
      </Flex>

      {/* Chart */}
      <Box flex="1" position="relative" minH={0}>
        {loading && (
          <Flex
            position="absolute"
            inset={0}
            align="center"
            justify="center"
            zIndex={1}
          >
            <Spinner color="blue.400" />
          </Flex>
        )}
        <Box ref={chartContainerRef} w="100%" h="100%" />
      </Box>
    </Box>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/trade/TradingChart.tsx frontend/package.json frontend/package-lock.json
git commit -m "feat: add TradingChart component with lightweight-charts"
```

---

## Task 11: Frontend — Watchlist Component

**Files:**
- Create: `frontend/components/trade/Watchlist.tsx`
- Create: `frontend/__tests__/components/trade/Watchlist.test.tsx`

- [ ] **Step 1: Create the component**

```typescript
// frontend/components/trade/Watchlist.tsx
"use client";
import { useState, useCallback, useMemo, useRef } from "react";
import { Box, Input, Text, Flex, useColorModeValue } from "@chakra-ui/react";
import {
  useBinanceTickerStream,
  type TickerData,
} from "@/lib/hooks/useBinanceWebSocket";

const DEFAULT_SYMBOLS = [
  "BTCUSDT",
  "ETHUSDT",
  "SOLUSDT",
  "XRPUSDT",
  "BNBUSDT",
  "ADAUSDT",
  "DOGEUSDT",
];

interface Props {
  activeSymbol: string;
  onSymbolSelect: (symbol: string) => void;
}

export function Watchlist({ activeSymbol, onSymbolSelect }: Props) {
  const [search, setSearch] = useState("");
  const tickerMapRef = useRef<Record<string, TickerData>>({});
  const [, forceUpdate] = useState(0);

  const bg = useColorModeValue("white", "#151822");
  const activeBg = useColorModeValue("blue.50", "#1c2333");
  const borderColor = useColorModeValue("gray.200", "#2a2d3a");

  const handleTicker = useCallback((data: TickerData) => {
    tickerMapRef.current[data.symbol] = data;
    // Throttle UI updates to avoid excessive re-renders
    forceUpdate((n) => n + 1);
  }, []);

  const { connected } = useBinanceTickerStream(DEFAULT_SYMBOLS, handleTicker);

  const filtered = useMemo(() => {
    if (!search) return DEFAULT_SYMBOLS;
    const q = search.toUpperCase();
    return DEFAULT_SYMBOLS.filter((s) => s.includes(q));
  }, [search]);

  return (
    <Box
      w="180px"
      bg={bg}
      borderRight="1px"
      borderColor={borderColor}
      overflowY="auto"
      flexShrink={0}
    >
      <Box p={2} borderBottom="1px" borderColor={borderColor}>
        <Input
          size="sm"
          placeholder="Search symbol..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          bg={useColorModeValue("gray.50", "#1c1f2e")}
          border="none"
        />
        {!connected && (
          <Text fontSize="xs" color="red.400" mt={1}>
            Disconnected
          </Text>
        )}
      </Box>
      <Box>
        {filtered.map((symbol) => {
          const ticker = tickerMapRef.current[symbol];
          const isActive = symbol === activeSymbol;
          return (
            <Flex
              key={symbol}
              justify="space-between"
              px={2}
              py={2}
              cursor="pointer"
              bg={isActive ? activeBg : "transparent"}
              borderLeft={isActive ? "2px solid" : "2px solid transparent"}
              borderLeftColor={isActive ? "blue.500" : "transparent"}
              _hover={{ bg: activeBg }}
              onClick={() => onSymbolSelect(symbol)}
            >
              <Box>
                <Text fontSize="xs" fontWeight={isActive ? "bold" : "medium"}>
                  {symbol.replace("USDT", "")}
                </Text>
                <Text fontSize="2xs" color="gray.500">
                  {symbol}
                </Text>
              </Box>
              <Box textAlign="right">
                <Text fontSize="xs" fontWeight="semibold">
                  {ticker
                    ? ticker.price.toLocaleString(undefined, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: ticker.price < 1 ? 6 : 2,
                      })
                    : "—"}
                </Text>
                <Text
                  fontSize="2xs"
                  color={
                    ticker && ticker.change24h >= 0 ? "green.400" : "red.400"
                  }
                >
                  {ticker
                    ? `${ticker.change24h >= 0 ? "+" : ""}${ticker.change24h.toFixed(2)}%`
                    : ""}
                </Text>
              </Box>
            </Flex>
          );
        })}
      </Box>
    </Box>
  );
}
```

- [ ] **Step 2: Write test**

```typescript
// frontend/__tests__/components/trade/Watchlist.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";

// Mock the WebSocket hook
jest.mock("@/lib/hooks/useBinanceWebSocket", () => ({
  useBinanceTickerStream: () => ({ connected: true }),
}));

import { Watchlist } from "@/components/trade/Watchlist";

describe("Watchlist", () => {
  const onSelect = jest.fn();

  it("renders default symbols", () => {
    render(
      <ChakraProvider>
        <Watchlist activeSymbol="BTCUSDT" onSymbolSelect={onSelect} />
      </ChakraProvider>,
    );
    expect(screen.getByText("BTCUSDT")).toBeInTheDocument();
    expect(screen.getByText("ETHUSDT")).toBeInTheDocument();
  });

  it("filters symbols by search", () => {
    render(
      <ChakraProvider>
        <Watchlist activeSymbol="BTCUSDT" onSymbolSelect={onSelect} />
      </ChakraProvider>,
    );
    fireEvent.change(screen.getByPlaceholderText("Search symbol..."), {
      target: { value: "ETH" },
    });
    expect(screen.getByText("ETHUSDT")).toBeInTheDocument();
    expect(screen.queryByText("BTCUSDT")).not.toBeInTheDocument();
  });

  it("calls onSymbolSelect when symbol clicked", () => {
    render(
      <ChakraProvider>
        <Watchlist activeSymbol="BTCUSDT" onSymbolSelect={onSelect} />
      </ChakraProvider>,
    );
    fireEvent.click(screen.getByText("ETHUSDT"));
    expect(onSelect).toHaveBeenCalledWith("ETHUSDT");
  });
});
```

- [ ] **Step 3: Run tests**

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/frontend
PATH="/nix/store/p7rrmmg1avg6zd0mbyvki32lg3r80gxq-nodejs-20.20.1/bin:$PATH" npx jest __tests__/components/trade/Watchlist.test.tsx --no-coverage
```

Expected: All 3 tests pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/trade/Watchlist.tsx frontend/__tests__/components/trade/Watchlist.test.tsx
git commit -m "feat: add Watchlist component with live Binance prices"
```

---

## Task 12: Frontend — OrderForm Component

**Files:**
- Create: `frontend/components/trade/OrderForm.tsx`
- Create: `frontend/__tests__/components/trade/OrderForm.test.tsx`

- [ ] **Step 1: Create the component**

```typescript
// frontend/components/trade/OrderForm.tsx
"use client";
import { useState, useMemo } from "react";
import {
  Box,
  Button,
  Flex,
  FormControl,
  FormLabel,
  Input,
  Select,
  Slider,
  SliderTrack,
  SliderFilledTrack,
  SliderThumb,
  Text,
  useColorModeValue,
  useToast,
} from "@chakra-ui/react";
import { apiClient } from "@/lib/api/client";
import { useBrokers } from "@/lib/hooks/useApi";
import { useBrokerBalance } from "@/lib/hooks/useApi";
import { getBrokerCaps } from "@/components/trade/BrokerCapabilities";

interface Props {
  symbol: string;
  currentPrice: number | null;
  onOrderPlaced?: () => void;
}

export function OrderForm({ symbol, currentPrice, onOrderPlaced }: Props) {
  const toast = useToast();
  const { data: brokerConnections } = useBrokers();

  // Form state
  const [selectedBrokerId, setSelectedBrokerId] = useState<string>("");
  const [productType, setProductType] = useState<"SPOT" | "FUTURES">("SPOT");
  const [action, setAction] = useState<"BUY" | "SELL">("BUY");
  const [orderType, setOrderType] = useState("MARKET");
  const [price, setPrice] = useState("");
  const [priceSliderPct, setPriceSliderPct] = useState(50); // 50% = current price
  const [quantityPct, setQuantityPct] = useState(0);
  const [quantity, setQuantity] = useState("");
  const [takeProfit, setTakeProfit] = useState("");
  const [stopLoss, setStopLoss] = useState("");
  const [triggerPrice, setTriggerPrice] = useState("");
  const [leverage, setLeverage] = useState(1);
  const [positionModel, setPositionModel] = useState("isolated");
  const [loading, setLoading] = useState(false);

  const { data: balance } = useBrokerBalance(selectedBrokerId || null);

  const selectedBroker = brokerConnections?.find(
    (b) => String(b.id) === selectedBrokerId,
  );
  const caps = selectedBroker
    ? getBrokerCaps(selectedBroker.broker_type)
    : null;

  const bg = useColorModeValue("white", "#151822");
  const inputBg = useColorModeValue("gray.50", "#1c1f2e");
  const borderColor = useColorModeValue("gray.200", "#2a2d3a");

  // Price slider: ±5% from current price
  const priceFromSlider = useMemo(() => {
    if (!currentPrice) return 0;
    const min = currentPrice * 0.95;
    const max = currentPrice * 1.05;
    return min + (max - min) * (priceSliderPct / 100);
  }, [currentPrice, priceSliderPct]);

  // Quantity from percentage of balance
  const computedQuantity = useMemo(() => {
    if (!balance || !currentPrice || quantityPct === 0) return 0;
    const available = balance.available;
    const effectivePrice = price ? parseFloat(price) : currentPrice;
    if (!effectivePrice) return 0;
    const maxQty = available / effectivePrice;
    return maxQty * (quantityPct / 100);
  }, [balance, currentPrice, quantityPct, price]);

  const handlePriceSliderChange = (val: number) => {
    setPriceSliderPct(val);
    if (currentPrice) {
      const min = currentPrice * 0.95;
      const max = currentPrice * 1.05;
      const p = min + (max - min) * (val / 100);
      setPrice(p.toFixed(2));
    }
  };

  const handleQuantityPctChange = (val: number) => {
    setQuantityPct(val);
    if (balance && currentPrice) {
      const effectivePrice = price ? parseFloat(price) : currentPrice;
      if (effectivePrice > 0) {
        const maxQty = balance.available / effectivePrice;
        setQuantity((maxQty * (val / 100)).toFixed(6));
      }
    }
  };

  const handleSubmit = async () => {
    if (!selectedBrokerId || !quantity) return;
    setLoading(true);
    try {
      const body: Record<string, unknown> = {
        broker_connection_id: selectedBrokerId,
        symbol,
        exchange: selectedBroker?.broker_type === "exchange1" ? "EXCHANGE1" : "BINANCE",
        product_type: productType,
        action: action,
        quantity: parseFloat(quantity),
        order_type: orderType.toLowerCase(),
        price: price ? parseFloat(price) : null,
        trigger_price: triggerPrice ? parseFloat(triggerPrice) : null,
        take_profit: takeProfit ? parseFloat(takeProfit) : null,
        stop_loss: stopLoss ? parseFloat(stopLoss) : null,
      };
      if (productType === "FUTURES") {
        body.leverage = leverage;
        body.position_model = positionModel;
      }
      await apiClient("/api/v1/trades/manual", {
        method: "POST",
        body,
      });
      toast({
        title: "Order placed",
        status: "success",
        duration: 2000,
      });
      onOrderPlaced?.();
      // Reset
      setQuantity("");
      setQuantityPct(0);
      setPrice("");
      setPriceSliderPct(50);
    } catch {
      toast({
        title: "Failed to place order",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading(false);
    }
  };

  const isFuturesDisabled = caps && !caps.futures;
  const isShortDisabled =
    productType === "FUTURES" && caps && !caps.shortFutures;
  const showTriggerPrice =
    orderType === "SL" || orderType === "SL-M";
  const isLimitLike = orderType === "LIMIT" || orderType === "SL";

  const actionLabel =
    productType === "FUTURES"
      ? action === "BUY"
        ? "Long"
        : "Short"
      : action;
  const submitLabel = `${actionLabel} ${symbol}${productType === "FUTURES" && leverage > 1 ? ` ${leverage}x` : ""}`;

  return (
    <Box
      w="280px"
      bg={bg}
      borderLeft="1px"
      borderColor={borderColor}
      overflowY="auto"
      flexShrink={0}
      p={3}
    >
      {/* Spot / Futures toggle */}
      <Flex bg={inputBg} borderRadius="md" p="2px" mb={3}>
        <Button
          flex={1}
          size="sm"
          variant={productType === "SPOT" ? "solid" : "ghost"}
          colorScheme={productType === "SPOT" ? "green" : "gray"}
          onClick={() => setProductType("SPOT")}
        >
          Spot
        </Button>
        <Button
          flex={1}
          size="sm"
          variant={productType === "FUTURES" ? "solid" : "ghost"}
          colorScheme={productType === "FUTURES" ? "yellow" : "gray"}
          onClick={() => setProductType("FUTURES")}
          isDisabled={!!isFuturesDisabled}
        >
          Futures
        </Button>
      </Flex>

      {/* Broker selector */}
      <FormControl mb={3}>
        <FormLabel fontSize="xs" color="gray.500" textTransform="uppercase">
          Broker
        </FormLabel>
        <Select
          size="sm"
          bg={inputBg}
          value={selectedBrokerId}
          onChange={(e) => setSelectedBrokerId(e.target.value)}
          placeholder="Select broker..."
        >
          {(brokerConnections ?? []).map((b) => (
            <option key={String(b.id)} value={String(b.id)}>
              {b.broker_type} — {String(b.id).slice(0, 8)}
            </option>
          ))}
        </Select>
      </FormControl>

      {/* Buy / Sell */}
      <Flex gap={2} mb={3}>
        <Button
          flex={1}
          size="sm"
          colorScheme={action === "BUY" ? "green" : "gray"}
          variant={action === "BUY" ? "solid" : "outline"}
          onClick={() => setAction("BUY")}
        >
          {productType === "FUTURES" ? "Long" : "Buy"}
        </Button>
        <Button
          flex={1}
          size="sm"
          colorScheme={action === "SELL" ? "red" : "gray"}
          variant={action === "SELL" ? "solid" : "outline"}
          onClick={() => setAction("SELL")}
          isDisabled={!!isShortDisabled}
        >
          {productType === "FUTURES" ? "Short" : "Sell"}
        </Button>
      </Flex>

      {/* Futures: Margin + Leverage */}
      {productType === "FUTURES" && (
        <Flex gap={2} mb={3}>
          <FormControl flex={1}>
            <FormLabel fontSize="xs" color="gray.500">
              MARGIN
            </FormLabel>
            <Flex gap={1}>
              <Button
                size="xs"
                variant={positionModel === "isolated" ? "solid" : "ghost"}
                colorScheme="yellow"
                onClick={() => setPositionModel("isolated")}
              >
                Isolated
              </Button>
              <Button
                size="xs"
                variant={positionModel === "cross" ? "solid" : "ghost"}
                colorScheme="yellow"
                onClick={() => setPositionModel("cross")}
              >
                Cross
              </Button>
            </Flex>
          </FormControl>
          <FormControl flex={1}>
            <FormLabel fontSize="xs" color="gray.500">
              LEVERAGE
            </FormLabel>
            <Select
              size="sm"
              bg={inputBg}
              value={leverage}
              onChange={(e) => setLeverage(Number(e.target.value))}
            >
              {[1, 2, 3, 5, 10, 20, 50, 75, 100, 125].map((l) => (
                <option key={l} value={l}>
                  {l}x
                </option>
              ))}
            </Select>
          </FormControl>
        </Flex>
      )}

      {/* Order type */}
      <FormControl mb={3}>
        <FormLabel fontSize="xs" color="gray.500" textTransform="uppercase">
          Order Type
        </FormLabel>
        <Flex gap={1} flexWrap="wrap">
          {["MARKET", "LIMIT", "SL-M", "SL"].map((ot) => {
            const disabled =
              caps && !caps.orderTypes.includes(ot);
            return (
              <Button
                key={ot}
                size="xs"
                variant={orderType === ot ? "solid" : "ghost"}
                colorScheme={orderType === ot ? "blue" : "gray"}
                onClick={() => setOrderType(ot)}
                isDisabled={!!disabled}
              >
                {ot === "SL-M" ? "Stop" : ot === "SL" ? "Stop Limit" : ot.charAt(0) + ot.slice(1).toLowerCase()}
              </Button>
            );
          })}
        </Flex>
      </FormControl>

      {/* Price */}
      {isLimitLike && (
        <FormControl mb={3}>
          <FormLabel fontSize="xs" color="gray.500">
            PRICE
          </FormLabel>
          <Input
            size="sm"
            type="number"
            bg={inputBg}
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            placeholder={currentPrice?.toFixed(2) ?? ""}
          />
          <Slider
            mt={1}
            min={0}
            max={100}
            value={priceSliderPct}
            onChange={handlePriceSliderChange}
            size="sm"
          >
            <SliderTrack>
              <SliderFilledTrack />
            </SliderTrack>
            <SliderThumb />
          </Slider>
          <Flex justify="space-between" fontSize="2xs" color="gray.500">
            <Text>-5%</Text>
            <Text>+5%</Text>
          </Flex>
        </FormControl>
      )}

      {/* Trigger price */}
      {showTriggerPrice && (
        <FormControl mb={3}>
          <FormLabel fontSize="xs" color="gray.500">
            TRIGGER PRICE
          </FormLabel>
          <Input
            size="sm"
            type="number"
            bg={inputBg}
            value={triggerPrice}
            onChange={(e) => setTriggerPrice(e.target.value)}
          />
        </FormControl>
      )}

      {/* Quantity */}
      <FormControl mb={3}>
        <FormLabel fontSize="xs" color="gray.500">
          QUANTITY
        </FormLabel>
        <Input
          size="sm"
          type="number"
          bg={inputBg}
          value={quantity}
          onChange={(e) => {
            setQuantity(e.target.value);
            setQuantityPct(0);
          }}
        />
        <Slider
          mt={1}
          min={0}
          max={100}
          step={1}
          value={quantityPct}
          onChange={handleQuantityPctChange}
          size="sm"
        >
          <SliderTrack>
            <SliderFilledTrack />
          </SliderTrack>
          <SliderThumb />
        </Slider>
        <Flex justify="space-between" fontSize="2xs" color="gray.500">
          <Text>0%</Text>
          <Text>25%</Text>
          <Text>50%</Text>
          <Text>75%</Text>
          <Text>100%</Text>
        </Flex>
      </FormControl>

      {/* TP / SL */}
      <Flex gap={2} mb={3}>
        <FormControl flex={1}>
          <FormLabel fontSize="xs" color="gray.500">
            TAKE PROFIT
          </FormLabel>
          <Input
            size="sm"
            type="number"
            bg={inputBg}
            placeholder="Optional"
            value={takeProfit}
            onChange={(e) => setTakeProfit(e.target.value)}
          />
        </FormControl>
        <FormControl flex={1}>
          <FormLabel fontSize="xs" color="gray.500">
            STOP LOSS
          </FormLabel>
          <Input
            size="sm"
            type="number"
            bg={inputBg}
            placeholder="Optional"
            value={stopLoss}
            onChange={(e) => setStopLoss(e.target.value)}
          />
        </FormControl>
      </Flex>

      {/* Total / Margin info */}
      {productType === "FUTURES" && currentPrice && quantity ? (
        <Box
          borderTop="1px"
          borderColor={borderColor}
          py={2}
          mb={2}
          fontSize="xs"
        >
          <Flex justify="space-between">
            <Text color="gray.500">Required Margin</Text>
            <Text color="yellow.400">
              {(
                (parseFloat(quantity) *
                  (parseFloat(price) || currentPrice)) /
                leverage
              ).toFixed(2)}{" "}
              USDT
            </Text>
          </Flex>
        </Box>
      ) : null}

      {currentPrice && quantity ? (
        <Flex
          justify="space-between"
          borderTop="1px"
          borderColor={borderColor}
          py={2}
          mb={3}
          fontSize="xs"
        >
          <Text color="gray.500">Total</Text>
          <Text fontWeight="semibold">
            {(
              parseFloat(quantity) *
              (parseFloat(price) || currentPrice)
            ).toFixed(2)}{" "}
            USDT
          </Text>
        </Flex>
      ) : null}

      {/* Submit */}
      <Button
        w="100%"
        colorScheme={action === "BUY" ? "green" : "red"}
        onClick={handleSubmit}
        isLoading={loading}
        isDisabled={!selectedBrokerId || !quantity}
      >
        {submitLabel}
      </Button>

      {/* Available balance */}
      {balance && (
        <Text textAlign="center" mt={2} fontSize="xs" color="gray.500">
          Available: {balance.available.toLocaleString()} USDT
        </Text>
      )}
    </Box>
  );
}
```

- [ ] **Step 2: Write test**

```typescript
// frontend/__tests__/components/trade/OrderForm.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import * as useApiModule from "@/lib/hooks/useApi";

jest.mock("@/lib/hooks/useApi");
jest.mock("@/lib/api/client", () => ({ apiClient: jest.fn() }));

import { OrderForm } from "@/components/trade/OrderForm";

describe("OrderForm", () => {
  beforeEach(() => {
    (useApiModule.useBrokers as jest.Mock).mockReturnValue({
      data: [{ id: "b1", broker_type: "exchange1" }],
    });
    (useApiModule.useBrokerBalance as jest.Mock).mockReturnValue({
      data: { available: 10000, total: 10000 },
    });
  });

  it("renders spot/futures toggle", () => {
    render(
      <ChakraProvider>
        <OrderForm symbol="BTCUSDT" currentPrice={83000} />
      </ChakraProvider>,
    );
    expect(screen.getByText("Spot")).toBeInTheDocument();
    expect(screen.getByText("Futures")).toBeInTheDocument();
  });

  it("renders buy/sell buttons", () => {
    render(
      <ChakraProvider>
        <OrderForm symbol="BTCUSDT" currentPrice={83000} />
      </ChakraProvider>,
    );
    expect(screen.getByText("Buy")).toBeInTheDocument();
    expect(screen.getByText("Sell")).toBeInTheDocument();
  });

  it("shows broker selector", () => {
    render(
      <ChakraProvider>
        <OrderForm symbol="BTCUSDT" currentPrice={83000} />
      </ChakraProvider>,
    );
    expect(screen.getByText(/Select broker/)).toBeInTheDocument();
  });

  it("disables submit when no broker selected", () => {
    render(
      <ChakraProvider>
        <OrderForm symbol="BTCUSDT" currentPrice={83000} />
      </ChakraProvider>,
    );
    const submitBtn = screen.getByRole("button", { name: /Buy BTCUSDT/i });
    expect(submitBtn).toBeDisabled();
  });
});
```

- [ ] **Step 3: Run tests**

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/frontend
PATH="/nix/store/p7rrmmg1avg6zd0mbyvki32lg3r80gxq-nodejs-20.20.1/bin:$PATH" npx jest __tests__/components/trade/OrderForm.test.tsx --no-coverage
```

Expected: All 4 tests pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/trade/OrderForm.tsx frontend/__tests__/components/trade/OrderForm.test.tsx
git commit -m "feat: add OrderForm component with spot/futures, sliders, and broker selection"
```

---

## Task 13: Frontend — TradeHistory Component

**Files:**
- Create: `frontend/components/trade/TradeHistory.tsx`
- Create: `frontend/__tests__/components/trade/TradeHistory.test.tsx`

- [ ] **Step 1: Create the component**

```typescript
// frontend/components/trade/TradeHistory.tsx
"use client";
import { useState } from "react";
import {
  Box,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  Button,
  Flex,
  Text,
  useColorModeValue,
  useToast,
} from "@chakra-ui/react";
import { apiClient } from "@/lib/api/client";
import { useManualTrades, useOpenManualTrades } from "@/lib/hooks/useManualTrades";

interface Props {
  onTradeUpdate?: () => void;
}

export function TradeHistory({ onTradeUpdate }: Props) {
  const [tab, setTab] = useState<"open" | "history">("open");
  const { data: openData, mutate: refreshOpen } = useOpenManualTrades();
  const { data: historyData, mutate: refreshHistory } = useManualTrades(0, 50);
  const toast = useToast();
  const borderColor = useColorModeValue("gray.200", "#2a2d3a");
  const bg = useColorModeValue("white", "#151822");

  const handleCancel = async (tradeId: string) => {
    try {
      await apiClient(`/api/v1/trades/manual/${tradeId}/cancel`, {
        method: "POST",
      });
      toast({ title: "Order cancelled", status: "success", duration: 2000 });
      refreshOpen();
      refreshHistory();
      onTradeUpdate?.();
    } catch {
      toast({ title: "Failed to cancel", status: "error", duration: 3000 });
    }
  };

  const trades =
    tab === "open"
      ? openData?.trades ?? []
      : historyData?.trades ?? [];

  return (
    <Box borderTop="1px" borderColor={borderColor} bg={bg}>
      <Flex gap={4} px={3} py={2} borderBottom="1px" borderColor={borderColor}>
        <Text
          fontSize="sm"
          fontWeight={tab === "open" ? "bold" : "normal"}
          color={tab === "open" ? "blue.400" : "gray.500"}
          cursor="pointer"
          borderBottom={tab === "open" ? "2px solid" : "none"}
          borderColor="blue.400"
          pb={1}
          onClick={() => setTab("open")}
        >
          Open Orders ({openData?.trades?.length ?? 0})
        </Text>
        <Text
          fontSize="sm"
          fontWeight={tab === "history" ? "bold" : "normal"}
          color={tab === "history" ? "blue.400" : "gray.500"}
          cursor="pointer"
          borderBottom={tab === "history" ? "2px solid" : "none"}
          borderColor="blue.400"
          pb={1}
          onClick={() => setTab("history")}
        >
          Trade History
        </Text>
      </Flex>

      {trades.length === 0 ? (
        <Box py={4} textAlign="center">
          <Text color="gray.500" fontSize="sm">
            {tab === "open" ? "No open orders" : "No trade history"}
          </Text>
        </Box>
      ) : (
        <Box overflowX="auto" maxH="200px" overflowY="auto">
          <Table size="sm" variant="simple">
            <Thead>
              <Tr>
                <Th>Time</Th>
                <Th>Symbol</Th>
                <Th>Side</Th>
                <Th>Type</Th>
                <Th isNumeric>Price</Th>
                <Th isNumeric>Qty</Th>
                <Th>Status</Th>
                {tab === "open" && <Th>Action</Th>}
              </Tr>
            </Thead>
            <Tbody>
              {trades.map((t) => (
                <Tr key={t.id} fontSize="xs">
                  <Td color="gray.500">
                    {new Date(t.created_at).toLocaleTimeString()}
                  </Td>
                  <Td fontWeight="medium">{t.symbol}</Td>
                  <Td>
                    <Badge
                      colorScheme={t.action === "BUY" ? "green" : "red"}
                      size="sm"
                    >
                      {t.action}
                    </Badge>
                  </Td>
                  <Td>{t.order_type}</Td>
                  <Td isNumeric>
                    {t.fill_price
                      ? t.fill_price.toLocaleString()
                      : t.price
                        ? t.price.toLocaleString()
                        : "MKT"}
                  </Td>
                  <Td isNumeric>{t.fill_quantity ?? t.quantity}</Td>
                  <Td>
                    <Badge
                      colorScheme={
                        t.status === "filled"
                          ? "green"
                          : t.status === "open"
                            ? "blue"
                            : t.status === "cancelled"
                              ? "gray"
                              : "red"
                      }
                      size="sm"
                    >
                      {t.status}
                    </Badge>
                  </Td>
                  {tab === "open" && (
                    <Td>
                      <Button
                        size="xs"
                        colorScheme="red"
                        variant="ghost"
                        onClick={() => handleCancel(t.id)}
                      >
                        Cancel
                      </Button>
                    </Td>
                  )}
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

- [ ] **Step 2: Write test**

```typescript
// frontend/__tests__/components/trade/TradeHistory.test.tsx
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";

jest.mock("@/lib/hooks/useManualTrades", () => ({
  useManualTrades: jest.fn(),
  useOpenManualTrades: jest.fn(),
}));
jest.mock("@/lib/api/client", () => ({ apiClient: jest.fn() }));

import { TradeHistory } from "@/components/trade/TradeHistory";
import * as hooks from "@/lib/hooks/useManualTrades";

describe("TradeHistory", () => {
  it("renders empty state for open orders", () => {
    (hooks.useOpenManualTrades as jest.Mock).mockReturnValue({
      data: { trades: [], total: 0, offset: 0, limit: 100 },
      mutate: jest.fn(),
    });
    (hooks.useManualTrades as jest.Mock).mockReturnValue({
      data: { trades: [], total: 0, offset: 0, limit: 50 },
      mutate: jest.fn(),
    });
    render(
      <ChakraProvider>
        <TradeHistory />
      </ChakraProvider>,
    );
    expect(screen.getByText(/no open orders/i)).toBeInTheDocument();
  });

  it("renders trade row", () => {
    (hooks.useOpenManualTrades as jest.Mock).mockReturnValue({
      data: {
        trades: [
          {
            id: "t1",
            symbol: "BTCUSDT",
            action: "BUY",
            order_type: "LIMIT",
            price: 82000,
            quantity: 0.05,
            fill_price: null,
            fill_quantity: null,
            status: "open",
            created_at: "2026-04-06T10:00:00Z",
          },
        ],
        total: 1,
        offset: 0,
        limit: 100,
      },
      mutate: jest.fn(),
    });
    (hooks.useManualTrades as jest.Mock).mockReturnValue({
      data: { trades: [], total: 0, offset: 0, limit: 50 },
      mutate: jest.fn(),
    });
    render(
      <ChakraProvider>
        <TradeHistory />
      </ChakraProvider>,
    );
    expect(screen.getByText("BTCUSDT")).toBeInTheDocument();
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.getByText("Cancel")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run tests**

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/frontend
PATH="/nix/store/p7rrmmg1avg6zd0mbyvki32lg3r80gxq-nodejs-20.20.1/bin:$PATH" npx jest __tests__/components/trade/TradeHistory.test.tsx --no-coverage
```

Expected: All 2 tests pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/trade/TradeHistory.tsx frontend/__tests__/components/trade/TradeHistory.test.tsx
git commit -m "feat: add TradeHistory component with open orders and history tabs"
```

---

## Task 14: Frontend — /trade Page Layout

**Files:**
- Create: `frontend/app/(dashboard)/trade/page.tsx`

- [ ] **Step 1: Create the page**

```typescript
// frontend/app/(dashboard)/trade/page.tsx
"use client";
import { useState, useCallback } from "react";
import { Box, Flex } from "@chakra-ui/react";
import { Watchlist } from "@/components/trade/Watchlist";
import { TradingChart } from "@/components/trade/TradingChart";
import { OrderForm } from "@/components/trade/OrderForm";
import { TradeHistory } from "@/components/trade/TradeHistory";
import { type TickerData } from "@/lib/hooks/useBinanceWebSocket";

export default function TradePage() {
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [tickerMap, setTickerMap] = useState<Record<string, TickerData>>({});

  const currentTicker = tickerMap[symbol];

  const handleSymbolSelect = useCallback((s: string) => {
    setSymbol(s);
  }, []);

  // Called by Watchlist whenever any ticker updates
  const handleTickerUpdate = useCallback((data: TickerData) => {
    setTickerMap((prev) => ({ ...prev, [data.symbol]: data }));
  }, []);

  return (
    <Box h="calc(100vh - 64px)" display="flex" flexDirection="column">
      {/* Main 3-column layout */}
      <Flex flex="1" minH={0}>
        {/* Left: Watchlist */}
        <Watchlist
          activeSymbol={symbol}
          onSymbolSelect={handleSymbolSelect}
          onTickerUpdate={handleTickerUpdate}
        />

        {/* Center: Chart */}
        <TradingChart
          symbol={symbol}
          price={currentTicker?.price}
          change24h={currentTicker?.change24h}
        />

        {/* Right: Order Form */}
        <OrderForm
          symbol={symbol}
          currentPrice={currentTicker?.price ?? null}
        />
      </Flex>

      {/* Bottom: Trade History */}
      <TradeHistory />
    </Box>
  );
}
```

**Important:** The `Watchlist` component must accept and call the `onTickerUpdate` prop. Update the `Watchlist` Props interface to include:

```typescript
interface Props {
  activeSymbol: string;
  onSymbolSelect: (symbol: string) => void;
  onTickerUpdate?: (data: TickerData) => void;
}
```

And in the `handleTicker` callback inside Watchlist, also call `onTickerUpdate`:

```typescript
const handleTicker = useCallback((data: TickerData) => {
  tickerMapRef.current[data.symbol] = data;
  forceUpdate((n) => n + 1);
  onTickerUpdate?.(data);
}, [onTickerUpdate]);
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/\(dashboard\)/trade/page.tsx
git commit -m "feat: add /trade page with 3-column trading terminal layout"
```

---

## Task 15: Frontend — Sidebar Nav Item

**Files:**
- Modify: `frontend/components/layout/Sidebar.tsx`

- [ ] **Step 1: Add "Trade" to NAV_ITEMS**

In `frontend/components/layout/Sidebar.tsx`, add a new entry in the `NAV_ITEMS` array after the "Live Trading" entry (line 25). Import `MdSwapHoriz` from `react-icons/md` (or use `MdCandlestickChart` if available):

```typescript
{ icon: MdSwapHoriz, label: "Trade", href: "/trade" },
```

Place it right after:
```typescript
{ icon: MdTrendingUp, label: "Live Trading", href: "/live-trading" },
```

Add `MdSwapHoriz` to the existing `react-icons/md` import at the top.

- [ ] **Step 2: Verify nav renders**

Start the dev server and check that "Trade" appears in the sidebar between "Live Trading" and "Webhooks":

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/frontend
PATH="/nix/store/p7rrmmg1avg6zd0mbyvki32lg3r80gxq-nodejs-20.20.1/bin:$PATH" npm run dev
```

Navigate to `http://localhost:3000/app/trade` — should render the trading terminal.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/layout/Sidebar.tsx
git commit -m "feat: add Trade nav item to sidebar"
```

---

## Task 16: Frontend — Upgrade ManualOrderModal

**Files:**
- Modify: `frontend/components/live-trading/ManualOrderModal.tsx`

- [ ] **Step 1: Upgrade the modal**

Replace the entire content of `ManualOrderModal.tsx`:

```typescript
// frontend/components/live-trading/ManualOrderModal.tsx
"use client";
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  Button,
  FormControl,
  FormLabel,
  Input,
  Select,
  Slider,
  SliderTrack,
  SliderFilledTrack,
  SliderThumb,
  HStack,
  Flex,
  Text,
  useToast,
} from "@chakra-ui/react";
import { useState, useMemo } from "react";
import { apiClient } from "@/lib/api/client";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  deploymentId: string;
  onOrderPlaced?: () => void;
  currentPrice?: number | null;
  availableBalance?: number | null;
}

export function ManualOrderModal({
  isOpen,
  onClose,
  deploymentId,
  onOrderPlaced,
  currentPrice,
  availableBalance,
}: Props) {
  const [action, setAction] = useState("buy");
  const [quantity, setQuantity] = useState("");
  const [quantityPct, setQuantityPct] = useState(0);
  const [orderType, setOrderType] = useState("market");
  const [price, setPrice] = useState("");
  const [priceSliderPct, setPriceSliderPct] = useState(50);
  const [triggerPrice, setTriggerPrice] = useState("");
  const [takeProfit, setTakeProfit] = useState("");
  const [stopLoss, setStopLoss] = useState("");
  const [loading, setLoading] = useState(false);
  const toast = useToast();

  const isLimitLike = orderType === "limit" || orderType === "stop_limit";
  const showTriggerPrice = orderType === "stop" || orderType === "stop_limit";

  // Price from slider (±5% of current price)
  const handlePriceSliderChange = (val: number) => {
    setPriceSliderPct(val);
    if (currentPrice) {
      const min = currentPrice * 0.95;
      const max = currentPrice * 1.05;
      setPrice((min + (max - min) * (val / 100)).toFixed(2));
    }
  };

  // Quantity from % of balance
  const handleQuantityPctChange = (val: number) => {
    setQuantityPct(val);
    if (availableBalance && currentPrice) {
      const effectivePrice = price ? parseFloat(price) : currentPrice;
      if (effectivePrice > 0) {
        const maxQty = availableBalance / effectivePrice;
        setQuantity((maxQty * (val / 100)).toFixed(6));
      }
    }
  };

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const body: Record<string, unknown> = {
        action,
        quantity: parseFloat(quantity),
        order_type: orderType,
        price: price ? parseFloat(price) : null,
        trigger_price: triggerPrice ? parseFloat(triggerPrice) : null,
        take_profit: takeProfit ? parseFloat(takeProfit) : null,
        stop_loss: stopLoss ? parseFloat(stopLoss) : null,
      };
      await apiClient(`/api/v1/deployments/${deploymentId}/manual-order`, {
        method: "POST",
        body,
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
            <FormLabel>Order Type</FormLabel>
            <Select
              value={orderType}
              onChange={(e) => setOrderType(e.target.value)}
            >
              <option value="market">Market</option>
              <option value="limit">Limit</option>
              <option value="stop">Stop</option>
              <option value="stop_limit">Stop Limit</option>
            </Select>
          </FormControl>

          {isLimitLike && (
            <FormControl mb={3}>
              <FormLabel>Price</FormLabel>
              <Input
                type="number"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder={currentPrice?.toFixed(2)}
              />
              {currentPrice && (
                <>
                  <Slider
                    mt={1}
                    min={0}
                    max={100}
                    value={priceSliderPct}
                    onChange={handlePriceSliderChange}
                    size="sm"
                  >
                    <SliderTrack>
                      <SliderFilledTrack />
                    </SliderTrack>
                    <SliderThumb />
                  </Slider>
                  <Flex justify="space-between" fontSize="xs" color="gray.500">
                    <Text>-5%</Text>
                    <Text>+5%</Text>
                  </Flex>
                </>
              )}
            </FormControl>
          )}

          {showTriggerPrice && (
            <FormControl mb={3}>
              <FormLabel>Trigger Price</FormLabel>
              <Input
                type="number"
                value={triggerPrice}
                onChange={(e) => setTriggerPrice(e.target.value)}
              />
            </FormControl>
          )}

          <FormControl mb={3}>
            <FormLabel>Quantity</FormLabel>
            <Input
              type="number"
              value={quantity}
              onChange={(e) => {
                setQuantity(e.target.value);
                setQuantityPct(0);
              }}
            />
            {availableBalance && currentPrice && (
              <>
                <Slider
                  mt={1}
                  min={0}
                  max={100}
                  step={1}
                  value={quantityPct}
                  onChange={handleQuantityPctChange}
                  size="sm"
                >
                  <SliderTrack>
                    <SliderFilledTrack />
                  </SliderTrack>
                  <SliderThumb />
                </Slider>
                <Flex justify="space-between" fontSize="xs" color="gray.500">
                  <Text>0%</Text>
                  <Text>50%</Text>
                  <Text>100%</Text>
                </Flex>
              </>
            )}
          </FormControl>

          <HStack mb={3}>
            <FormControl>
              <FormLabel>Take Profit</FormLabel>
              <Input
                type="number"
                placeholder="Optional"
                value={takeProfit}
                onChange={(e) => setTakeProfit(e.target.value)}
              />
            </FormControl>
            <FormControl>
              <FormLabel>Stop Loss</FormLabel>
              <Input
                type="number"
                placeholder="Optional"
                value={stopLoss}
                onChange={(e) => setStopLoss(e.target.value)}
              />
            </FormControl>
          </HStack>
        </ModalBody>
        <ModalFooter>
          <HStack>
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button
              colorScheme="blue"
              onClick={handleSubmit}
              isLoading={loading}
              isDisabled={!quantity}
            >
              Place Order
            </Button>
          </HStack>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
```

- [ ] **Step 2: Update ManualOrderModal usage in deployment detail page**

In `frontend/app/(dashboard)/live-trading/[deploymentId]/page.tsx`, update the `ManualOrderModal` props to pass `currentPrice` and `availableBalance` from the existing `useDeploymentPosition` and `useOhlcv` hooks that are already in scope on that page. Find where `<ManualOrderModal` is rendered and add:

```typescript
currentPrice={/* latest price from ohlcv or position data */}
availableBalance={positionData?.portfolio?.available_margin ?? null}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/live-trading/ManualOrderModal.tsx frontend/app/\(dashboard\)/live-trading/\[deploymentId\]/page.tsx
git commit -m "feat: upgrade ManualOrderModal with TP/SL, trigger price, and sliders"
```

---

## Task 17: Integration Test — Full Flow Verification

- [ ] **Step 1: Run all frontend tests**

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/frontend
PATH="/nix/store/p7rrmmg1avg6zd0mbyvki32lg3r80gxq-nodejs-20.20.1/bin:$PATH" npx jest --no-coverage
```

Expected: All tests pass including new ones.

- [ ] **Step 2: Run all backend tests**

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/backend
.venv/bin/pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 3: Verify frontend builds**

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/frontend
PATH="/nix/store/p7rrmmg1avg6zd0mbyvki32lg3r80gxq-nodejs-20.20.1/bin:$PATH" npm run build
```

Expected: Build succeeds without errors.

- [ ] **Step 4: Manual smoke test**

Start backend + frontend dev servers and verify:
1. Navigate to `/trade` — chart loads with BTCUSDT candles
2. Watchlist shows live prices updating
3. Click ETHUSDT in watchlist — chart switches
4. Select a broker, enter quantity, place a market order
5. Order appears in trade history
6. Navigate to a deployment detail page — modal shows new TP/SL fields and sliders

- [ ] **Step 5: Final commit if any fixes needed**

```bash
git add -u
git commit -m "fix: integration test fixes"
```
