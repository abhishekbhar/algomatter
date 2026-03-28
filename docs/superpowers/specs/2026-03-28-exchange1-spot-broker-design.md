# Exchange1 Spot Broker Adapter — Design Spec

## Overview

Add an `Exchange1Broker` adapter that connects AlgoMatter to the Exchange1 Global spot trading API (`https://www.exchange1.global`) for executing trades. Implements the full `BrokerAdapter` ABC interface. Historical kline data falls back to Binance's public API since Exchange1 only provides klines via WebSocket.

## Motivation

AlgoMatter currently has `SimulatedBroker` (paper trading) and `BinanceTestnetBroker` (testnet). Adding Exchange1 provides a real production exchange adapter for spot trading. This follows the same patterns established by the Binance adapter.

## Architecture

### New Files

| File | Purpose |
|------|---------|
| `backend/app/brokers/exchange1.py` | `Exchange1Broker` class implementing `BrokerAdapter` |

### Modified Files

| File | Change |
|------|--------|
| `backend/app/brokers/factory.py` | Add `"exchange1"` case to `get_broker()` |
| `backend/app/brokers/__init__.py` | Re-export `Exchange1Broker` |
| `frontend/app/(dashboard)/brokers/new/page.tsx` | Add `exchange1` to `BROKER_FIELDS` and dropdown |

### New Test Files

| File | Purpose |
|------|---------|
| `backend/tests/test_exchange1.py` | Unit tests with `respx` mocking |

### No Changes Needed

- No new runtime dependencies (`cryptography` already present for RSA, `httpx` for HTTP)
- No DB migration (existing `broker_connections` table with `broker_type` string column)
- No changes to `BrokerAdapter` ABC or data models

## Backend: `Exchange1Broker`

### Authentication & Signing

Exchange1 uses RSA (SHA256WithRSA) request signing, unlike Binance's HMAC-SHA256:

1. Credentials stored as `{"api_key": "...", "private_key": "..."}` (PEM format, encrypted in DB)
2. Every signed request:
   - Sets `X-SAASAPI-API-KEY` header with the API key
   - Sets `X-SAASAPI-TIMESTAMP` header with epoch milliseconds
   - Sets `X-SAASAPI-RECV-WINDOW` header (default `5000`)
   - Builds signature payload string: `timestamp + api_key + recv_window + sorted_params`
   - Parameters sorted by key ASCII ascending, formatted as `key1=value1&key2=value2`
   - Empty/null values excluded from parameter string
   - Signs payload with SHA256WithRSA using the private key
   - Base64 encodes the signature → `X-SAASAPI-SIGN` header
3. Uses `cryptography` library for RSA signing (already a project dependency)

```python
def _build_signed_headers(self, params: dict) -> dict[str, str]:
    """Build all four required auth headers for a signed request.
    Returns a dict with X-SAASAPI-API-KEY, X-SAASAPI-TIMESTAMP,
    X-SAASAPI-RECV-WINDOW, and X-SAASAPI-SIGN."""
    timestamp = str(int(time.time() * 1000))
    # Filter empty values, sort by key ASCII ascending
    filtered = {k: v for k, v in params.items() if v is not None and v != ""}
    sorted_params = "&".join(f"{k}={v}" for k, v in sorted(filtered.items()))
    payload = f"{timestamp}{self._api_key}{self._recv_window}{sorted_params}"

    signature = self._private_key_obj.sign(
        payload.encode(),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return {
        "X-SAASAPI-API-KEY": self._api_key,
        "X-SAASAPI-TIMESTAMP": timestamp,
        "X-SAASAPI-RECV-WINDOW": self._recv_window,
        "X-SAASAPI-SIGN": base64.b64encode(signature).decode(),
        "Content-Type": "application/json",
    }
```

The `_get()` and `_post()` HTTP helpers call `_build_signed_headers(params)` to get the complete header dict, ensuring the timestamp used in the signature always matches the timestamp sent in the header.

### `authenticate` vs `verify_connection`

- **`authenticate(credentials)`**: Stores `api_key` and `private_key`, loads RSA private key object, creates `httpx.AsyncClient`, calls `POST /openapi/v1/token` to validate credentials. Returns `True` on success, `False` on auth failure.
- **`verify_connection()`**: Calls `GET /openapi/v1/balance` as a lightweight authenticated check. Returns `True` if successful.

### Endpoint Mapping

