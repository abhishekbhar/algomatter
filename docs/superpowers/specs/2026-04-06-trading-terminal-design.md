# Trading Terminal & Enhanced Manual Orders — Design Spec

## Goal

Add a dedicated `/trade` page with a full-screen trading terminal (live charts, watchlist, advanced order form) for standalone manual crypto trading, plus upgrade the existing deployment manual order modal with TP/SL and percentage-based sizing.

## Scope

Two features sharing a common foundation:

1. **`/trade` page** — Standalone trading terminal (not tied to deployments)
2. **Upgraded `ManualOrderModal`** — Enhanced order form on the deployment detail page

---

## 1. `/trade` Page

### Layout

3-column layout with bottom panel, full viewport height:

- **Left (180px fixed):** Watchlist — searchable list of crypto symbols with live prices and 24h change. Click to switch chart. Default set of popular pairs (BTC, ETH, SOL, XRP, BNB, ADA, DOGE). Active symbol highlighted.
- **Center (flex):** TradingView chart — candlestick chart using `lightweight-charts` library with volume bars and indicator support. Toolbar with symbol name, live price, 24h change, and interval selector (1m, 5m, 15m, 1h, 4h, 1d).
- **Right (280px fixed):** Order form — full-featured order entry panel (see Order Form section below).
- **Bottom (collapsible):** Trade history — tabs for "Open Orders" and "Trade History" showing standalone manual trades.

### Watchlist

- Displays symbol name, short name, last price, 24h % change
- Search/filter input at top
- Prices update in real-time via Binance WebSocket
- Click a symbol to load its chart and pre-fill order form
- Default symbols: BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, ADAUSDT, DOGEUSDT

### TradingView Chart

