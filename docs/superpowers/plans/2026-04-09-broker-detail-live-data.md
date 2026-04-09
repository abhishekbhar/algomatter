# Broker Detail Live Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the broker detail page show live data for webhook-driven strategies by adding live positions from Exchange1, a merged activity feed (webhook signals + deployment trades), and balance with used margin.

**Architecture:** Three new backend endpoints (`/live-positions`, `/activity`, enhanced `/balance`) pull live data from Exchange1 and the DB, merge by source, and tag each item with its origin. The frontend replaces the empty deployment-only views with new hooks and components that consume these endpoints.

**Tech Stack:** FastAPI (Python), SQLAlchemy async, Next.js 14, Chakra UI, SWR

---

## File Map

| File | Change |
|------|--------|
| `backend/app/brokers/schemas.py` | Add `used_margin` to `BrokerBalanceResponse`; add `LivePositionResponse`, `ActivityItemResponse`, `ActivityResponse` |
| `backend/app/brokers/router.py` | Enhance `/balance`; add `GET /{id}/live-positions`; add `GET /{id}/activity` |
| `backend/tests/test_broker_live_data.py` | New test file for the three endpoints |
| `frontend/lib/api/types.ts` | Add `LivePosition`, `ActivityItem`, `ActivityResponse` interfaces; add `used_margin` to `BrokerBalance` |
| `frontend/lib/hooks/useApi.ts` | Add `useLivePositions`, `useActivity`; update `useBrokerBalance` return type |
| `frontend/components/brokers/OriginBadge.tsx` | New reusable badge component |
| `frontend/components/brokers/BrokerPositionsTable.tsx` | Replace with live positions view |
| `frontend/components/brokers/BrokerTradesTable.tsx` | Replace with activity view |
| `frontend/components/brokers/BrokerStatsBar.tsx` | Add balance row |
| `frontend/app/(dashboard)/brokers/[id]/page.tsx` | Rename "Order History" → "Activity"; wire `useLivePositions` for position count |

---

## Task 1: Enhance `/balance` — add `used_margin`

**Files:**
- Modify: `backend/app/brokers/schemas.py`
- Modify: `backend/app/brokers/router.py`
- Create: `backend/tests/test_broker_live_data.py`
- Modify: `frontend/lib/api/types.ts`
- Modify: `frontend/lib/hooks/useApi.ts`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_broker_live_data.py`:

```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from tests.conftest import create_authenticated_user


@pytest.mark.asyncio
async def test_balance_includes_used_margin(client):
    tokens = await create_authenticated_user(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    create_resp = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "exchange1",
            "label": "Test Broker",
            "credentials": {"api_key": "k", "api_secret": "s"},
        },
        headers=headers,
    )
    broker_id = create_resp.json()["id"]

    mock_balance = AsyncMock()
    mock_balance.available = Decimal("50000")
    mock_balance.total = Decimal("60000")
    mock_balance.used_margin = Decimal("10000")

    mock_broker = AsyncMock()
    mock_broker.get_balance = AsyncMock(return_value=mock_balance)
    mock_broker.close = AsyncMock()

    with patch("app.brokers.router.get_broker", return_value=mock_broker):
        resp = await client.get(f"/api/v1/brokers/{broker_id}/balance", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] == 50000.0
    assert data["total"] == 60000.0
    assert data["used_margin"] == 10000.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/abhishekbhar/projects/algomatter_worktree/algomatter/backend
LD_LIBRARY_PATH=$(nix-build --no-out-link '<nixpkgs>' -A stdenv.cc.cc.lib)/lib \
  .venv/bin/pytest tests/test_broker_live_data.py::test_balance_includes_used_margin -v
```

Expected: FAIL — `KeyError: 'used_margin'` or `AssertionError`

- [ ] **Step 3: Add `used_margin` to `BrokerBalanceResponse` in schemas.py**

In `backend/app/brokers/schemas.py`, change:

```python
class BrokerBalanceResponse(BaseModel):
    available: float
    total: float
```

to:

```python
class BrokerBalanceResponse(BaseModel):
    available: float
    total: float
    used_margin: float
```

- [ ] **Step 4: Update `/balance` endpoint in router.py**

In `backend/app/brokers/router.py`, change:

```python
        return BrokerBalanceResponse(
            available=float(balance.available),
            total=float(balance.total),
        )