| BrokerAdapter Method | Exchange1 REST Endpoint | Signed? |
|---------------------|------------------------|---------|
| `authenticate(credentials)` | `POST /openapi/v1/token` | Yes |
| `verify_connection()` | `GET /openapi/v1/balance` | Yes |
| `place_order(order)` | `POST /openapi/v1/spot/order/create` (BUY) or `POST /openapi/v1/spot/order/close` (SELL) | Yes |
| `cancel_order(order_id)` | `POST /openapi/v1/spot/order/cancel` | Yes |
| `get_order_status(order_id)` | `GET /openapi/v1/spot/order/detail?id=order_id` | Yes |
| `get_positions()` | `GET /openapi/v1/balance` → non-zero balances | Yes |
| `get_holdings()` | `GET /openapi/v1/balance` → non-zero balances | Yes |
| `get_balance()` | `GET /openapi/v1/balance` → USDT available/hold/total | Yes |
| `get_quotes(symbols)` | `GET /openapi/v1/spot/orderbook?symbol=X` per symbol | No |
| `get_historical(...)` | Binance `GET https://api.binance.com/api/v3/klines` (public, no auth) | No |

### Order Mapping

AlgoMatter `OrderRequest` → Exchange1 `POST /openapi/v1/spot/order/create` (BUY) or `/close` (SELL):

| AlgoMatter Field | Exchange1 Param | Mapping |
|-----------------|-----------------|---------|
| `symbol` | `symbol` | Lowercase (e.g., `BTCUSDT` → `btcusdt`) |
| `action` | _(determines endpoint)_ | `BUY` → `/order/create`, `SELL` → `/order/close` |
| `order_type` | `positionType` | `MARKET` → `market`, `LIMIT` → `limit` |
| `quantity` | `quantity` (BUY) / `closeNum` (SELL) | Decimal → string |
| `price` | `price` | Only for LIMIT orders, Decimal → string |
| `exchange` | _(ignored)_ | Adapter always uses `EXCHANGE1` in responses |
| `product_type` | _(ignored)_ | Spot only; callers should pass `"DELIVERY"` (webhook router already defaults to this) |
| `trigger_price` | _(not supported)_ | Exchange1 spot has no stop-loss order type; ignored |

BUY request body:
```json
{
  "symbol": "btcusdt",
  "positionType": "market",
  "quantity": "0.001",
  "quantityUnit": "cont"
}
```

SELL request body:
```json
{
  "symbol": "btcusdt",
  "positionType": "market",
  "closeNum": "0.001"
}
```

For LIMIT orders, add `"price": "66000.00"` to both.

The `quantityUnit` field is always `"cont"` for spot BUY orders (represents the asset quantity in contracts/coins).

### Cancel Order

`cancel_order(order_id)` sends `POST /openapi/v1/spot/order/cancel` with body:

```json
{
  "id": "855188"
}
```

The `id` parameter is the order ID string returned from `place_order`. Unlike Binance, Exchange1 cancel does not require a `symbol` parameter for spot orders, so no internal `_order_symbols` mapping is needed.

Response: `{"code": 200, "msg": "success"}` on success. Fully filled orders cannot be cancelled and return an error code.

### Response Mapping

Exchange1 order response → AlgoMatter `OrderResponse`:

| Exchange1 Field | AlgoMatter Field | Mapping |
|----------------|-----------------|---------|
| `data` (order ID) | `order_id` | `str(data)` |
| `code` | `status` | `200` → `"filled"` (market) or `"open"` (limit); else `"rejected"` |
| `msg` | `message` | Error message string |

### Order Status Mapping

`get_order_status(order_id)` calls `GET /openapi/v1/spot/order/detail?id=order_id`.

Exchange1 `state` → AlgoMatter status (`_STATUS_MAP`):

```python
_STATUS_MAP = {
    "new": "open",
    "partially_filled": "open",
    "filled": "filled",
    "cancelled": "cancelled",
    "canceled": "cancelled",      # handle both spellings
    "rejected": "rejected",
    "expired": "cancelled",
}
```

Any unrecognized state defaults to `"open"`.

Order detail response field mapping → `OrderStatus`:

| Exchange1 Field | AlgoMatter Field | Mapping |
|----------------|-----------------|---------|
| `state` | `status` | Via `_STATUS_MAP` above |
| `tradePrice` or `estimatedPrice` | `fill_price` | `Decimal(str(value))`, `Decimal("0")` if absent |
| `doneQuantity` | `fill_quantity` | `Decimal(str(value))`, `Decimal("0")` if absent |
| `quantity - doneQuantity` | `pending_quantity` | Computed, `Decimal("0")` if fully filled |

Since Exchange1 may not return fill price/quantity in the initial create response for market orders, `fill_price` and `fill_quantity` will be `Decimal("0")` in the `place_order` response. The actual fill details are available via `get_order_status`.

