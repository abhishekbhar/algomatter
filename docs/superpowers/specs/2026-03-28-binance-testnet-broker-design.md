# Binance Testnet Broker Adapter — Design Spec

## Overview

Add a `BinanceTestnetBroker` adapter that connects AlgoMatter to the Binance Spot Test Network (`https://testnet.binance.vision/api`) for executing trades with virtual funds. Implements the full `BrokerAdapter` ABC interface.

## Motivation

AlgoMatter currently only has a `SimulatedBroker` (in-memory paper trading). Adding the Binance testnet broker provides a real exchange environment with order books, market data, and execution — without risking real funds. This is the first live-exchange adapter and establishes the pattern for future broker integrations.

## Architecture

### New Files

| File | Purpose |
|------|---------|
| `backend/app/brokers/binance_testnet.py` | `BinanceTestnetBroker` class implementing `BrokerAdapter` |
| `backend/app/brokers/factory.py` | Async broker factory: resolves `broker_type` string → authenticated adapter instance |

### Modified Files

| File | Change |
|------|--------|
| `frontend/app/(dashboard)/brokers/new/page.tsx` | Add `binance_testnet` to `BROKER_FIELDS` and dropdown |
| `backend/app/brokers/__init__.py` | Re-export `BinanceTestnetBroker` and `get_broker` |
| `backend/app/webhooks/router.py` | Add `elif strategy.mode == "live"` branch for live broker dispatch |

### No Changes Needed

- No new runtime dependencies (uses `httpx` + stdlib `hmac`/`hashlib`)
- No DB migration (existing `broker_connections` table with `broker_type` string column)
- No changes to `BrokerAdapter` ABC or data models

### New Test Dependencies

- `respx` added to `pyproject.toml` `[project.optional-dependencies] dev`

## Backend: `BinanceTestnetBroker`

### Authentication & Signing

Binance testnet uses HMAC-SHA256 request signing:

1. Credentials stored as `{"api_key": "...", "api_secret": "..."}` (encrypted in DB)
2. Every signed request:
   - Adds `timestamp` param (epoch ms, with server time offset applied)
   - Computes `signature = HMAC-SHA256(api_secret, query_string)`
   - Appends `signature` as the **last** query param
   - Sets `X-MBX-APIKEY` header
3. Optional `recvWindow` param (default 5000ms) controls request validity window

```python
def _sign(self, params: dict) -> dict:
    params["timestamp"] = int(time.time() * 1000) + self._time_offset_ms
    query = urlencode(params)
    sig = hmac.new(self._secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    params["signature"] = sig
    return params
```

### `authenticate` vs `verify_connection`

- **`authenticate(credentials)`**: Stores `api_key` and `api_secret`, creates `httpx.AsyncClient`, calls `GET /api/v3/time` to compute clock offset (`self._time_offset_ms`), then calls `GET /api/v3/account` to validate credentials. Returns `True` on success, `False` on auth failure.
- **`verify_connection()`**: Lightweight health check — calls `GET /api/v3/ping` (unsigned). Does not require valid credentials. Used for connectivity checks.

### Order ID → Symbol Tracking

Binance's `DELETE /api/v3/order` and `GET /api/v3/order` both require `symbol` alongside `orderId`. Since the `BrokerAdapter` ABC only passes `order_id` to `cancel_order` and `get_order_status`, the adapter maintains an internal `dict[str, str]` mapping `order_id → symbol`, populated during `place_order`. If the order_id is not found in the map, these methods raise `ValueError`.

### Endpoint Mapping

| BrokerAdapter Method | Binance REST Endpoint | Signed? |
|---------------------|----------------------|---------|
| `authenticate(credentials)` | `GET /api/v3/time` + `GET /api/v3/account` | Yes |
| `verify_connection()` | `GET /api/v3/ping` | No |
| `place_order(order)` | `POST /api/v3/order` | Yes |
| `cancel_order(order_id)` | `DELETE /api/v3/order` (symbol from internal map) | Yes |
| `get_order_status(order_id)` | `GET /api/v3/order` (symbol from internal map) | Yes |
| `get_positions()` | `GET /api/v3/account` → non-zero balances | Yes |
| `get_holdings()` | `GET /api/v3/account` → non-zero balances | Yes |
| `get_balance()` | `GET /api/v3/account` → USDT/USDC free + locked | Yes |
| `get_quotes(symbols)` | `GET /api/v3/ticker/24hr?symbol=X` per symbol | No |
| `get_historical(...)` | `GET /api/v3/klines` (paginated if >1000 candles) | No |

