# Live Trading Section — Design Spec

## Overview

A dedicated Live Trading section providing a command center for all active deployments, individual deployment drill-down with trade monitoring, manual trading controls, live performance analytics, and backtest-vs-live comparison.

**Route:** `/live-trading` (command center) and `/live-trading/[deploymentId]` (detail)

---

## 1. Data Model

### New Table: `DeploymentTrade`

Structured trade records for live/paper deployments. Replaces parsing `DeploymentLog` messages for trade history.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default uuid4 | |
| tenant_id | UUID | FK → users.id, NOT NULL, INDEX | RLS |
| deployment_id | UUID | FK → strategy_deployments.id, NOT NULL, INDEX, ondelete CASCADE | |
| order_id | String(32) | NOT NULL | Strategy-assigned order ID |
| broker_order_id | String(64) | NULLABLE | Broker-assigned ID after submission |
| action | String(10) | NOT NULL | BUY or SELL |
| quantity | Numeric | NOT NULL | |
| order_type | String(10) | NOT NULL | MARKET, LIMIT, SL-M, SL |
| price | Numeric | NULLABLE | Requested price (limit/stop-limit) |
| trigger_price | Numeric | NULLABLE | Trigger (stop/stop-limit) |
| fill_price | Numeric | NULLABLE | Actual fill price |
| fill_quantity | Numeric | NULLABLE | Actual filled quantity |
| status | String(20) | NOT NULL, default "submitted" | submitted, filled, partially_filled, cancelled, rejected |
| is_manual | Boolean | NOT NULL, default false | Distinguishes manual vs strategy orders |
| realized_pnl | Numeric | NULLABLE | PnL realized on this trade |
| created_at | DateTime(tz) | server_default now() | |
| filled_at | DateTime(tz) | NULLABLE | |

**RLS policy:** Same pattern as other tables — `tenant_id = current_setting('app.current_tenant')::uuid`.

### Modify Existing: `DeploymentResponse`

Add `strategy_name` field to `DeploymentResponse` schema (and `_to_response()` helper in the deployment router). This requires eager-loading or joining the `StrategyCode.name` via the existing `strategy_code` relationship on `StrategyDeployment`. The frontend needs this to display strategy names on cards without a separate lookup.

### Integration with Existing Models

- `order_router.dispatch_orders()` writes a `DeploymentTrade` row on each order dispatch (status="submitted") and updates on fill (status="filled", fill_price, fill_quantity, filled_at, realized_pnl). Import `DeploymentTrade` in `order_router.py`. The session is already passed into `dispatch_orders()` by `tick_runner.run_tick()` — the caller is responsible for committing after the function returns.
- Manual order endpoints also write here with `is_manual=true`.
- `DeploymentState.open_orders` (JSON) continues to be the subprocess protocol's state — `DeploymentTrade` is the source of truth for history.

---

## 2. Backend API Endpoints

### New Endpoints

#### `POST /api/v1/deployments/{deployment_id}/manual-order`

Place a manual order through a deployment's broker connection.

**Request:**
```json
{
  "action": "buy",
  "quantity": 1.0,
  "order_type": "market",
  "price": null,
  "trigger_price": null
}
```

**Logic:**
1. Verify deployment exists, belongs to tenant, is running or paused
2. Verify deployment mode is "paper" or "live" (no manual orders on backtests)
3. Translate order using `order_router.translate_order()`
4. For live: dispatch through broker via `order_router.dispatch_orders()`
5. For paper: record as submitted (simulated fill)
6. Write `DeploymentTrade` with `is_manual=true`
7. Return trade record

**Response:** `201` with `DeploymentTradeResponse`

#### `POST /api/v1/deployments/{deployment_id}/cancel-order`

Cancel a specific pending order.

**Request:**
```json
{
  "order_id": "abc123"
}
```