### Balance

`GET /openapi/v1/balance` returns an accounts array with currency balances. Extract USDT balance:
- `available` → `Balance.available`
- `hold` → `Balance.used_margin`
- `total` → `Balance.total`

### Positions & Holdings

Exchange1 spot doesn't have a "positions" concept. Derived from account balances (same approach as Binance adapter):
- `get_positions()`: Non-zero balances (excluding USDT) as `Position` objects with `exchange="EXCHANGE1"`, `action="BUY"`, `entry_price=Decimal("0")` (no cost basis tracking)
- `get_holdings()`: Same data mapped to `Holding` objects
- Quote assets excluded: `USDT`, `USDC`

### Account Call Deduplication

Same pattern as Binance adapter: `_get_balance()` with 2-second TTL cache. Shared by `get_positions()`, `get_holdings()`, `get_balance()`.

### Quotes (Orderbook)

`get_quotes(symbols)` calls `GET /openapi/v1/spot/orderbook?symbol=X` for each symbol (lowercase). Returns best bid/ask from the orderbook response:
- `asks[0][0]` → ask price
- `bids[0][0]` → bid price
- Mid price as the quote price

If the orderbook is empty (no asks or no bids) for a symbol, the quote for that symbol is skipped (not included in the returned list). This handles illiquid pairs gracefully.

### Historical Data (Binance Fallback)

`get_historical()` calls Binance public API `GET https://api.binance.com/api/v3/klines` (no authentication required, production endpoint, not testnet). Same interval mapping and pagination logic as `BinanceTestnetBroker`. This is clearly documented in the code with comments explaining the cross-exchange fallback.

Interval mapping (same as Binance):
- `"1m"`, `"5m"`, `"15m"`, `"1h"`, `"4h"`, `"1d"`, `"1w"` → same strings

Pagination: Binance returns max 1000 candles per request. If range exceeds 1000, paginate by advancing `startTime`.

### Error Handling

- `code != 200` in response body → `OrderResponse(status="rejected", message=msg)` for order endpoints; raise `RuntimeError(msg)` for non-order endpoints
- HTTP 5xx or network errors → raise `httpx.HTTPStatusError` (caller handles retry)
- HTTP 429 → log warning via `structlog`, raise so caller can retry
- Use `structlog` for all logging (consistent with codebase)

### HTTP Client Lifecycle

- `httpx.AsyncClient` created in `authenticate()`, stored as `self._client`
- Base URL: `https://www.exchange1.global`
- Separate Binance client created lazily for `get_historical()` only: `https://api.binance.com`
- Binance client stored as `self._binance_client`, reused across `get_historical()` calls
- Timeout: 10s default
- `close()` shuts down both clients, clears private key from memory
- Note: `close()` is not defined in the `BrokerAdapter` ABC but is required by the webhook router (`finally: await broker.close()`) and the broker factory (cleanup on auth failure). Implemented as a concrete method, same as the Binance adapter.

## Backend: Broker Factory Update

Add `"exchange1"` case to `app/brokers/factory.py`:

```python
case "exchange1":
    broker = Exchange1Broker()
    authenticated = await broker.authenticate(credentials)
    if not authenticated:
        await broker.close()
        raise RuntimeError("Failed to authenticate with Exchange1")
    return broker
```

This matches the existing error-handling pattern used by the `binance_testnet` case.

## Frontend Changes

In `frontend/app/(dashboard)/brokers/new/page.tsx`:

1. Add to `BROKER_FIELDS`:
   ```typescript
   exchange1: ["api_key", "private_key"],
   ```

2. Add to dropdown:
   ```tsx
   <option value="exchange1">Exchange1</option>
   ```

## Testing Strategy

- **Unit tests** with `respx` to verify:
  - RSA signing produces valid signatures (known test vector with test RSA key pair)
  - Sorted parameter string construction
  - Order placement maps fields correctly (BUY → create, SELL → close)
  - LIMIT vs MARKET order params
  - Error responses produce `status="rejected"`
  - Balance parsing extracts USDT correctly
  - Positions exclude quote assets
  - Account cache deduplication avoids duplicate requests
  - Orderbook quotes return mid price
  - Historical data delegates to Binance with correct params
  - `cancel_order` sends correct body
  - `get_order_status` maps state correctly
  - `close()` clears private key from memory

## Security Considerations

- RSA private key encrypted at rest (AES-256-GCM, per-tenant derived keys) — no changes needed
- Private key never logged or returned in API responses
- `close()` method clears `self._private_key` and `self._api_key` from memory
- Base URL hardcoded to `https://www.exchange1.global` (not configurable)
