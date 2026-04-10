---
name: exchange1-api
description: Use when working with the Exchange1 broker adapter, placing or cancelling orders, reading balances or positions, checking order status, or debugging Exchange1 API errors. Also use when the Exchange1 OpenAPI docs are needed.
---

# Exchange1 API Reference

**Docs:** https://openapi.exchange1.global/doc
**Adapter:** `backend/app/brokers/exchange1.py`
**Base URL:** `https://www.exchange1.global/openapi/v1`

---

## Authentication

Every signed request requires these headers:

| Header | Value |
|--------|-------|
| `X-SAASAPI-API-KEY` | API key |
| `X-SAASAPI-TIMESTAMP` | UTC milliseconds |
| `X-SAASAPI-SIGN` | SHA256WithRSA signature (Base64) |
| `X-SAASAPI-RECV-WINDOW` | Validity window (optional) |

**Signature payload:** filter empty values + `sign`, sort params by ASCII, concatenate as `key=value&...`, sign with RSA private key.

---

## Futures Endpoints

### Open position
`POST /openapi/v1/futures/order/create`

| Field | Values | Notes |
|-------|--------|-------|
| `symbol` | `btc`, `eth`, … | lowercase |
| `positionType` | `limit` / `market` | SL and SL-M also map to `limit` |
| `positionSide` | `long` / `short` | |
| `positionModel` | `cross` / `fix` | `fix` = isolated; requires per-symbol wallet |
| `leverage` | `"10"` | string |
| `quantity` | `"1"` | string, ≥1 contract |
| `quantityUnit` | `cont` | |
| `price` | `"65000"` | **required whenever `positionType=limit`** (includes SL/SL-M) |

⚠️ **`takeProfitPrice` / `stopLossPrice` are NOT accepted** — causes `401 sign error`. Reject at adapter before calling the API.

### Close position
`POST /openapi/v1/futures/order/close`

| Field | Values | Notes |
|-------|--------|-------|
| `symbol` | `btc` | |
| `positionType` | `limit` / `market` | |
| `closeType` | `"all"` or position ID | position ID = numeric string from `/futures/order/positions` |
| `closeNum` | `"2"` | required when `closeType` is a position ID |
| `price` | `"65000"` | required when `positionType=limit` |

### Cancel order
`POST /openapi/v1/futures/order/cancel`
Body: `{ id, symbol, positionType }` — all three required.

Order IDs are encoded as `futures:{positionType}:{symbol}:{raw_id}` in the adapter.

### Query open orders
`GET /openapi/v1/futures/order/current?page=1&pageSize=50&positionModel=cross|fix`
Response rows are under `data.rows` (not `data.list`).

### Query positions
`GET /openapi/v1/futures/order/positions?page=1&pageSize=10&positionModel=cross|fix`

---

## Spot Endpoints

### Create order
`POST /openapi/v1/spot/order/create`
Fields: `symbol`, `positionType`, `quantity`, `quantityUnit`, `price`

### Close/sell
`POST /openapi/v1/spot/order/close`
Fields: `symbol`, `positionType`, `quantity`, `margin`, `spreadsRate`

### Cancel
`POST /openapi/v1/spot/order/cancel`
Body: `{ id }` only (no symbol/positionType needed).

### Order detail
`GET /openapi/v1/spot/order/detail?id=<id>`
State field returns **uppercase**: `NEW`, `ENTRY`, `TRANSACTED`, `FREEZED`, `CANCELLED`.

---

## Balance / Account

`GET /openapi/v1/balance`

Response structure:
```json
{
  "data": {
    "accounts": [
      { "biz": {"name": "asset"}, "currencies": [...] },
      { "biz": {"name": "spot"},  "currencies": [...] },
      { "biz": {"name": "cfd"},   "currencies": [...] }
    ]
  }
}
```

| Biz | Contents |
|-----|----------|
| `asset` | Base-token holdings (BTC, ETH, SOL) — use for `get_positions` |
| `spot` | Quote currencies (USDT, USDC) — use for `get_balance` |
| `cfd` | Futures margin (USDT) |

⚠️ Base-token spot balances are in `asset`, **not** `spot`.

---

## Order States

Exchange1 returns **uppercase** states. Always `.lower()` before map lookup.

| Raw state | Mapped status |
|-----------|--------------|
| `NEW` | `open` |
| `ENTRY` | `open` |
| `FREEZED` | `open` |
| `PARTIALLY_FILLED` | `open` |
| `TRANSACTED` | `filled` |
| `FILLED` | `filled` |
| `CANCELLED` / `CANCELED` | `cancelled` |

---

## Error Codes

| Code | Meaning |
|------|---------|
| 9257 | No isolated-margin wallet for symbol — fund it or switch to cross |
| 9001 | Contract not found |
| 9006 | Below minimum order quantity (≥1 contract) |
| 9008 | Insufficient margin |
| 9016 | Parameter error |
| 9030 | Exceeded max position limit |
| 10015 | Leverage error |

---

## Adapter Dispatch Table

```
BUY  + long (default) → _open_futures(order, "long")   → /futures/order/create
SELL + short          → _open_futures(order, "short")  → /futures/order/create
SELL + long (default) → _close_futures(order)          → /futures/order/close
BUY  + short          → _close_futures(order)          → /futures/order/close
```

`position_side` on `OrderRequest` defaults to `None` (treated as `"long"`).

---

## Key Constraints

- Cannot close the same position within **30 seconds**
- Batch endpoints: max **20 orders** per call
- WebSocket: GZIP-compressed; server pings every 5s; disconnect after 60s inactivity
- All timestamps: UTC milliseconds