```

to:

```python
        return BrokerBalanceResponse(
            available=float(balance.available),
            total=float(balance.total),
            used_margin=float(balance.used_margin),
        )
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /home/abhishekbhar/projects/algomatter_worktree/algomatter/backend
LD_LIBRARY_PATH=$(nix-build --no-out-link '<nixpkgs>' -A stdenv.cc.cc.lib)/lib \
  .venv/bin/pytest tests/test_broker_live_data.py::test_balance_includes_used_margin -v
```

Expected: PASS

- [ ] **Step 6: Update `BrokerBalance` in `frontend/lib/api/types.ts`**

Change:

```typescript
export interface BrokerBalance {
  available: number;
  total: number;
}
```

to:

```typescript
export interface BrokerBalance {
  available: number;
  total: number;
  used_margin: number;
}
```

Also add `BrokerBalance` to imports if not already there — it is already defined at line 392.

- [ ] **Step 7: Update `useBrokerBalance` return type in `frontend/lib/hooks/useApi.ts`**

Change:

```typescript
export function useBrokerBalance(brokerConnectionId: string | null, productType?: string) {
  const params = productType ? `?product_type=${productType}` : "";
  return useApiGet<{ available: number; total: number }>(
    brokerConnectionId ? `/api/v1/brokers/${brokerConnectionId}/balance${params}` : null,
    { refreshInterval: 10000 },
  );
}
```

to:

```typescript
export function useBrokerBalance(brokerConnectionId: string | null, productType?: string) {
  const params = productType ? `?product_type=${productType}` : "";
  return useApiGet<BrokerBalance>(
    brokerConnectionId ? `/api/v1/brokers/${brokerConnectionId}/balance${params}` : null,
    { refreshInterval: 10000 },
  );
}
```

Add `BrokerBalance` to the import at the top of `useApi.ts` (already imports from `types`).

- [ ] **Step 8: Commit**

```bash
cd /home/abhishekbhar/projects/algomatter_worktree/algomatter
git add backend/app/brokers/schemas.py backend/app/brokers/router.py \
        backend/tests/test_broker_live_data.py \
        frontend/lib/api/types.ts frontend/lib/hooks/useApi.ts
git commit -m "feat: add used_margin to broker balance endpoint"
```

---

## Task 2: Backend `GET /{id}/live-positions`

**Files:**
- Modify: `backend/app/brokers/schemas.py`
- Modify: `backend/app/brokers/router.py`
- Modify: `backend/tests/test_broker_live_data.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_broker_live_data.py`:

```python
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from app.db.models import Strategy, StrategyDeployment, StrategyCode, StrategyCodeVersion, DeploymentState
import uuid


