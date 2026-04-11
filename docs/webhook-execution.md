# Webhook Execution — Single Leg & Dual Leg

## Overview

A webhook signal travels through five stages before an order reaches the broker:

```
HTTP POST /api/v1/webhook/{token}
        │
        ▼
1. Token auth + tenant lookup
        │
        ▼
2. Signal mapping   (raw payload → StandardSignal via JSONPath)
        │
        ▼
3. Rules evaluation (whitelist / blacklist / max_positions / trading_hours)
        │
        ▼
4. Order execution  (single-leg OR dual-leg)
        │
        ▼
5. DB write         (WebhookSignal row with result + detail)
```

---

## 1. Token Auth

- URL token is SHA-256 hashed and compared to `users.webhook_token_hash`
- Tenant ID resolved from the matched user row
- All subsequent DB queries are RLS-scoped to that tenant

---

## 2. Signal Mapping

The strategy's `mapping_template` JSON is applied to the raw webhook payload.

Values prefixed with `$.` are JSONPath references into the payload:

```json
// mapping_template
{
  "exchange": "EXCHANGE1",
  "product_type": "FUTURES",
  "symbol": "$.symbol",
  "action": "$.action",
  "quantity": "$.qty",
  "order_type": "MARKET",
  "leverage": 20
}

// incoming payload
{ "action": "buy", "qty": 1 }

// resolved StandardSignal
{
  "exchange": "EXCHANGE1",
  "product_type": "FUTURES",
  "symbol": "BTCUSDT",
  "action": "BUY",
  "quantity": 1,
  "order_type": "MARKET",
  "leverage": 20
}
```

`StandardSignal` fields:

| Field | Type | Notes |
|---|---|---|
| `symbol` | str | e.g. `BTCUSDT` |
| `exchange` | str | e.g. `EXCHANGE1` |
| `action` | str | `BUY` or `SELL` |
| `quantity` | Decimal | number of contracts |
| `order_type` | str | `MARKET`, `LIMIT`, `SL` |
| `price` | Decimal? | required when order_type=LIMIT |
| `product_type` | str | `FUTURES` or `DELIVERY` |
| `leverage` | int? | e.g. 20 |
| `position_model` | str? | `cross` or `isolated` |
| `position_side` | str? | `long` or `short` (set by executor for dual-leg) |
| `take_profit` | Decimal? | not supported by Exchange1 at order time |
| `stop_loss` | Decimal? | not supported by Exchange1 at order time |

---

## 3. Rules Evaluation

Evaluated in `webhooks/processor.py::evaluate_rules()`.

| Rule | Pass condition |
|---|---|
| `symbol_whitelist` | signal.symbol in list (empty = allow all) |
| `symbol_blacklist` | signal.symbol NOT in list |
| `max_positions` | current open positions < limit |
| `max_signals_per_day` | signals today < limit |
| `trading_hours` | now() within start–end in given timezone |

Open positions and daily signal count are tracked in Redis:
- `strategy:{id}:positions` — incremented on BUY fill, decremented on SELL fill
- `strategy:{id}:signals_today` — incremented on any fill, TTL until midnight IST

If any rule fails → `rule_result="blocked_by_rule"`, no order placed.

---

## 4a. Single-Leg Execution (dual_leg.enabled = false)

```
signal → _place_live_order() → broker.place_order() → Exchange1 API
```

`_place_live_order`:
1. Fetches `BrokerConnection` from DB (AES-256-GCM decrypt credentials)
2. Builds `OrderRequest` from `StandardSignal`
3. Calls `broker.place_order(order_req)`
4. On success: increments Redis position count + signals today
5. Returns `(execution_result, execution_detail)`

Exchange1 dispatch (`_place_futures_order`):

```
action=BUY  + position_side="long"  (or None) → _open_futures("long")   → POST /futures/order/create
action=SELL + position_side="short"            → _open_futures("short")  → POST /futures/order/create
action=SELL + position_side="long"  (or None)  → _close_futures()        → POST /futures/order/close
action=BUY  + position_side="short"            → _close_futures()        → POST /futures/order/close
```

Single-leg does not set `position_side` — it uses whatever comes from the mapping template (usually `None`). Most strategies just send BUY/SELL and rely on the default "long" routing.

**execution_result values:**

| Value | Meaning |
|---|---|
| `filled` | Order confirmed filled by Exchange1 |
| `accepted` | Order accepted (limit orders) |
| `rejected` | Exchange1 rejected the order (see message) |
| `broker_error` | Exception during API call |
| `broker_not_found` | No matching BrokerConnection in DB |
| `no_broker_connection` | Strategy has no broker assigned |
| `no_active_session` | Paper mode but no active paper session |

---

