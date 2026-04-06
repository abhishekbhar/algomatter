# Broker Detail Page — Design Spec

**Date:** 2026-04-06
**Status:** Approved

---

## Overview

Add a dedicated broker connection detail page at `/brokers/[id]` that shows exchange-level trading activity — positions, open orders, order history, and summary stats — aggregated across all deployments that use that broker connection.

Target users: traders who run multiple strategies on one exchange account and want a unified view of what's happening on that account.

---

## Scope

- **In scope:** Per broker connection views (positions, open orders, order history, stats)
- **Out of scope:** Live data fetched directly from the exchange; cross-broker aggregation; manual order creation from this page
- **Data source:** AlgoMatter database only — aggregated from existing `deployment_trades` and `deployment_states` tables

---

## Navigation

- `app/(dashboard)/brokers/page.tsx` (existing) — each broker card becomes a `Next.js Link` to `/brokers/[id]`
- `app/(dashboard)/brokers/[id]/page.tsx` (new) — full detail page
- Back link on detail page navigates to `/brokers`

---

## Page Layout

```
[← Broker Connections]   Exchange1 · Main Account   [Connected]

┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Active Depls    │ │ Total P&L       │ │ Win Rate        │ │ Total Trades    │
│       3         │ │    +$2,340      │ │      64%        │ │      142        │
└─────────────────┘ └─────────────────┘ └─────────────────┘ └─────────────────┘

┌────────────────────────────────────────────────────────────┐
│  [Positions (3)]  [Open Orders (1)]  [Order History]       │
├────────────────────────────────────────────────────────────┤
│  Symbol │ Side │ Qty │ Avg Entry │ Unrealized P&L │ Strategy │ Action │
│  ...    │ ...  │ ... │ ...       │ ...            │ ...      │ Close  │
└────────────────────────────────────────────────────────────┘
```

---

## Backend

### New Endpoints

Add to `app/brokers/router.py`. All endpoints:
- Require authenticated user (existing `current_user` dependency)
- Filter by `tenant_id` to enforce multi-tenancy
- Return 404 if broker connection not found or does not belong to the tenant

#### `GET /api/v1/brokers/{connection_id}/stats`

Aggregates across all `StrategyDeployment` rows where `broker_connection_id = connection_id`.

**Response: `BrokerStatsResponse`**
```python
class BrokerStatsResponse(BaseModel):
    active_deployments: int      # COUNT where mode='live' AND status='running'
    total_realized_pnl: float    # SUM(realized_pnl) from deployment_trades WHERE status='filled'
    win_rate: float              # COUNT(pnl > 0) / COUNT(total filled trades with non-null pnl), 0.0 if no trades
    total_trades: int            # COUNT of filled trades
```

#### `GET /api/v1/brokers/{connection_id}/positions`

Fetches `deployment_states` for all deployments with `mode='live' AND status='running'` linked to this broker, returns rows where `position` is not null. Use `selectinload(StrategyDeployment.strategy_code)` when querying deployments to avoid N+1; `deployment_name` is `dep.strategy_code.name if dep.strategy_code else ""` — same pattern as `deployments/router.py`.

**Response: `list[BrokerPositionResponse]`**
```python
class BrokerPositionResponse(BaseModel):
    deployment_id: str
    deployment_name: str         # dep.strategy_code.name (via ORM relationship, not a column)
    symbol: str                  # StrategyDeployment.symbol
    side: str                    # "LONG" if quantity > 0, "SHORT" if quantity < 0
    quantity: float              # abs(position["quantity"])
    avg_entry_price: float       # position["avg_entry_price"]
    unrealized_pnl: float        # position["unrealized_pnl"]
```

#### `GET /api/v1/brokers/{connection_id}/orders`

Fetches `deployment_states.open_orders` for all deployments with `mode='live' AND status='running'` linked to this broker, flattens into a single list. Use `selectinload(StrategyDeployment.strategy_code)` same as positions endpoint.

**Response: `list[BrokerOrderResponse]`**
```python
class BrokerOrderResponse(BaseModel):
    order_id: str
    deployment_id: str
    deployment_name: str         # dep.strategy_code.name (via ORM relationship)
    symbol: str
    action: str                  # BUY or SELL
    quantity: float
    order_type: str              # MARKET or LIMIT
    price: float | None
    created_at: str | None
```

#### `GET /api/v1/brokers/{connection_id}/trades`

Queries `deployment_trades` JOIN `strategy_deployments` WHERE `broker_connection_id = connection_id`, across all deployments and statuses (not filtered to running only — history includes stopped deployments).

Use `selectinload` on `StrategyDeployment.strategy_code` (or join to `strategy_codes`) so each trade's `strategy_name` can be resolved via `dep.strategy_code.name` — same pattern as `_trade_to_response()` in `deployments/router.py`. Without eager loading this will produce an N+1 query.

**Query params:** `offset: int = 0`, `limit: int = 50` (max 200)

`total` in the response must be the pre-pagination count (a separate `SELECT COUNT(*)` with the same WHERE clause, not the count of the current page).

**Response: `TradesResponse`** — reuses the existing schema (already contains `strategy_name` and `symbol`)
```python
class TradesResponse(BaseModel):
    trades: list[DeploymentTradeResponse]
    total: int
    offset: int
    limit: int
```