**Logic:**
1. Verify deployment ownership
2. Find order in `DeploymentState.open_orders` by order_id
3. For live: call `broker.cancel_order(broker_order_id)`
4. Update `DeploymentTrade` status to "cancelled"
5. Remove from `DeploymentState.open_orders`

**Response:** `200` with updated trade record

#### `GET /api/v1/deployments/{deployment_id}/trades`

Get trade history for a deployment.

**Query params:** `offset` (default 0), `limit` (default 50), `is_manual` (optional bool filter)

**Response:**
```json
{
  "trades": [DeploymentTradeResponse],
  "total": 150,
  "offset": 0,
  "limit": 50
}
```

#### `GET /api/v1/deployments/{deployment_id}/position`

Get current position and P&L for a deployment.

**Response:**
```json
{
  "deployment_id": "...",
  "position": { "quantity": 1.0, "avg_entry_price": 105.0, "unrealized_pnl": 2.5 } | null,
  "portfolio": { "balance": 10000, "equity": 10250, "available_margin": 9750 },
  "open_orders_count": 2,
  "total_realized_pnl": 450.0
}
```

Source: `DeploymentState` for position/portfolio, aggregated `DeploymentTrade` for realized PnL.

#### `GET /api/v1/deployments/{deployment_id}/metrics`

Compute live performance metrics from trade history.

**Response:**
```json
{
  "total_return": 4.5,
  "win_rate": 62.5,
  "profit_factor": 1.8,
  "sharpe_ratio": 1.2,
  "max_drawdown": 3.1,
  "total_trades": 24,
  "avg_trade_pnl": 18.75,
  "best_trade": 125.0,
  "worst_trade": -45.0
}
```

**Logic:**
- For completed backtests: return stored `StrategyResult.metrics`
- For paper/live: compute from `DeploymentTrade` records using `compute_metrics()` from `app.analytics.metrics`. Note: `compute_metrics()` does not currently return `best_trade` or `worst_trade` — these two fields must be computed separately from the trade records (max/min of `realized_pnl`). Do NOT modify `compute_metrics()` to avoid side effects on existing backtest results.
- Build equity curve on-the-fly from chronological trade PnLs + initial capital from `deployment.config`

#### `GET /api/v1/deployments/{deployment_id}/comparison`

Compare backtest metrics vs current deployment metrics. Only available when deployment has a promotion chain back to a backtest.

**Response:**
```json
{
  "backtest": { "total_return": 12.5, "win_rate": 65, ... },
  "current": { "total_return": 8.3, "win_rate": 58, ... },
  "deltas": { "total_return": -4.2, "win_rate": -7, ... },
  "backtest_deployment_id": "...",
  "promotion_chain": ["backtest-id", "paper-id", "live-id"]
}
```

**Logic:** Walk `promoted_from_id` chain until reaching a backtest deployment. Fetch its `StrategyResult.metrics`. Compute current metrics from `DeploymentTrade`. Calculate deltas.

**Response:** `404` if no backtest found in promotion chain. `200` with comparison data.

#### `GET /api/v1/deployments/aggregate-stats`

Aggregate stats across all active deployments for the current user.

**Response:**
```json
{
  "total_deployed_capital": 50000,
  "aggregate_pnl": 1250.50,
  "aggregate_pnl_pct": 2.5,
  "active_deployments": 3,
  "todays_trades": 12
}
```

**Logic:**
- Sum `portfolio.equity` from `DeploymentState` for all running/paused deployments
- Sum initial capital from deployment configs for `total_deployed_capital`
- Aggregate P&L = total equity - total deployed capital
- Count today's `DeploymentTrade` records

#### `GET /api/v1/deployments/recent-trades`

Get recent trades across all active deployments for the current user. Avoids N separate API calls on the command center.

**Query params:** `limit` (default 20)

**Response:**
```json
{
  "trades": [DeploymentTradeResponse],
  "total": 150
}
```