- Uses `lightweight-charts` npm package (TradingView's open-source library)
- Candlestick series with volume histogram
- Interval selector: 1m, 5m, 15m, 1h, 4h, 1d
- Historical data loaded via Binance REST API (`GET /api/v3/klines`)
- Real-time updates via Binance WebSocket kline stream
- When symbol or interval changes: unsubscribe old stream, load new historical data, subscribe to new stream

### Order Form (Standalone)

**Common fields (Spot & Futures):**
- **Broker selector** — dropdown of user's connected broker connections
- **Order type** — Limit, Market, Stop, Stop Limit
- **Price** — input field + slider (±5% from current market price). Slider for quick selection, input for exact values. Disabled for market orders.
- **Quantity** — input field + slider (0–100% of available balance, auto-calculates quantity)
- **Take Profit** — optional price field
- **Stop Loss** — optional price field
- **Total** — calculated display (price × quantity)
- **Available balance** — shown below submit button

**Spot mode:**
- BUY / SELL toggle
- All common fields above

**Futures mode (additional fields):**
- LONG / SHORT direction (UI labels only — mapped to BUY/SELL before calling `broker.place_order()`. LONG → BUY, SHORT → SELL. The broker adapters only accept BUY/SELL.)
- Margin mode — Isolated / Cross toggle
- Leverage — selector (1x to 125x)
- Trigger price — for stop and stop-limit orders
- Required margin — calculated display
- Available margin — from broker balance
- **Note:** Exchange1 futures currently only supports opening long positions (BUY=open-long, SELL=close-long). SHORT must be disabled in the UI when Exchange1 is the selected broker. Binance Testnet is spot-only so futures mode is disabled entirely for it.

**Submit button:** Shows contextual label — "Buy BTCUSDT", "Sell ETHUSDT", "Long BTCUSDT 10x", etc.

### Trade History (Bottom Panel)

Two tabs:
- **Open Orders** — active/pending orders with cancel button per row. Columns: Time, Symbol, Side, Type, Price, Qty, Filled, Action.
- **Trade History** — completed/cancelled orders with pagination. Columns: Time, Symbol, Side, Type, Price, Qty, Fill Price, Status.

**Loading & error states:** Show a spinner/skeleton while chart history loads. On fetch failure, show a retry prompt. Empty watchlist symbols gracefully show "No data available."

---

## 2. Upgraded ManualOrderModal (Deployment Page)

The existing modal at `/live-trading/[deploymentId]` gains these fields:

**New fields:**
- **Take Profit** — optional price
- **Stop Loss** — optional price
- **Trigger Price** — already exists in backend schema, just needs UI exposure. Shown when order type is stop/stop-limit.
- **Quantity slider** — 0–100% of portfolio balance (from `useDeploymentPosition`), auto-calculates quantity
- **Price slider** — ±5% from current market price for limit orders

**Not added (stays on `/trade` only):**
- Spot/futures toggle (inherits from deployment's `product_type`)
- Leverage/margin mode (set at deployment level)
- Broker selector (deployment already has a broker connection)

---

## 3. Backend

### New Database Table: `ManualTrade`

Separate from `DeploymentTrade` — standalone orders not tied to any deployment.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| tenant_id | UUID | FK to tenant |
| broker_connection_id | UUID | FK to broker_connection |
| symbol | String | e.g. BTCUSDT |
| exchange | String | e.g. EXCHANGE1, BINANCE |
| product_type | String | SPOT or FUTURES |
| action | String | BUY or SELL (LONG/SHORT are frontend labels mapped to BUY/SELL) |
| quantity | Float | Order quantity |
| order_type | String | MARKET, LIMIT, SL, SL-M |
| price | Float (nullable) | Limit price |
| trigger_price | Float (nullable) | Stop trigger price |
| leverage | Integer (nullable) | Futures leverage |
| position_model | String (nullable) | isolated or cross |
| take_profit | Float (nullable) | TP price |
| stop_loss | Float (nullable) | SL price |
| fill_price | Float (nullable) | Actual fill price |
| fill_quantity | Float (nullable) | Actual filled quantity |
| status | String | submitted, open, filled, rejected, cancelled, failed |
| broker_order_id | String (nullable) | ID from broker response |
| broker_symbol | String (nullable) | Symbol as known by broker (needed for cancel on Binance Testnet) |
| created_at | DateTime | Order creation time |
| updated_at | DateTime | Last status change time |
| filled_at | DateTime (nullable) | Fill time |

### New API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/trades/manual` | Place standalone manual order |
| GET | `/api/v1/trades/manual` | List manual trades (paginated, filterable by symbol/status) |
| POST | `/api/v1/trades/manual/{id}/cancel` | Cancel an open manual order |

### Manual Order Flow

1. Frontend sends order with `broker_connection_id` + full order params
2. Backend validates inputs, creates `ManualTrade` record with status `submitted`
3. Gets broker adapter via factory using the broker connection
4. Builds `OrderRequest` directly (do NOT use `translate_order` — it drops TP/SL fields). Include `take_profit`, `stop_loss`, `trigger_price` in the `OrderRequest`.
5. Calls `broker.place_order()` — returns an `OrderResponse` Pydantic model (use attribute access: `result.fill_price`, NOT `result.get("fill_price")`)
6. Updates `ManualTrade` record: if market order and filled → status `filled` with fill info. If limit order acknowledged → status `open`. If rejected → status `rejected`.
7. Stores `broker_order_id` and `broker_symbol` from the response for later cancel operations.
8. Returns response to frontend.

**Open order handling:** Limit orders that remain `open` after placement are displayed in the "Open Orders" tab. Status updates happen when the user refreshes or when the frontend polls the GET endpoint. No server-side polling of broker order status in v1 — this can be added later via a background worker.

### Existing Endpoint Change

`POST /api/v1/deployments/{id}/manual-order` — extend `ManualOrderRequest` schema to accept optional:
- `take_profit` (float, nullable) — **new**
- `stop_loss` (float, nullable) — **new**

Note: `trigger_price` already exists on `ManualOrderRequest`. The new fields must be passed through to `broker.place_order()` — the current code in `deployments/router.py` uses `translate_order()` which drops these fields, so the manual order path should build the `OrderRequest` directly instead. Also fix existing bug: `broker_result` is an `OrderResponse` Pydantic model, not a dict — use attribute access (`broker_result.fill_price`), not `.get()`.

### New Endpoint: Broker Balance

`GET /api/v1/brokers/{broker_connection_id}/balance` — Returns available balance and total equity for the selected broker connection. Used by the `/trade` page order form to show available balance and calculate percentage-based quantity.

### Broker Capabilities

The frontend needs to know which modes each broker supports to correctly enable/disable UI controls. Use a hardcoded client-side mapping:

```typescript
const BROKER_CAPABILITIES = {
  EXCHANGE1: { spot: true, futures: true, orderTypes: ["MARKET", "LIMIT"], shortFutures: false },
  BINANCE: { spot: true, futures: false, orderTypes: ["MARKET", "LIMIT", "SL", "SL-M"], shortFutures: false },
};
```

This disables: futures toggle for Binance Testnet, stop/stop-limit orders for Exchange1, SHORT direction for Exchange1 futures.

---

## 4. Real-Time Data (Binance WebSocket)

All market data comes from Binance public APIs — no auth required, no backend proxy.

### Price Ticker (Watchlist)

- Connect to `wss://stream.binance.com:9443/stream`
- Subscribe to `miniTicker` streams for all watchlist symbols
- Provides: last price, 24h price change %, 24h volume
- Updates ~1 second
- Single shared WebSocket connection

### Candlestick Data (Chart)

- **Historical:** REST `GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=500`
- **Real-time:** Subscribe to kline stream, e.g. `btcusdt@kline_15m`
- On symbol/interval change: unsubscribe old, fetch new history, subscribe new

### Reconnection

- Auto-reconnect on disconnect with exponential backoff (1s, 2s, 4s, max 30s)
- Visual disconnection indicator in UI

### Frontend Hook

`useBinanceWebSocket` — manages connection lifecycle, subscription management, reconnection, and cleanup. Used by both Watchlist and TradingChart components.

---

## 5. Navigation

New sidebar nav item: **"Trade"** at `/trade`. Positioned after "Live Trading" in the sidebar nav order (before "Webhooks").

---

## 6. New Files

### Frontend

| File | Purpose |
|------|---------|
| `app/(dashboard)/trade/page.tsx` | Trade page layout |
| `components/trade/Watchlist.tsx` | Symbol list with live prices |
| `components/trade/TradingChart.tsx` | TradingView lightweight-charts wrapper |
| `components/trade/OrderForm.tsx` | Full order form (spot/futures) |
| `components/trade/TradeHistory.tsx` | Open orders + history tabs |
| `lib/hooks/useBinanceWebSocket.ts` | WebSocket hook for Binance streams |
| `lib/hooks/useManualTrades.ts` | SWR hooks for manual trade CRUD |

### Frontend (Modified)

| File | Change |
|------|--------|
| `components/live-trading/ManualOrderModal.tsx` | Add TP/SL, trigger price, % slider |
| Sidebar/nav component | Add "Trade" nav item |

### Backend

| File | Purpose |
|------|---------|
| `app/manual_trades/router.py` | API endpoints for standalone trades |
| `app/manual_trades/schemas.py` | Request/response Pydantic models |
| `app/brokers/router.py` (modify) | Add `GET /brokers/{id}/balance` endpoint |
| `app/db/models.py` (modify) | Add ManualTrade model |
| Alembic migration `add_manual_trades_table` | Create manual_trades table |

### Dependencies

| Package | Source | Purpose |
|---------|--------|---------|
| `lightweight-charts` | npm | TradingView charting library |

---

## 7. Constraints & Notes

- **Exchange1** supports spot (MARKET, LIMIT) and futures (MARKET, LIMIT with leverage/TP/SL). Does NOT support stop/stop-limit orders.
- **Binance Testnet** supports spot only (MARKET, LIMIT, SL, SL-M).
- Order form should disable unsupported order types based on selected broker.
- **Currency display:** Watchlist and chart prices come from Binance and are in USDT — display them as USDT values (no ₹ conversion). The order form shows prices in USDT. Only broker balance/margin figures from Exchange1 may be in INR — display those with ₹. This avoids misleading currency mixing.
- No WebSocket needed from backend — all real-time data direct from Binance public API.
- Manual trades are completely independent of deployments and the strategy runner.
- **Binance WebSocket limits:** Max 5 subscribe messages/second, max 1024 streams per connection. Throttle subscribe/unsubscribe when switching symbols rapidly.
- **Cancel orders:** The cancel endpoint requires `broker_order_id` and `broker_symbol` (stored on `ManualTrade`). For Binance Testnet, `cancel_order` needs the symbol since broker instances are ephemeral (no persistent `_order_symbols` map).
- **Desktop-first layout:** The 3-column layout targets desktop viewports (min ~1200px width). Mobile/responsive layout is out of scope for v1.