### New Schemas

Add to `app/brokers/schemas.py`:
- `BrokerStatsResponse`
- `BrokerPositionResponse`
- `BrokerOrderResponse`

`TradesResponse` and `DeploymentTradeResponse` already exist in `app/deployments/schemas.py` — import and reuse.

---

## Frontend

### New Files

#### `app/(dashboard)/brokers/[id]/page.tsx`

- Calls `useBrokerPositions(brokerId)` and `useBrokerOrders(brokerId)` at the page level to get counts for tab badges. SWR deduplicates these — when the tab panels mount and call the same hooks with the same key, no extra network requests are made.
- Renders: back link, broker name + status badge, `BrokerStatsBar`, Chakra `Tabs` with `isLazy`
- Three tab panels: Positions, Open Orders, Order History
- Passes `brokerId` down to each table component

#### `components/brokers/BrokerStatsBar.tsx`

Props: `brokerId: string`

- Calls `useBrokerStats(brokerId)` with `refreshInterval: 30000`
- Renders 4 `Stat` boxes (Chakra UI): Active Deployments, Total Realized P&L, Win Rate, Total Trades
- P&L colored green/red via `useColorModeValue` + value sign

#### `components/brokers/BrokerPositionsTable.tsx`

Props: `brokerId: string`

- Calls `useBrokerPositions(brokerId)` with `refreshInterval: 5000`
- Columns: Symbol, Side, Qty, Avg Entry, Unrealized P&L, Strategy, Action
- Side badge: green "LONG" / red "SHORT"
- Unrealized P&L colored by sign
- "Close" button: fires POST to `/api/v1/deployments/{deployment_id}/manual-order` with `{ action: oppositeSide, quantity, order_type: "MARKET" }` — reuses existing manual order endpoint
- Empty state if no open positions

#### `components/brokers/BrokerOrdersTable.tsx`

Props: `brokerId: string`

- Calls `useBrokerOrders(brokerId)` with `refreshInterval: 5000`
- Columns: Time, Symbol, Action, Qty, Order Type, Price, Strategy
- Empty state if no open orders
- No cancel action (cancel is available on the deployment detail page)

#### `components/brokers/BrokerTradesTable.tsx`

Props: `brokerId: string`

- Calls `useBrokerTrades(brokerId, offset, limit)` — no polling (static history)
- Columns: Time, Symbol, Action, Qty, Fill Price, P&L, Strategy, Status
- Pagination: prev/next buttons, shows "X–Y of Z"
- P&L colored by sign; null P&L shown as "—"
- Page size: 50

### Modified Files

#### `app/(dashboard)/brokers/page.tsx`

- Wrap each broker card with `<Link href={/brokers/${broker.id}}>` (Next.js `Link`)
- Add cursor pointer styling to cards

#### `lib/api/types.ts`

Add:
```ts
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

`BrokerTradesTable` reuses existing `TradesResponse` and `DeploymentTrade` types.

#### `lib/hooks/useApi.ts`

Add:
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

---

## "Close Position" Flow

The Positions table has a Close button per row. It:
1. Determines opposite action: if `side === "LONG"` → action = `"SELL"`, else `"BUY"`
2. POSTs to `/api/v1/deployments/{deployment_id}/manual-order` with:
   ```json
   { "action": "SELL", "quantity": 0.05, "order_type": "market" }
   ```
   Note: `order_type` must be lowercase (`"market"`) — matches `ManualOrderRequest` schema default and existing frontend usage.
3. Shows a loading spinner on the button during the request
4. On success: mutates `useBrokerPositions` to refetch
5. On error: shows a Chakra `toast` with the error message

No new backend endpoint required — reuses the existing manual order endpoint.

---

## Component Structure

```
components/brokers/
  BrokerStatsBar.tsx
  BrokerPositionsTable.tsx
  BrokerOrdersTable.tsx
  BrokerTradesTable.tsx

app/(dashboard)/brokers/
  page.tsx                  (modify: add Link wrappers)
  new/page.tsx              (unchanged)
  [id]/
    page.tsx                (new)
```

---

## Files to Create / Modify

| File | Action |
|------|--------|
| `backend/app/brokers/router.py` | Modify — add 4 new endpoints |
| `backend/app/brokers/schemas.py` | Modify — add 3 new response schemas |
| `frontend/lib/api/types.ts` | Modify — add BrokerStats, BrokerPosition, BrokerOrder |
| `frontend/lib/hooks/useApi.ts` | Modify — add 4 new hooks |
| `frontend/app/(dashboard)/brokers/page.tsx` | Modify — wrap cards with Link |
| `frontend/app/(dashboard)/brokers/[id]/page.tsx` | Create |
| `frontend/components/brokers/BrokerStatsBar.tsx` | Create |
| `frontend/components/brokers/BrokerPositionsTable.tsx` | Create |
| `frontend/components/brokers/BrokerOrdersTable.tsx` | Create |
| `frontend/components/brokers/BrokerTradesTable.tsx` | Create |

---

## Out of Scope

- Manual order creation from the broker detail page (available on deployment detail)
- Cancel order from broker detail page (available on deployment detail)
- Live data fetched directly from the exchange API
- Cross-broker aggregation (e.g. "all exchanges combined")
- Position history / closed positions (separate feature, requires tracking position close events)