**Logic:** Query `DeploymentTrade` for all deployments belonging to the current tenant, ordered by `created_at DESC`, limited.

### Modified Endpoint

#### `POST /api/v1/deployments/stop-all` (enhanced)

Current behavior: stops all active deployments.

**Enhancement:** Also cancel all open orders for each stopped deployment. For live deployments, call `broker.cancel_order()` for each open order. Update corresponding `DeploymentTrade` records to "cancelled".

The current endpoint returns `list[DeploymentResponse]` (response_model). Change response_model to `StopAllResponse` (defined in Section 3). This is a **breaking change** — update the frontend caller at the same time.

```json
{
  "deployments": [DeploymentResponse, ...],
  "orders_cancelled": 7
}
```

---

## 3. Backend Schemas

### New Pydantic Models

```python
class ManualOrderRequest(BaseModel):
    action: str  # buy or sell
    quantity: float
    order_type: str = "market"  # market, limit, stop, stop_limit
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
    strategy_name: str  # Joined from StrategyDeployment → StrategyCode.name
    symbol: str  # From StrategyDeployment.symbol

class TradesResponse(BaseModel):
    trades: list[DeploymentTradeResponse]
    total: int
    offset: int
    limit: int

class PositionResponse(BaseModel):
    deployment_id: str
    position: dict | None
    portfolio: dict
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
    best_trade: float | None  # None when zero trades
    worst_trade: float | None  # None when zero trades

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

### Modified Schema

Add `strategy_name: str` field to the existing `DeploymentResponse` in `app/deployments/schemas.py`. Update `_deployment_to_response()` helper to populate it via eager-loaded `deployment.strategy_code.name`.

---

## 4. Strategy Runner Integration

### `order_router.dispatch_orders()` Changes

After dispatching each order (paper or live), write a `DeploymentTrade` record:

```python
trade = DeploymentTrade(
    tenant_id=deployment.tenant_id,
    deployment_id=deployment.id,
    order_id=order["id"],
    action=order["action"].upper(),
    quantity=order["quantity"],
    order_type=ORDER_TYPE_MAP.get(order.get("order_type", "market"), "MARKET"),
    price=order.get("price"),
    trigger_price=order.get("trigger_price"),
    status="submitted",
    is_manual=False,
)
session.add(trade)
```

For live fills, update the trade record when the broker confirms:
```python
trade.status = "filled"
trade.fill_price = broker_result.get("fill_price")
trade.fill_quantity = broker_result.get("fill_quantity")
trade.broker_order_id = broker_result.get("order_id")
trade.filled_at = datetime.now(timezone.utc)
```

Paper mode: immediately mark as filled with the current candle close as fill_price.

### PnL Calculation

Realized PnL is computed when a position-closing trade fills:
- Track position via `DeploymentState.position`
- On sell (closing a long): `realized_pnl = (fill_price - avg_entry_price) * fill_quantity`
- On buy (closing a short): `realized_pnl = (avg_entry_price - fill_price) * fill_quantity`

---

## 5. Frontend: Pages

### Command Center (`/live-trading`)

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│ Live Trading                          [Kill Switch 🔴]  │
│ Filters: [All ▾] [Running ▾]                           │
├──────────┬──────────┬──────────┬──────────┐             │
│ Deployed │ Total    │ Active   │ Today's  │             │
│ Capital  │ P&L      │ Deploy.  │ Trades   │             │
│ ₹50,000  │ +₹1,250  │ 3        │ 12       │             │
├──────────┴──────────┴──────────┴──────────┘             │
│                                                         │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
│ │ BTCUSDT     │ │ ETHUSDT     │ │ NIFTY       │       │
│ │ 🟢 live     │ │ 🟡 paper    │ │ 🟢 live     │       │
│ │ P&L: +₹500  │ │ P&L: +₹320  │ │ P&L: +₹430  │       │
│ │ 8 trades    │ │ 4 trades    │ │ 12 trades   │       │
│ │ Last: 2m ago│ │ Last: 1m ago│ │ Last: 5m ago│       │
│ └─────────────┘ └─────────────┘ └─────────────┘       │
│                                                         │
│ Recent Trades                                           │
│ ┌──────────────────────────────────────────────────┐   │
│ │ Time    Strategy  Symbol  Action  Qty  Price  P&L │   │
│ │ 14:05   SMA Bot   BTCUSDT BUY     1    67200  —  │   │
│ │ 14:00   RSI Bot   ETHUSDT SELL    2    3150  +85 │   │
│ │ ...                                               │   │
│ └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**Data sources:**
- Stats: `GET /api/v1/deployments/aggregate-stats` (2s polling)
- Deployment cards: `GET /api/v1/deployments?status=running` + `GET /api/v1/deployments?status=paused` (2s polling)
- Recent trades: `GET /api/v1/deployments/recent-trades?limit=20` (5s polling)
- Position info per card: `GET /api/v1/deployments/{id}/position` (2s polling) — note: this is N requests for N deployments; acceptable for ≤5 active deployments per user (current limit), but if limits increase consider a batched endpoint

**Components:**
- `AggregateStats` — 4 StatCards in a row
- `LiveDeploymentCard` — Card with strategy name, symbol, mode/status badges, P&L, trade count, last tick time, click to navigate
- `RecentTradesTable` — DataTable showing merged trades across deployments
- `KillSwitchButton` — Red button opening ConfirmModal, calls stop-all

### Deployment Detail (`/live-trading/[deploymentId]`)

**Layout:**
```
┌───────────────────────────────────────────────────────────┐
│ SMA Crossover  [paper 🟡] [running 🟢]                    │
│                            [Pause] [Stop] [Promote] [Kill]│
├───────────────────────────────┬───────────────────────────┤
│                               │ [Analytics] [Compare]     │
│ Position                      │ [Logs] [Config]           │
│ ┌───────────────────────────┐ │                           │
│ │ BTCUSDT LONG 1.0 @ 67200 │ │ Analytics Tab:            │
│ │ Unrealized P&L: +₹150    │ │ ┌─────────┬────────────┐ │
│ │           [Close Position]│ │ │ Return  │ Win Rate   │ │
│ └───────────────────────────┘ │ │ +4.5%   │ 62.5%      │ │
│                               │ │ PF      │ Sharpe     │ │
│ Pending Orders                │ │ 1.8     │ 1.2        │ │
│ ┌───────────────────────────┐ │ │ MaxDD   │ Trades     │ │
│ │ LIMIT BUY 1 @ 66500 [✕]  │ │ │ -3.1%   │ 24         │ │
│ │ [Place Order]             │ │ └─────────┴────────────┘ │
│ └───────────────────────────┘ │                           │
│                               │ Cumulative P&L Chart     │
│ Trade History                 │ ┌───────────────────────┐ │
│ ┌───────────────────────────┐ │ │ ╱‾‾╲   ╱‾‾‾‾╲       │ │
│ │ Time  Action Qty Price PnL│ │ │╱    ╲_╱      ╲╱‾‾   │ │
│ │ 14:05 BUY   1  67200  —  │ │ └───────────────────────┘ │
│ │ 13:55 SELL  1  67350 +150│ │                           │
│ │ 13:30 BUY   1  67200  —  │ │ Compare Tab (if promoted):│
│ │ ...               [More] │ │ Metric  | BT   | Live    │
│ └───────────────────────────┘ │ Return  | 12.5 | 8.3     │
│                               │ WinRate | 65%  | 58%     │
│                               │ ...                       │
├───────────────────────────────┴───────────────────────────┤
```

**Data sources:**
- Deployment: `useDeployment(id)` (2s polling)
- Position: `GET /api/v1/deployments/{id}/position` (2s polling)
- Trades: `GET /api/v1/deployments/{id}/trades` (5s polling)
- Metrics: `GET /api/v1/deployments/{id}/metrics` (10s polling)
- Comparison: `GET /api/v1/deployments/{id}/comparison` (no polling, fetch once)
- Logs: existing `useDeploymentLogs` hook

---

## 6. Frontend: Components

### New Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `KillSwitchButton` | `components/live-trading/KillSwitchButton.tsx` | Red button with ConfirmModal, calls stop-all or stop+cancel for single deployment |
| `ManualOrderModal` | `components/live-trading/ManualOrderModal.tsx` | Form: action, quantity, order_type, price, trigger_price with confirmation step |
| `PositionCard` | `components/live-trading/PositionCard.tsx` | Shows current position, unrealized P&L, "Close Position" button |
| `PendingOrdersList` | `components/live-trading/PendingOrdersList.tsx` | List of open orders with per-order cancel button, "Place Order" button |
| `TradeHistoryTable` | `components/live-trading/TradeHistoryTable.tsx` | Paginated DataTable of DeploymentTrade records, manual badge |
| `LiveDeploymentCard` | `components/live-trading/LiveDeploymentCard.tsx` | Card for command center grid — strategy name, symbol, badges, P&L, trades, last tick |
| `MetricsGrid` | `components/live-trading/MetricsGrid.tsx` | 2×4 grid of metric values using StatCard |
| `ComparisonTable` | `components/live-trading/ComparisonTable.tsx` | Side-by-side table: Metric / Backtest / Live / Delta with color-coded deltas |
| `AggregateStats` | `components/live-trading/AggregateStats.tsx` | 4 StatCards for command center top bar |

### Reused Components

- `DeploymentBadge` — mode + status badges (already exists)
- `LogViewer` — paginated logs (already exists)
- `EquityCurve` — chart component (already exists, used for cumulative P&L)
- `StatCard` — stat display (already exists)
- `DataTable` — sortable table (already exists)
- `ConfirmModal` — confirmation dialog (already exists)

---

## 7. Frontend: Types & Hooks

### New Types (add to `frontend/lib/api/types.ts`)

Also update the existing `Deployment` interface to add `strategy_name: string`.

```typescript
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

