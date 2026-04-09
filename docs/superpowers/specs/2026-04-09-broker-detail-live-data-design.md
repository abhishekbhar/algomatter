# Broker Detail Live Data Design

**Date:** 2026-04-09

## Goal

Fix the broker detail page so it shows useful data for webhook-driven strategies (like CHANNEL-TRADEVIEW). Currently the page is empty because all data sources pull from AlgoMatter's internal deployment tracking, which webhook trades never touch.

## Problem Statement

The broker detail page has three data sources — positions, orders, trade history — all backed by `DeploymentState` and `DeploymentTrade` DB tables. Webhook strategies fire orders directly via the broker API and record results in `WebhookSignal`, but are invisible to the broker page. Exchange-direct trades (placed on the broker platform, not through AlgoMatter) are also completely invisible.

---

## Architecture

### Backend

#### 1. Enhance `GET /brokers/{id}/balance`

File: `backend/app/brokers/schemas.py`

Add `used_margin` to `BrokerBalanceResponse`:

```python
class BrokerBalanceResponse(BaseModel):
    available: float
    total: float
    used_margin: float  # NEW — from Exchange1 cfd account available_margin field
```

File: `backend/app/brokers/router.py` — update the existing `/balance` endpoint to populate `used_margin` from `broker.get_balance()`. The `AccountBalance` object returned by Exchange1 already has `used_margin` (computed as `total - available`).

#### 2. New `GET /brokers/{id}/live-positions`

File: `backend/app/brokers/router.py`

Calls `broker.get_positions()` live from the exchange. For each position returned, infers origin:

**Origin inference logic:**
1. Fetch all running live `StrategyDeployment` rows for this broker. For each, check `state.position` — if symbol + side matches the Exchange1 position → `"deployment"`.
2. Fetch all `WebhookSignal` rows (last 30 days) for strategies linked to this broker (`Strategy.broker_connection_id == connection_id`) where `execution_result = "filled"`. Reconstruct net open position per symbol by summing filled BUY quantities minus SELL quantities. If net > 0 and Exchange1 shows a long → `"webhook"`. If net < 0 and Exchange1 shows a short → `"webhook"`.
3. If neither matches → `"exchange_direct"`.

Tie-breaking: if both a deployment and a webhook signal match the same position, `"deployment"` takes priority (deployment tracking is more precise).

Schema:

```python
class LivePositionResponse(BaseModel):
    symbol: str
    exchange: str
    action: str           # "BUY" (long) or "SELL" (short)
    quantity: float
    entry_price: float
    product_type: str     # "FUTURES" or "DELIVERY"
    origin: str           # "webhook", "deployment", "exchange_direct"
    strategy_name: str | None  # populated when origin is webhook or deployment
```

Response: `list[LivePositionResponse]`

#### 3. New `GET /brokers/{id}/activity`

File: `backend/app/brokers/router.py`

Merges two sources, sorted by `created_at` descending, paginated (offset/limit, default limit 50, max 200):

**Source A — Webhook signals:**
```sql
SELECT ws.*, s.name AS strategy_name
FROM webhook_signals ws
JOIN strategies s ON ws.strategy_id = s.id
WHERE s.broker_connection_id = :connection_id
  AND ws.tenant_id = :tenant_id
  AND ws.execution_result = 'filled'
```

**Source B — Deployment trades:**
```sql
SELECT dt.*, sc.name AS strategy_name, sd.symbol
FROM deployment_trades dt
JOIN strategy_deployments sd ON dt.deployment_id = sd.id
JOIN strategy_codes sc ON sd.strategy_code_id = sc.id
WHERE sd.broker_connection_id = :connection_id
  AND sd.tenant_id = :tenant_id
```

Merge in Python: fetch both sets without pagination, sort combined list by `created_at` desc, then apply offset/limit. Return total count of combined list.

Schema:

```python
class ActivityItemResponse(BaseModel):
    id: str
    source: str           # "webhook" or "deployment"
    symbol: str
    action: str           # "BUY" or "SELL"
    quantity: float
    fill_price: float | None   # null for Exchange1 futures (API limitation)
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

**Note on exchange-direct history:** Exchange1's API does not return historical order fills. Exchange-direct trades cannot appear in activity history. A note in the UI explains this.

---

### Frontend

#### 1. Stats Bar — add balance

File: `frontend/app/(dashboard)/brokers/[id]/page.tsx` (or `BrokerStatsBar` component if extracted)

Add a balance row using a `useBrokerBalance(id)` hook (existing hook, enhanced with `used_margin`). Refresh every 15 seconds. Display: **Available**, **Used Margin**, **Total**. Shown above or as an additional row in the existing stats bar.

#### 2. Positions Tab — live from Exchange1

Replace `useBrokerPositions(id)` with a new `useLivePositions(id)` hook:
- Fetches `GET /api/v1/brokers/{id}/live-positions`
- Refreshes every 10 seconds

Each position card shows an `OriginBadge`:
- `"webhook"` → blue badge labelled "Webhook"
- `"deployment"` → purple badge labelled "Deployment"
- `"exchange_direct"` → orange badge labelled "Exchange Direct"

When origin is `"webhook"` or `"deployment"`, show `strategy_name` below the symbol.

Empty state: "No open positions on this account."

#### 3. Activity Tab — merged webhook + deployment

Rename "Order History" tab → "Activity".

Replace `useBrokerTrades` with a new `useActivity(id, offset, limit)` hook:
- Fetches `GET /api/v1/brokers/{id}/activity`
- No auto-refresh (paginated table, user-controlled)

Each row has a source badge:
- `"webhook"` → blue "Webhook"
- `"deployment"` → purple "Deployment"

Fill price column shows `—` for null values with a tooltip: "Exchange1 does not return fill prices for futures orders."

Footer note below the table: "Exchange-direct trades (placed directly on Exchange1) are not visible here."

#### 4. Open Orders Tab

No change. Remains deployment-only.

#### New hooks in `frontend/lib/hooks/useApi.ts`

```typescript
useLivePositions(id: string)   // GET /api/v1/brokers/{id}/live-positions, 10s refresh
useActivity(id: string, offset: number, limit: number)  // GET /api/v1/brokers/{id}/activity
```

#### New component

`frontend/components/brokers/OriginBadge.tsx` — small reusable Chakra `Badge` component:

```typescript
interface OriginBadgeProps {
  origin: "webhook" | "deployment" | "exchange_direct";
}
// webhook → blue, deployment → purple, exchange_direct → orange
```

---

## Data Flow

**Positions:**
```
Page load → useLivePositions → GET /live-positions →
broker.get_positions() [Exchange1 live] +
DeploymentState query [DB] +
WebhookSignal net-position query [DB] →
Origin inference → list[LivePositionResponse] →
Rendered with OriginBadge
```

**Activity:**
```
Page load → useActivity → GET /activity →
WebhookSignal (filled, last 30d) [DB] +
DeploymentTrade [DB] →
Merged + sorted → paginated ActivityResponse →
Rendered with source badge
```

**Balance:**
```
Page load → useBrokerBalance → GET /balance →
broker.get_balance() [Exchange1 live] →
BrokerBalanceResponse { available, total, used_margin }
```

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Exchange1 auth fails on live-positions | Return 502 with `"Failed to fetch positions from broker"` |
| Exchange1 auth fails on balance | Return 502 with `"Failed to fetch balance from broker"` |
| No strategies linked to broker | `/activity` returns empty list, `/live-positions` still calls Exchange1 |
| Broker connection not found | 404 (existing behaviour, unchanged) |
| `broker.get_positions()` returns empty | `/live-positions` returns `[]`, page shows empty state |

---

## Files Changed

| File | Change |
|------|--------|
| `backend/app/brokers/schemas.py` | Add `used_margin` to `BrokerBalanceResponse`; add `LivePositionResponse`, `ActivityItemResponse`, `ActivityResponse` |
| `backend/app/brokers/router.py` | Enhance `/balance`; add `GET /{id}/live-positions`; add `GET /{id}/activity` |
| `frontend/lib/hooks/useApi.ts` | Add `useLivePositions`, `useActivity` hooks; update `useBrokerBalance` type |
| `frontend/components/brokers/OriginBadge.tsx` | New component |
| `frontend/app/(dashboard)/brokers/[id]/page.tsx` | Use `useLivePositions` for Positions tab; use `useActivity` for Activity tab; add balance to stats bar |

---

## Out of Scope

- Open Orders tab: not wired to Exchange1 (Exchange1 open orders list endpoint untested)
- Unrealized PNL: Exchange1 does not return this for futures positions
- Exchange-direct trade history: Exchange1 does not expose historical order fills via API
- Pagination on live-positions: Exchange1 returns all open positions in one call
