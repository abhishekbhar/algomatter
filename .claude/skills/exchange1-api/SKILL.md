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
      { "biz": {"name": "otc"},     "cryptoTotal": 0, "fiatTotal": 0, "total": 0, "currencies": [...] },
      { "biz": {"name": "options"}, "cryptoTotal": 0, "fiatTotal": 0, "total": 0, "currencies": [...] },
      { "biz": {"name": "cfd"},     "cryptoTotal": 0, "fiatTotal": 0, "total": 0, "currencies": [...] },
      { "biz": {"name": "asset"},   "cryptoTotal": 0, "fiatTotal": 0, "total": 0, "currencies": [...] },
      { "biz": {"name": "spot"},    "cryptoTotal": 0, "fiatTotal": 0, "total": 0, "currencies": [...] }
    ]
  }
}
```

Every account has **USD-equivalent aggregate fields**:
- `cryptoTotal` — USD value of crypto holdings in this account
- `fiatTotal` — USD value of fiat holdings in this account
- `total` — `cryptoTotal + fiatTotal`
- `acct_total` (adapter-computed) = `cryptoTotal + fiatTotal` — universal aggregate for all account types

| Biz | `product_type` param | Contents |
|-----|----------|----------|
| `cfd` | `"FUTURES"` | Futures margin — INR for India, USDT for Global 2 |
| `spot` | `"SPOT"` | Quote currencies (USDT, USDC, LINK…) — Global 2 only; India's is empty |
| `asset` | `"FUNDING"` | Funding wallet: base-token crypto + USDT — exchange UI "Funding" category |
| `options` | — | Options account (usually empty) |
| `otc` | — | OTC account (usually empty) |

⚠️ Base-token spot balances are in `asset`, **not** `spot`.

### Exchange UI ↔ Account mapping (verified)

**Global 2 observed totals:**
```
Funding  = asset.total  = 11.73 USD   (USDT + BTC/ETH dust in funding wallet)
Spot     = spot.total   = 100.49 USD  (USDT + USDC + LINK)
Futures  = cfd.total    = 209.69 USD
Total Est. Value        = 321.91 USD  ✓
```

**India observed totals:**
```
Futures  = cfd.total    = ~10.78 USD  (in INR: ~970 INR)
Funding  = asset.total  = ~0.0001 USD (dust only)
Spot     = spot.total   = 0           (empty — India keeps all money in cfd)
```

### Currency fields per account entry

Each entry in `currencies` has a `balance` object:

```json
{
  "displayCode": "USDT",
  "balance": {
    "available": 8.3195,
    "hold": 0.0,
    "margin": 2.4721,
    "profitUnreal": -0.2751,
    "total": 10.5165,
    "availableMargin": 8.3195
  }
}
```

| Field | Maps to | Notes |
|-------|---------|-------|
| `availableMargin` | `available` (futures) | Prefer over `available` for futures |
| `margin` | `used_margin` | Active margin in use — **NOT `hold`** |
| `hold` | `frozen_deposit` | Frozen/locked funds |
| `profitUnreal` | `unrealized_pnl` | Floating P&L |
| `total` | `total` | Per-currency total |

### Balance logic by product_type

**`"FUTURES"`** — `cfd` account, `availableMargin` field; India=INR, Global 2=USDT

**`"SPOT"`** — `spot.acct_total` (USD aggregate, Global 2); falls back to `asset` INR entry (India ~0)

**`"FUNDING"`** — `asset.acct_total` (USD aggregate); Global 2=~11.73 USD, India=~0 (dust)

### IP Allowlist

Exchange1 enforces server IP whitelisting per API key. If the production server IP is not whitelisted, the API returns HTTP 500 with body `{"data": "ip is error"}`. Fix: add `194.61.31.226` to the API key's allowed IPs in Exchange1 settings.

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
