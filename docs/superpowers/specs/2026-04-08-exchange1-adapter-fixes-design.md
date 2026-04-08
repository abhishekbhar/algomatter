# Exchange1 Adapter Fixes Design

**Goal:** Fix six confirmed divergences between `exchange1.py` and the live Exchange1 API, and add short-position support via a new `position_side` field on `OrderRequest`.

**Architecture:** Targeted patch + futures routing refactor. `base.py` gains one optional field. `exchange1.py` replaces the two futures order methods with three cleaner ones dispatched from an explicit routing table. All other broker adapters and callers are unaffected (new field defaults to `None`).

**Evidence base:** Live order-placement test (2026-04-08) + Exchange1 OpenAPI docs at `https://openapi.exchange1.global/doc` + validation report at `docs/../review/exchange1_api_validation_report.md`.

---

## Divergences Being Fixed

| # | Issue | Root Cause | Fix |
|---|-------|-----------|-----|
| 1 | TP/SL on futures open causes `401 sign error` | `takeProfitPrice`/`stopLossPrice` are not accepted by Exchange1's `/futures/order/create` endpoint | Reject at adapter with clear error if either field is set |
| 2 | Partial close ignores `trigger_price` | `closeType` hardcoded to `"all"`, `trigger_price` never read | Use `trigger_price` as position ID in `closeType`; add `closeNum` |
| 3 | No short position support | `positionSide` hardcoded to `"long"` in `_open_futures_long`; no routing for short-open or short-close | Add `position_side` to `OrderRequest`; unified `_open_futures(order, side)` method |
| 4 | Uppercase status values not mapped | `_STATUS_MAP` uses lowercase keys; Exchange1 returns `"NEW"`, `"ENTRY"`, `"TRANSACTED"`, `"FREEZED"` | Lowercase raw state before map lookup; add missing key mappings |
| 5 | `get_positions` returns empty spot balances | Filters `account_type == "spot"` but base-token balances live under `"asset"` biz | Change filter to `account_type == "asset"` |
| 6 | SL / SL-M orders fail with 500 | Routed as `positionType=limit` but `price` only added when `order_type == "LIMIT"` → limit order sent without price | Add `price` whenever `positionType == "limit"` regardless of `order_type` |

---

## Schema Change — `base.py`

Add one optional field to `OrderRequest`:

```python
position_side: Literal["long", "short"] | None = None
```

- `None` means "use default for this action" — all existing callers unchanged.
- Ignored entirely for spot orders.

---

## Futures Routing Table

Replaces the current `BUY → open long / SELL → close long` binary:

| `action` | `position_side` | API endpoint | `positionSide` sent |
|----------|----------------|-------------|---------------------|
| BUY | None / "long" | `/futures/order/create` | long |
| SELL | "short" | `/futures/order/create` | short |
| SELL | None / "long" | `/futures/order/close` | — |
| BUY | "short" | `/futures/order/close` | — |

---

## Method Changes — `exchange1.py`

### Removed
- `_open_futures_long(order)` — replaced by `_open_futures(order, position_side)`

### Added
- `_open_futures(order, position_side: str) -> OrderResponse`
  - Accepts `"long"` or `"short"` as `position_side`
  - **Rejects immediately** if `order.take_profit` or `order.stop_loss` is set:
    `"Exchange1 does not support take_profit/stop_loss at order creation time. Remove them or configure TP/SL on the Exchange1 platform after the order is placed."`
  - Adds `price` to body when `order_type != "MARKET"` (covers LIMIT, SL, SL-M)
  - Body: `{symbol, positionType, positionSide, quantity, quantityUnit, positionModel, leverage, [price]}`
  - Order ID encoded as `futures:{positionType}:{symbol}:{raw_id}` — unchanged

### Modified
- `_place_futures_order(order)` — implement the 4-row dispatch table above
- `_close_futures_position(order)` → renamed `_close_futures(order)`
  - When `order.trigger_price` is set and non-zero: `closeType = str(order.trigger_price)`, add `closeNum: str(order.quantity)`
  - Otherwise: `closeType = "all"` (unchanged)