export interface PositionInfo {
  deployment_id: string;
  position: { quantity: number; avg_entry_price: number; unrealized_pnl: number } | null;
  portfolio: { balance: number; equity: number; available_margin: number };
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
```

### New Hooks (add to `frontend/lib/hooks/useApi.ts`)

```typescript
export function useAggregateStats() {
  return useApiGet<AggregateStats>("/api/v1/deployments/aggregate-stats", { refreshInterval: 2000 });
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

---

## 8. Navigation

Update `frontend/components/layout/Sidebar.tsx` to add:

```typescript
{ icon: MdTrendingUp, label: "Live Trading", href: "/live-trading" },
```

Position after "Hosted Strategies" and before "Webhooks".

Import `MdTrendingUp` from `react-icons/md`.

---

## 9. Coexistence with Existing Features

- The existing Paper Trading section (`/paper-trading`) remains unchanged — it serves webhook-driven strategies with simulated sessions
- The Live Trading section covers hosted strategy deployments in both paper and live modes
- The existing deployments page at `/strategies/hosted/[id]/deployments` remains as a strategy-scoped view; Live Trading is a cross-strategy operations view
- The existing `POST /api/v1/deployments/stop-all` endpoint is enhanced (cancel orders) with a new `StopAllResponse` response shape — this is a breaking change, update the frontend caller at the same time

---

## 10. What's NOT Included (YAGNI)

- WebSocket/real-time push — polling at 2-5s is sufficient for 5min+ cron strategies
- Risk dashboard / exposure tracking — can be added later
- Notifications / alerts system — can be added later
- Activity feed — logs + trades table covers this
- Multi-symbol per strategy — single symbol per deployment constraint remains
- Position sizing / risk management rules — strategy code handles this