## 4b. Dual-Leg Execution (dual_leg.enabled = true)

Dual-leg implements a **close-then-open** reversal pattern. Each signal closes the existing opposite position before opening a new one. Position state is tracked in Redis, not queried from the broker.

### Redis State

```
strategy:{id}:dual_leg_side   → "long" | "short" | "" (empty = no position)
strategy:{id}:dual_leg_trades  → integer trade count (resets at midnight IST)
```

### Decision Logic

```python
existing_side  = Redis state
new_side       = "long" if action=="BUY" else "short"
same_side      = (existing_side == new_side)
stop           = trade_count >= max_trades  OR  outside trading_hours

need_close = existing_side != ""  AND  (stop OR existing_side != new_side)
need_open  = NOT stop  AND  (existing_side == "" OR existing_side != new_side)
```

| Scenario | need_close | need_open | Outcome |
|---|---|---|---|
| No existing position, not stopped | false | true | `opened` |
| Opposite position exists, not stopped | true | true | `reversed` |
| Same position exists, not stopped | false | false | `no_action` |
| Any position exists, stopped | true | false | `closed` |
| Close fails (not 9012) | true | — | `close_failed` |
| Open fails | true | true | `open_failed` |

### Close Leg

The close leg constructs a signal that triggers `_close_futures` on the broker:

```python
# Closing a long → SELL + None (defaults to "long") → _close_futures
# Closing a short → BUY + "short"                   → _close_futures
close_action = "SELL" if existing_side == "long" else "BUY"
close_side   = None   if existing_side == "long" else "short"
```

Exchange1's close endpoint (`POST /futures/order/close`) uses `closeType="all"` — closes the full open position.

**9012 "position not found" is treated as success** — position was already closed externally. Execution continues to the open leg.

### Open Leg

The open leg sets `position_side=new_side` explicitly before calling the broker:

```python
open_signal = signal.model_copy(update={"position_side": new_side})
```

This ensures the broker dispatch routes to `_open_futures`:
- BUY + `position_side="long"` → `_open_futures("long")`
- SELL + `position_side="short"` → `_open_futures("short")`

Without setting `position_side`, a SELL signal with `position_side=None` would default to "long" and call `_close_futures` instead of opening a short — the bug fixed on 2026-04-11.

### Redis Updates (after open leg fills)

```python
set_dual_leg_position(redis, strategy_id, new_side)   # "long" or "short"
increment_dual_leg_trade_count(redis, strategy_id)    # +1 toward max_trades
increment_signals_today(redis, strategy_id)           # daily counter
```

### Full Dual-Leg Flow (example: BUY → SELL reversal)

```
State: existing_side="long" (from previous BUY)
Signal: { action: "SELL" }

1. need_close=true, need_open=true

2. Close leg:
   close_signal = { action:"SELL", position_side:None }
   → broker: SELL + long(default) → _close_futures → POST /futures/order/close
   → Exchange1: closes the long position
   → Redis: clear dual_leg_side

3. Open leg:
   open_signal = { action:"SELL", position_side:"short" }
   → broker: SELL + "short" → _open_futures("short") → POST /futures/order/create
   → Exchange1: opens a new short position
   → Redis: dual_leg_side="short", dual_leg_trades+=1

4. execution_result = "reversed"
   execution_detail = {
     "close": { "order_id": "futures:market:btc:...", "status": "filled", ... },
     "open":  { "order_id": "futures:market:btc:...", "status": "filled", ... }
   }
```

### execution_result values (dual-leg)

| Value | Meaning |
|---|---|
| `opened` | No prior position; open leg placed successfully |
| `reversed` | Closed opposite + opened new side |
| `closed` | Closed position but did not open (stop condition) |
| `close_failed` | Close leg rejected (not 9012); open leg aborted |
| `open_failed` | Close succeeded; open leg rejected |
| `no_action` | Same side already open; nothing to do |

---

## 5. DB Write

`WebhookSignal` row written by the router (not executor):

| Column | Value |
|---|---|
| `raw_payload` | Original JSON body |
| `parsed_signal` | StandardSignal as dict |
| `rule_result` | `passed` / `blocked_by_rule` / `mapping_error` / `no_mapping_template` |
| `rule_detail` | Reason string (when blocked) |
| `execution_result` | See tables above |
| `execution_detail` | JSON with order IDs, fill prices, error messages |
| `processing_ms` | Total time from receipt to DB write |

---

## Latency Profile (observed)

| Stage | Typical time |
|---|---|
| Webhook receipt → order started | ~21–25ms |
| Exchange1 API call (open/close) | ~650–860ms |
| DB write | ~2–8ms |
| **Total end-to-end** | **~700–900ms** |

All latency is in the Exchange1 API round trip. Internal processing is <30ms.