- `get_order_status(order_id)` — lowercase raw state before `_STATUS_MAP` lookup
- `_STATUS_MAP` — add: `"entry": "open"`, `"transacted": "filled"`, `"freezed": "open"`
- `get_positions()` — change `account_type != "spot"` → `account_type != "asset"`

---

## Test Changes — `test_exchange1.py`

### Fix `_BALANCE_RESPONSE` fixture
Update from flat list to nested accounts format matching `_get_balance_data`'s parser:

```python
_BALANCE_RESPONSE = {
    "code": 200,
    "data": {
        "accounts": [
            {
                "biz": {"name": "asset"},
                "currencies": [
                    {"displayCode": "BTC", "balance": {"available": "0.5", "hold": "0.1", "total": "0.6", "availableMargin": "0.5"}},
                    {"displayCode": "ETH", "balance": {"available": "10.0", "hold": "0.0", "total": "10.0", "availableMargin": "10.0"}},
                    {"displayCode": "SOL", "balance": {"available": "0.0", "hold": "0.0", "total": "0.0", "availableMargin": "0.0"}},
                ],
            },
            {
                "biz": {"name": "spot"},
                "currencies": [
                    {"displayCode": "USDT", "balance": {"available": "5000.00", "hold": "1000.00", "total": "6000.00", "availableMargin": "5000.00"}},
                    {"displayCode": "USDC", "balance": {"available": "2000.00", "hold": "0.0", "total": "2000.00", "availableMargin": "2000.00"}},
                ],
            },
            {
                "biz": {"name": "cfd"},
                "currencies": [
                    {"displayCode": "USDT", "balance": {"available": "0.0", "hold": "0.0", "total": "0.0", "availableMargin": "0.0"}},
                ],
            },
        ]
    },
}
```

### New tests to add (`TestOrders`)
- `test_open_futures_short` — `SELL + position_side="short"` → `/futures/order/create` body has `positionSide=short`
- `test_close_futures_short` — `BUY + position_side="short"` → `/futures/order/close`
- `test_futures_tp_rejected` — futures order with `take_profit` set → `status=rejected`, message contains "take_profit"
- `test_futures_sl_rejected` — futures order with `stop_loss` set → `status=rejected`, message contains "stop_loss"
- `test_futures_partial_close` — `trigger_price` set → `closeType=<trigger_price>`, `closeNum` in body
- `test_futures_sl_order_type_includes_price` — `order_type="SL"` → body includes `price` field

### New tests (`TestCancelAndStatus`)
- `test_get_order_status_uppercase_entry` — `state="ENTRY"` → `status="open"`
- `test_get_order_status_uppercase_transacted` — `state="TRANSACTED"` → `status="filled"`

### Updated tests (`TestPortfolio`)
- `test_get_positions_excludes_quote_and_zero` — update fixture expectation: BTC and ETH from "asset" account
- `test_get_positions_fields` — same
- `test_get_holdings` — same
- `test_account_cache_prevents_duplicate_calls` — same
- `test_get_balance_extracts_usdt` — balance comes from "spot" USDT entry

---

## Test Changes — `test_brokers.py`

Add tests covering the new routing:
- `test_futures_short_open_routes_to_create` — verifies `positionSide=short` in request body
- `test_futures_short_close_routes_to_close` — verifies `/futures/order/close` is called for `BUY + position_side="short"`
- `test_futures_tp_sl_rejected_before_api_call` — no HTTP call made when TP/SL present

---

## What Is Not Changed

- Spot order endpoints (`/spot/order/create`, `/spot/order/close`) — live tests confirm they work; report's claim that `spot/order/close` doesn't exist is incorrect per API docs and confirmed live usage
- RSA signing logic — unchanged
- Order ID encoding format — unchanged (cancel compatibility preserved)
- All callers of `place_order` outside the broker layer — `position_side` defaults to `None`, no changes needed