async def _make_broker(client, headers, label="Live Pos Broker"):
    resp = await client.post(
        "/api/v1/brokers",
        json={
            "broker_type": "exchange1",
            "label": label,
            "credentials": {"api_key": "k", "api_secret": "s"},
        },
        headers=headers,
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_live_positions_empty(client):
    """When Exchange1 returns no positions, endpoint returns []."""
    tokens = await create_authenticated_user(client, email="livepos1@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    broker_id = await _make_broker(client, headers)

    mock_broker = AsyncMock()
    mock_broker.get_positions = AsyncMock(return_value=[])
    mock_broker.close = AsyncMock()

    with patch("app.brokers.router.get_broker", return_value=mock_broker):
        resp = await client.get(f"/api/v1/brokers/{broker_id}/live-positions", headers=headers)

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_live_positions_exchange_direct(client):
    """Position with no matching deployment or webhook → exchange_direct."""
    tokens = await create_authenticated_user(client, email="livepos2@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    broker_id = await _make_broker(client, headers, label="ExDirect Broker")

    from app.brokers.base import Position as BrokerPosition
    mock_position = BrokerPosition(
        symbol="BANKNIFTY",
        exchange="NFO",
        action="BUY",
        quantity=Decimal("50"),
        entry_price=Decimal("45000"),
        product_type="FUTURES",
    )

    mock_broker = AsyncMock()
    mock_broker.get_positions = AsyncMock(return_value=[mock_position])
    mock_broker.close = AsyncMock()

    with patch("app.brokers.router.get_broker", return_value=mock_broker):
        resp = await client.get(f"/api/v1/brokers/{broker_id}/live-positions", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "BANKNIFTY"
    assert data[0]["origin"] == "exchange_direct"
    assert data[0]["strategy_name"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/abhishekbhar/projects/algomatter_worktree/algomatter/backend
LD_LIBRARY_PATH=$(nix-build --no-out-link '<nixpkgs>' -A stdenv.cc.cc.lib)/lib \
  .venv/bin/pytest tests/test_broker_live_data.py::test_live_positions_empty \
                   tests/test_broker_live_data.py::test_live_positions_exchange_direct -v
```

Expected: FAIL — 404 (endpoint not found)

- [ ] **Step 3: Add schemas to `backend/app/brokers/schemas.py`**

Append to the end of the file:

```python
class LivePositionResponse(BaseModel):
    symbol: str
    exchange: str
    action: str           # "BUY" (long) or "SELL" (short)
    quantity: float
    entry_price: float
    product_type: str
    origin: str           # "webhook", "deployment", "exchange_direct"
    strategy_name: str | None
```

- [ ] **Step 4: Add imports and `GET /{id}/live-positions` endpoint to `router.py`**

At the top of `backend/app/brokers/router.py`, add to the imports:

1. In the `from app.brokers.schemas import (...)` block, add `LivePositionResponse`
2. In the `from app.db.models import (...)` block, add `Strategy, WebhookSignal` (they're not currently imported there)

Then add the endpoint after the `get_broker_balance` function (around line 255, before the `get_broker_quote` function):

```python
@router.get("/{connection_id}/live-positions", response_model=list[LivePositionResponse])
async def get_live_positions(
    connection_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    from datetime import datetime, timedelta, timezone

    tenant_id = uuid.UUID(current_user["user_id"])
    conn = await session.scalar(_get_broker_or_404(connection_id, tenant_id))
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broker connection not found")

    credentials = decrypt_credentials(conn.tenant_id, conn.credentials)
    broker = await get_broker(conn.broker_type, credentials)
    try:
        exchange_positions = await broker.get_positions()
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to fetch positions from broker")
    finally:
        await broker.close()

    if not exchange_positions:
        return []

    # --- Origin inference ---

    # 1. Deployment positions: symbol → (deployment_name, side)
    dep_result = await session.execute(
        select(StrategyDeployment, DeploymentState, StrategyCode)
        .join(DeploymentState, DeploymentState.deployment_id == StrategyDeployment.id)
        .join(StrategyCode, StrategyCode.id == StrategyDeployment.strategy_code_id)
        .where(
            StrategyDeployment.broker_connection_id == connection_id,
            StrategyDeployment.tenant_id == tenant_id,
            StrategyDeployment.status.in_(["running", "paused"]),
        )
    )
    # Map: (symbol, side) → strategy_name, where side is "BUY" or "SELL"
    dep_positions: dict[tuple[str, str], str] = {}
    for sd, ds, sc in dep_result:
        pos = ds.position
        if pos and pos.get("quantity", 0) != 0:
            qty = pos["quantity"]
            side = "BUY" if qty > 0 else "SELL"
            dep_positions[(sd.symbol, side)] = sc.name

    # 2. Webhook net positions: symbol → (net_qty, strategy_name)
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    wh_result = await session.execute(
        select(WebhookSignal, Strategy)
        .join(Strategy, Strategy.id == WebhookSignal.strategy_id)
        .where(
            Strategy.broker_connection_id == connection_id,
            WebhookSignal.tenant_id == tenant_id,
            WebhookSignal.execution_result == "filled",
            WebhookSignal.received_at >= cutoff,
        )
    )
    # Reconstruct net open position per symbol
    webhook_net: dict[str, tuple[float, str]] = {}  # symbol → (net_qty, strategy_name)
    for ws, strat in wh_result:
        sig = ws.parsed_signal or {}
        symbol = sig.get("symbol")
        action = sig.get("action", "").upper()
        qty = float(sig.get("quantity", 0))
        if not symbol or not action or qty == 0:
            continue
        current_net, _ = webhook_net.get(symbol, (0.0, strat.name))
        delta = qty if action == "BUY" else -qty
        webhook_net[symbol] = (current_net + delta, strat.name)

    result: list[LivePositionResponse] = []
    for pos in exchange_positions:
        action = pos.action.upper()  # "BUY" or "SELL"
        origin = "exchange_direct"
        strategy_name = None

        # Deployment takes priority
        key = (pos.symbol, action)
        if key in dep_positions:
            origin = "deployment"
            strategy_name = dep_positions[key]
        else:
            net, wh_name = webhook_net.get(pos.symbol, (0.0, None))
            if (action == "BUY" and net > 0) or (action == "SELL" and net < 0):
                origin = "webhook"
                strategy_name = wh_name

        result.append(LivePositionResponse(
            symbol=pos.symbol,
            exchange=pos.exchange,
            action=action,
            quantity=float(pos.quantity),
            entry_price=float(pos.entry_price),
            product_type=pos.product_type,
            origin=origin,
            strategy_name=strategy_name,
        ))

    return result
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /home/abhishekbhar/projects/algomatter_worktree/algomatter/backend
LD_LIBRARY_PATH=$(nix-build --no-out-link '<nixpkgs>' -A stdenv.cc.cc.lib)/lib \
  .venv/bin/pytest tests/test_broker_live_data.py::test_live_positions_empty \
                   tests/test_broker_live_data.py::test_live_positions_exchange_direct -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd /home/abhishekbhar/projects/algomatter_worktree/algomatter
git add backend/app/brokers/schemas.py backend/app/brokers/router.py \
        backend/tests/test_broker_live_data.py
git commit -m "feat: add GET /brokers/{id}/live-positions endpoint with origin inference"
```

---

## Task 3: Backend `GET /{id}/activity`

**Files:**
- Modify: `backend/app/brokers/schemas.py`
- Modify: `backend/app/brokers/router.py`
- Modify: `backend/tests/test_broker_live_data.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_broker_live_data.py`:

```python
@pytest.mark.asyncio
async def test_activity_empty(client):
    """No signals or trades → empty list."""
    tokens = await create_authenticated_user(client, email="activity1@test.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    broker_id = await _make_broker(client, headers, label="Activity Broker")

    resp = await client.get(f"/api/v1/brokers/{broker_id}/activity", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["offset"] == 0
    assert data["limit"] == 50
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/abhishekbhar/projects/algomatter_worktree/algomatter/backend
LD_LIBRARY_PATH=$(nix-build --no-out-link '<nixpkgs>' -A stdenv.cc.cc.lib)/lib \
  .venv/bin/pytest tests/test_broker_live_data.py::test_activity_empty -v
```

Expected: FAIL — 404 (endpoint not found)

- [ ] **Step 3: Add schemas to `backend/app/brokers/schemas.py`**

Append to the end of the file:

```python
class ActivityItemResponse(BaseModel):
    id: str
    source: str           # "webhook" or "deployment"
    symbol: str
    action: str           # "BUY" or "SELL"
    quantity: float
    fill_price: float | None
    status: str
    order_id: str | None
    strategy_name: str | None
    created_at: str       # ISO 8601


class ActivityResponse(BaseModel):
    items: list[ActivityItemResponse]
    total: int
    offset: int
    limit: int
```

- [ ] **Step 4: Add `GET /{id}/activity` endpoint to `router.py`**

Also add `ActivityItemResponse, ActivityResponse` to the `from app.brokers.schemas import (...)` block.

Add the endpoint after `get_live_positions`:

```python
@router.get("/{connection_id}/activity", response_model=ActivityResponse)
async def get_broker_activity(
    connection_id: uuid.UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    conn = await session.scalar(_get_broker_or_404(connection_id, tenant_id))
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broker connection not found")

    items: list[ActivityItemResponse] = []

    # Source A: Webhook signals (filled, for strategies linked to this broker)
    wh_result = await session.execute(
        select(WebhookSignal, Strategy)
        .join(Strategy, Strategy.id == WebhookSignal.strategy_id)
        .where(
            Strategy.broker_connection_id == connection_id,
            WebhookSignal.tenant_id == tenant_id,
            WebhookSignal.execution_result == "filled",
        )
    )
    for ws, strat in wh_result:
        sig = ws.parsed_signal or {}
        detail = ws.execution_detail or {}
        order_id = detail.get("broker_order_id") or detail.get("order_id")
        items.append(ActivityItemResponse(
            id=str(ws.id),
            source="webhook",
            symbol=sig.get("symbol", ""),
            action=(sig.get("action") or "").upper(),
            quantity=float(sig.get("quantity", 0)),
            fill_price=None,  # Exchange1 doesn't return fill prices
            status=ws.execution_result or "filled",
            order_id=str(order_id) if order_id else None,
            strategy_name=strat.name,
            created_at=ws.received_at.isoformat() if ws.received_at else "",
        ))

    # Source B: Deployment trades for deployments linked to this broker
    dt_result = await session.execute(
        select(DeploymentTrade, StrategyDeployment, StrategyCode)
        .join(StrategyDeployment, StrategyDeployment.id == DeploymentTrade.deployment_id)
        .join(StrategyCode, StrategyCode.id == StrategyDeployment.strategy_code_id)
        .where(
            StrategyDeployment.broker_connection_id == connection_id,
            DeploymentTrade.tenant_id == tenant_id,
        )
    )
    for dt, sd, sc in dt_result:
        items.append(ActivityItemResponse(
            id=str(dt.id),
            source="deployment",
            symbol=sd.symbol,
            action=dt.action.upper(),
            quantity=float(dt.quantity),
            fill_price=float(dt.fill_price) if dt.fill_price is not None else None,
            status=dt.status,
            order_id=dt.broker_order_id,
            strategy_name=sc.name,
            created_at=dt.created_at.isoformat() if dt.created_at else "",
        ))

    # Sort combined list by created_at descending
    items.sort(key=lambda x: x.created_at, reverse=True)
    total = len(items)
    page = items[offset: offset + limit]

    return ActivityResponse(items=page, total=total, offset=offset, limit=limit)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /home/abhishekbhar/projects/algomatter_worktree/algomatter/backend
LD_LIBRARY_PATH=$(nix-build --no-out-link '<nixpkgs>' -A stdenv.cc.cc.lib)/lib \
  .venv/bin/pytest tests/test_broker_live_data.py::test_activity_empty -v
```

Expected: PASS

- [ ] **Step 6: Run all broker live data tests**

```bash
cd /home/abhishekbhar/projects/algomatter_worktree/algomatter/backend
LD_LIBRARY_PATH=$(nix-build --no-out-link '<nixpkgs>' -A stdenv.cc.cc.lib)/lib \
  .venv/bin/pytest tests/test_broker_live_data.py -v
```

Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
cd /home/abhishekbhar/projects/algomatter_worktree/algomatter
git add backend/app/brokers/schemas.py backend/app/brokers/router.py \
        backend/tests/test_broker_live_data.py
git commit -m "feat: add GET /brokers/{id}/activity endpoint merging webhook + deployment trades"
```

---

## Task 4: Frontend types, hooks, and `OriginBadge` component

**Files:**
- Modify: `frontend/lib/api/types.ts`
- Modify: `frontend/lib/hooks/useApi.ts`
- Create: `frontend/components/brokers/OriginBadge.tsx`

- [ ] **Step 1: Add new types to `frontend/lib/api/types.ts`**

Append to the end of `frontend/lib/api/types.ts`:

```typescript
export interface LivePosition {
  symbol: string;
  exchange: string;
  action: string;       // "BUY" or "SELL"
  quantity: number;
  entry_price: number;
  product_type: string;
  origin: "webhook" | "deployment" | "exchange_direct";
  strategy_name: string | null;
}

export interface ActivityItem {
  id: string;
  source: "webhook" | "deployment";
  symbol: string;
  action: string;
  quantity: number;
  fill_price: number | null;
  status: string;
  order_id: string | null;
  strategy_name: string | null;
  created_at: string;
}

export interface ActivityResponse {
  items: ActivityItem[];
  total: number;
  offset: number;
  limit: number;
}
```

- [ ] **Step 2: Add hooks to `frontend/lib/hooks/useApi.ts`**

Add the new imports at the top of `useApi.ts`. Add `LivePosition, ActivityResponse` to the existing `import type { ... }` block from `@/lib/api/types`.

Then append the new hooks at the end of `useApi.ts` (before the closing of the file):

```typescript
export function useLivePositions(id: string | undefined) {
  return useApiGet<LivePosition[]>(
    id ? `/api/v1/brokers/${id}/live-positions` : null,
    { refreshInterval: 10000 },
  );
}

export function useActivity(id: string | undefined, offset = 0, limit = 50) {
  return useApiGet<ActivityResponse>(
    id ? `/api/v1/brokers/${id}/activity?offset=${offset}&limit=${limit}` : null,
  );
}
```

- [ ] **Step 3: Create `frontend/components/brokers/OriginBadge.tsx`**

```typescript
"use client";
import { Badge } from "@chakra-ui/react";

interface OriginBadgeProps {
  origin: "webhook" | "deployment" | "exchange_direct";
}

const ORIGIN_CONFIG = {
  webhook: { colorScheme: "blue", label: "Webhook" },
  deployment: { colorScheme: "purple", label: "Deployment" },
  exchange_direct: { colorScheme: "orange", label: "Exchange Direct" },
} as const;

export function OriginBadge({ origin }: OriginBadgeProps) {
  const { colorScheme, label } = ORIGIN_CONFIG[origin];
  return (
    <Badge colorScheme={colorScheme} variant="subtle" fontSize="xs">
      {label}
    </Badge>
  );
}
```

- [ ] **Step 4: Commit**

```bash
cd /home/abhishekbhar/projects/algomatter_worktree/algomatter
git add frontend/lib/api/types.ts frontend/lib/hooks/useApi.ts \
        frontend/components/brokers/OriginBadge.tsx
git commit -m "feat: add LivePosition/Activity types, hooks, and OriginBadge component"
```

---

## Task 5: Replace `BrokerPositionsTable` with live positions + add balance to stats bar

**Files:**
- Modify: `frontend/components/brokers/BrokerPositionsTable.tsx`
- Modify: `frontend/components/brokers/BrokerStatsBar.tsx`

- [ ] **Step 1: Rewrite `frontend/components/brokers/BrokerPositionsTable.tsx`**

Replace the entire file content:

```typescript
"use client";
import {
  Box, Table, Thead, Tbody, Tr, Th, Td, Badge, Text, VStack,
  useColorModeValue,
} from "@chakra-ui/react";
import { useLivePositions } from "@/lib/hooks/useApi";
import { OriginBadge } from "@/components/brokers/OriginBadge";

interface Props {
  brokerId: string;
}

export function BrokerPositionsTable({ brokerId }: Props) {
  const { data: positions, isLoading } = useLivePositions(brokerId);
  const borderColor = useColorModeValue("gray.200", "gray.700");

  if (isLoading) return <Box py={4}><Text color="gray.500">Loading...</Text></Box>;
  if (!positions || positions.length === 0) {
    return <Box py={8} textAlign="center"><Text color="gray.500">No open positions on this account.</Text></Box>;
  }

  return (
    <Box overflowX="auto">
      <Table size="sm" variant="simple">
        <Thead>
          <Tr>
            <Th>Symbol</Th>
            <Th>Side</Th>
            <Th isNumeric>Qty</Th>
            <Th isNumeric>Entry Price</Th>
            <Th>Source</Th>
            <Th>Strategy</Th>
          </Tr>
        </Thead>
        <Tbody>
          {positions.map((pos, i) => (
            <Tr key={`${pos.symbol}-${i}`} borderBottomWidth={1} borderColor={borderColor}>
              <Td fontWeight="semibold">{pos.symbol}</Td>
              <Td>
                <Badge colorScheme={pos.action === "BUY" ? "green" : "red"}>
                  {pos.action === "BUY" ? "LONG" : "SHORT"}
                </Badge>
              </Td>
              <Td isNumeric>{pos.quantity}</Td>
              <Td isNumeric>₹{pos.entry_price.toLocaleString()}</Td>
              <Td><OriginBadge origin={pos.origin} /></Td>
              <Td color="gray.500" fontSize="sm">{pos.strategy_name ?? "—"}</Td>
            </Tr>
          ))}
        </Tbody>
      </Table>
    </Box>
  );
}
```

- [ ] **Step 2: Update `frontend/components/brokers/BrokerStatsBar.tsx`**

Replace the entire file content to add a balance row below the existing stats:

```typescript
"use client";
import {
  Box, SimpleGrid, Stat, StatLabel, StatNumber, Skeleton, Text,
  useColorModeValue,
} from "@chakra-ui/react";
import { useBrokerStats, useBrokerBalance } from "@/lib/hooks/useApi";

interface Props {
  brokerId: string;
}

function formatPnl(pnl: number): string {
  const sign = pnl >= 0 ? "+" : "-";
  return `${sign}₹${Math.abs(pnl).toFixed(2)}`;
}

function formatAmount(n: number): string {
  return `₹${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

export function BrokerStatsBar({ brokerId }: Props) {
  const { data: stats, isLoading: statsLoading } = useBrokerStats(brokerId);
  const { data: balance, isLoading: balanceLoading } = useBrokerBalance(brokerId, "cfd");
  const cardBg = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");
  const pnlColor = stats && stats.total_realized_pnl >= 0 ? "green.400" : "red.400";

  if (statsLoading) {
    return (
      <Box mb={6}>
        <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4} mb={4}>
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} height="80px" borderRadius="md" />)}
        </SimpleGrid>
        <SimpleGrid columns={{ base: 3 }} spacing={4} mb={4}>
          {[0, 1, 2].map((i) => <Skeleton key={i} height="80px" borderRadius="md" />)}
        </SimpleGrid>
      </Box>
    );
  }

  return (
    <Box mb={6}>
      <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4} mb={4}>
        <Stat bg={cardBg} borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
          <StatLabel>Active Deployments</StatLabel>
          <StatNumber>{stats?.active_deployments ?? "—"}</StatNumber>
        </Stat>
        <Stat bg={cardBg} borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
          <StatLabel>Total Realized P&L</StatLabel>
          <StatNumber color={pnlColor}>{stats ? formatPnl(stats.total_realized_pnl) : "—"}</StatNumber>
        </Stat>
        <Stat bg={cardBg} borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
          <StatLabel>Win Rate</StatLabel>
          <StatNumber>{stats ? `${(stats.win_rate * 100).toFixed(1)}%` : "—"}</StatNumber>
        </Stat>
        <Stat bg={cardBg} borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
          <StatLabel>Total Trades</StatLabel>
          <StatNumber>{stats?.total_trades ?? "—"}</StatNumber>
        </Stat>
      </SimpleGrid>

      {balance && (
        <SimpleGrid columns={{ base: 3 }} spacing={4}>
          <Stat bg={cardBg} borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
            <StatLabel>Available Balance</StatLabel>
            <StatNumber fontSize="md">{formatAmount(balance.available)}</StatNumber>
          </Stat>
          <Stat bg={cardBg} borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
            <StatLabel>Used Margin</StatLabel>
            <StatNumber fontSize="md" color="orange.400">{formatAmount(balance.used_margin)}</StatNumber>
          </Stat>
          <Stat bg={cardBg} borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
            <StatLabel>Total Balance</StatLabel>
            <StatNumber fontSize="md">{formatAmount(balance.total)}</StatNumber>
          </Stat>
        </SimpleGrid>
      )}
    </Box>
  );
}
```

- [ ] **Step 3: Commit**

```bash
cd /home/abhishekbhar/projects/algomatter_worktree/algomatter
git add frontend/components/brokers/BrokerPositionsTable.tsx \
        frontend/components/brokers/BrokerStatsBar.tsx
git commit -m "feat: live positions table with origin badge + balance row in stats bar"
```

---

## Task 6: Replace `BrokerTradesTable` with activity view + update page

**Files:**
- Modify: `frontend/components/brokers/BrokerTradesTable.tsx`
- Modify: `frontend/app/(dashboard)/brokers/[id]/page.tsx`

- [ ] **Step 1: Rewrite `frontend/components/brokers/BrokerTradesTable.tsx`**

Replace the entire file content:

```typescript
"use client";
import { useState } from "react";
import {
  Box, Table, Thead, Tbody, Tr, Th, Td, Badge, Text, HStack, Button, Flex, Tooltip,
} from "@chakra-ui/react";
import { useActivity } from "@/lib/hooks/useApi";
import { formatDate } from "@/lib/utils/formatters";

interface Props {
  brokerId: string;
}

const PAGE_SIZE = 50;

export function BrokerTradesTable({ brokerId }: Props) {
  const [offset, setOffset] = useState(0);
  const { data, isLoading } = useActivity(brokerId, offset, PAGE_SIZE);

  if (isLoading) return <Box py={4}><Text color="gray.500">Loading...</Text></Box>;
  if (!data || data.items.length === 0) {
    return <Box py={8} textAlign="center"><Text color="gray.500">No activity recorded</Text></Box>;
  }

  const { items, total } = data;
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
              <Th>Source</Th>
              <Th>Strategy</Th>
              <Th>Status</Th>
            </Tr>
          </Thead>
          <Tbody>
            {items.map((item) => (
              <Tr key={item.id}>
                <Td fontSize="xs" color="gray.500">{formatDate(item.created_at)}</Td>
                <Td fontWeight="semibold">{item.symbol}</Td>
                <Td>
                  <Badge colorScheme={item.action === "BUY" ? "green" : "red"}>{item.action}</Badge>
                </Td>
                <Td isNumeric>{item.quantity}</Td>
                <Td isNumeric>
                  {item.fill_price != null ? (
                    `₹${item.fill_price.toLocaleString()}`
                  ) : (
                    <Tooltip label="Exchange1 does not return fill prices for futures orders.">
                      <Text as="span" color="gray.400">—</Text>
                    </Tooltip>
                  )}
                </Td>
                <Td>
                  <Badge
                    colorScheme={item.source === "webhook" ? "blue" : "purple"}
                    variant="subtle"
                    fontSize="xs"
                  >
                    {item.source === "webhook" ? "Webhook" : "Deployment"}
                  </Badge>
                </Td>
                <Td color="gray.500" fontSize="sm">{item.strategy_name ?? "—"}</Td>
                <Td><Badge variant="subtle">{item.status}</Badge></Td>
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

      <Text fontSize="xs" color="gray.500" mt={3} px={1}>
        Exchange-direct trades (placed directly on Exchange1) are not visible here.
      </Text>
    </Box>
  );
}
```

- [ ] **Step 2: Update `frontend/app/(dashboard)/brokers/[id]/page.tsx`**

Two changes:
1. Rename `"Order History"` tab label → `"Activity"`
2. Import `useLivePositions` instead of `useBrokerPositions` for the position count badge

Replace the file content:

```typescript
"use client";
import {
  Box, Flex, Heading, Text, Tab, TabList, TabPanel, TabPanels, Tabs, Badge,
} from "@chakra-ui/react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useBrokers, useLivePositions, useBrokerOrders } from "@/lib/hooks/useApi";
import { BrokerStatsBar } from "@/components/brokers/BrokerStatsBar";
import { BrokerPositionsTable } from "@/components/brokers/BrokerPositionsTable";
import { BrokerOrdersTable } from "@/components/brokers/BrokerOrdersTable";
import { BrokerTradesTable } from "@/components/brokers/BrokerTradesTable";

export default function BrokerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: brokers } = useBrokers();
  const { data: positions } = useLivePositions(id);
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
        <Box>
          <Heading size="lg">{broker?.label ?? id}</Heading>
          {broker && (
            <Text fontSize="xs" color="gray.500" textTransform="uppercase">
              {broker.broker_type}
            </Text>
          )}
        </Box>
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
          <Tab>Activity</Tab>
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

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /home/abhishekbhar/projects/algomatter_worktree/algomatter/frontend
npx tsc --noEmit 2>&1 | head -30
```

Expected: No errors (or only pre-existing unrelated errors)

- [ ] **Step 4: Commit**

```bash
cd /home/abhishekbhar/projects/algomatter_worktree/algomatter
git add frontend/components/brokers/BrokerTradesTable.tsx \
        frontend/app/(dashboard)/brokers/[id]/page.tsx
git commit -m "feat: activity tab replaces order history, live positions on broker detail page"
```

---

## Spec Self-Review

- [x] `/balance` — `used_margin` added to schema, endpoint, frontend type, hook
- [x] `/live-positions` — `LivePositionResponse` with all fields, origin inference 3-tier logic, deployment priority over webhook
- [x] `/activity` — `ActivityItemResponse`/`ActivityResponse`, webhook + deployment merged, sorted descending, paginated
- [x] Frontend: `useLivePositions` (10s refresh), `useActivity` (no auto-refresh), `useBrokerBalance` updated type
- [x] `OriginBadge` — blue/purple/orange for webhook/deployment/exchange_direct
- [x] Balance row added to `BrokerStatsBar` with Available, Used Margin, Total
- [x] Positions tab — uses `useLivePositions`, shows `OriginBadge` + `strategy_name`
- [x] Activity tab — uses `useActivity`, source badge, fill price tooltip, exchange-direct footer note
- [x] "Order History" tab renamed to "Activity"
- [x] Error handling — 502 on Exchange1 auth failure for live-positions; 404 on broker not found
- [x] Empty states — "No open positions on this account." / "No activity recorded"

---

## Deployment

After all tasks complete and tests pass, run `/deploy` to push to production.