### Account Call Deduplication

`get_positions()`, `get_holdings()`, and `get_balance()` all call `GET /api/v3/account`. To avoid redundant API calls, the adapter uses a shared `_get_account_info()` method with a short-lived cache (2 second TTL). The cache stores the response and a timestamp; if the cached response is less than 2s old, it is reused.

### Order Mapping

AlgoMatter `OrderRequest` → Binance `POST /api/v3/order` params:

| AlgoMatter Field | Binance Param | Mapping |
|-----------------|---------------|---------|
| `symbol` | `symbol` | Pass through (e.g., `BTCUSDT`) |
| `action` | `side` | `"BUY"` → `"BUY"`, `"SELL"` → `"SELL"` |
| `order_type` | `type` | See order type mapping below |
| `quantity` | `quantity` | Decimal → string |
| `price` | `price` | Only for LIMIT orders, Decimal → string |
| `exchange` | _(ignored)_ | Adapter always uses `BINANCE_TESTNET` in responses |
| `product_type` | _(ignored)_ | Binance spot has no product type distinction; callers should pass `"DELIVERY"` |
| `trigger_price` | `stopPrice` | For stop-loss order types |

Order type mapping:
- `"MARKET"` → Binance `"MARKET"`
- `"LIMIT"` → Binance `"LIMIT"` with `timeInForce=GTC`
- `"SL"` → Binance `"STOP_LOSS_LIMIT"` with `stopPrice` + `price` + `timeInForce=GTC`
- `"SL-M"` → Binance `"STOP_LOSS"` with `stopPrice`

### Response Mapping

Binance order response → AlgoMatter `OrderResponse`:

| Binance Field | AlgoMatter Field | Mapping |
|--------------|-----------------|---------|
| `orderId` | `order_id` | `str(orderId)` |
| `status` | `status` | See status mapping below |
| `executedQty` | `fill_quantity` | Decimal |
| `cummulativeQuoteQty / executedQty` | `fill_price` | Weighted avg fill price |

Binance status → AlgoMatter status:
- `"FILLED"` → `"filled"`
- `"NEW"` → `"open"`
- `"PARTIALLY_FILLED"` → `"open"` (closest match; `fill_quantity` reflects partial fill)
- `"CANCELED"` → `"cancelled"`
- `"REJECTED"` → `"rejected"`
- `"EXPIRED"` → `"cancelled"`

### Positions & Holdings

Binance spot doesn't have a "positions" concept. We derive them from account balances:

- `get_positions()`: Returns non-zero balances (excluding quote assets) as `Position` objects with `exchange="BINANCE_TESTNET"`, `action="BUY"`, `entry_price=Decimal("0")` (Binance doesn't track cost basis)
- `get_holdings()`: Same as positions, mapped to `Holding` objects
- `get_balance()`: Sum of `USDT` and `USDC` balances only — `free` → `available`, `locked` → `used_margin`, `free + locked` → `total`

### Historical Data / Klines

`GET /api/v3/klines` interval mapping:

| AlgoMatter Interval | Binance Interval |
|--------------------|-----------------|
| `"1m"`, `"5m"`, `"15m"`, `"1h"`, `"4h"`, `"1d"`, `"1w"` | Same strings (Binance-compatible) |

- `start` and `end` datetime objects converted to epoch ms via `int(dt.timestamp() * 1000)`
- Binance returns max 1000 candles per request. If the requested range exceeds 1000 candles at the given interval, the adapter paginates: fetch 1000, advance `startTime` to last candle's close time, repeat until `endTime` reached or no more data
- Binance returns arrays: `[openTime, open, high, low, close, volume, ...]` → mapped to `OHLCV` models

### Quotes

`get_quotes(symbols)` calls `GET /api/v3/ticker/24hr?symbol=X` for each symbol individually. This is simpler and avoids fetching all tickers. For lists > 10 symbols, consider batching with no-symbol call and filtering, but for MVP the per-symbol approach is sufficient.

### Error Handling

- HTTP 4xx with `{"code": -XXXX, "msg": "..."}` → `OrderResponse(status="rejected", message=msg)` for order endpoints; raise `RuntimeError(msg)` for non-order endpoints
- HTTP 5xx or network errors → raise `httpx.HTTPStatusError` (caller handles retry)
- HTTP 429 (rate limit) → parse `Retry-After` header if present, log warning via `structlog`, raise so caller can retry. No automatic retry in the adapter itself.
- Use `structlog` for all logging (consistent with codebase)

### HTTP Client Lifecycle

- `httpx.AsyncClient` created in `authenticate()`, stored as `self._client`
- Base URL: `https://testnet.binance.vision` (hardcoded, not configurable)
- Timeout: 10s default
- Client reused across requests for connection pooling
- Adapter provides `async def close()` to shut down the client and clear `self._secret` from memory

### Clock Sync

During `authenticate()`, the adapter calls `GET /api/v3/time` and computes `self._time_offset_ms = server_time - local_time`. This offset is applied in `_sign()` to prevent authentication failures from clock drift. Binance rejects requests where timestamp is >1000ms off from server time.

## Backend: Broker Factory

`app/brokers/factory.py`:

```python
async def get_broker(broker_type: str, credentials: dict) -> BrokerAdapter:
    match broker_type:
        case "binance_testnet":
            broker = BinanceTestnetBroker()
            await broker.authenticate(credentials)
            return broker
        case _:
            raise ValueError(f"Unknown broker type: {broker_type}")
```

The factory is `async` and calls `authenticate()` internally, returning a ready-to-use adapter. This avoids the error-prone two-step initialization pattern. The `SimulatedBroker` is not included — it is only used by backtesting and paper trading, which instantiate it directly with their own `initial_capital`.

## Backend: Webhook Processor Integration

The webhook router (`app/webhooks/router.py`) currently handles `strategy.mode == "paper"` only. Add an `elif strategy.mode == "live"` branch:

```python
elif strategy.mode == "live":
    if not strategy.broker_connection_id:
        execution_result = "no_broker_connection"
    else:
        from app.brokers.factory import get_broker
        from app.crypto.encryption import decrypt_credentials
        from app.db.models import BrokerConnection

        bc_result = await session.execute(
            select(BrokerConnection).where(
                BrokerConnection.id == strategy.broker_connection_id
            )
        )
        bc = bc_result.scalar_one_or_none()
        if not bc:
            execution_result = "broker_connection_not_found"
        else:
            creds = decrypt_credentials(user.id, bc.credentials)
            broker = await get_broker(bc.broker_type, creds)
            try:
                order_req = OrderRequest(
                    symbol=signal.symbol,
                    exchange="BINANCE_TESTNET",
                    action=signal.action,
                    quantity=signal.quantity,
                    order_type=signal.order_type or "MARKET",
                    price=signal.price or Decimal("0"),
                    product_type="DELIVERY",
                    trigger_price=signal.trigger_price,
                )
                result = await broker.place_order(order_req)
                execution_result = result.status  # short string for String(50) column
                execution_detail = result.model_dump(mode="json")  # full response in JSON column
            except Exception as exc:
                execution_result = "broker_error"
                execution_detail = {"error": str(exc)}
            finally:
                await broker.close()
```

This code path: looks up the `BrokerConnection`, decrypts credentials, instantiates the adapter via the factory, places the order, and stores the status string in `execution_result` (String(50) column) and the full order response dict in `execution_detail` (JSON column).

## Frontend Changes

In `frontend/app/(dashboard)/brokers/new/page.tsx`:

1. Add to `BROKER_FIELDS`:
   ```typescript
   binance_testnet: ["api_key", "api_secret"],
   ```

2. Add to dropdown:
   ```tsx
   <option value="binance_testnet">Binance Testnet</option>
   ```

## Testing Strategy

- **Unit tests** with `respx` (httpx mock) to verify:
  - HMAC signing produces correct signatures (known test vector)
  - Clock offset is applied correctly
  - Order placement maps fields correctly for all 4 order types
  - `PARTIALLY_FILLED` maps to `"open"`
  - Error responses (4xx) produce `status="rejected"`
  - Kline pagination works for >1000 candles
  - Account call caching avoids duplicate requests
  - `cancel_order` / `get_order_status` use internal order_id→symbol map
- **Integration test** (optional, hits real testnet, skipped in CI):
  - `authenticate()` with valid testnet keys returns True
  - `verify_connection()` returns True
  - `get_balance()` returns non-zero (testnet has virtual funds)
- `respx` added to `pyproject.toml` under `[project.optional-dependencies] dev`

## Security Considerations

- API keys encrypted at rest (AES-256-GCM, per-tenant derived keys) — no changes needed
- Secret never logged or returned in API responses
- `close()` method clears `self._secret` from memory
- Testnet only — no risk of real fund loss
- Base URL hardcoded to testnet (not configurable) to prevent accidental production use
