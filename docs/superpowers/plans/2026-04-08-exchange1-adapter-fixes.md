# Exchange1 Adapter Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix six confirmed divergences in `exchange1.py` from the live Exchange1 API and add short-position support via a new `position_side` field on `OrderRequest`.

**Architecture:** Targeted patch + futures routing refactor. `base.py` gains one optional field. `exchange1.py` replaces `_open_futures_long` + `_close_futures_position` with three clean methods dispatched from an explicit routing table. Existing callers are unaffected — `position_side` defaults to `None`. No DB migrations, no frontend changes.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, Pydantic v2, httpx, respx (test mocking), pytest-asyncio.

---

## Context for implementers

The Exchange1 broker adapter lives at `backend/app/brokers/exchange1.py`. It handles RSA-signed requests to the Exchange1 Global trading API. `OrderRequest` is defined in `backend/app/brokers/base.py` and is shared across all broker adapters.

Run tests from `backend/` with the virtualenv active:
```bash
cd backend
source .venv/bin/activate    # or: nix develop (from algomatter/)
pytest tests/test_exchange1.py tests/test_brokers.py -v
```

Six bugs are being fixed:
1. `takeProfitPrice`/`stopLossPrice` in signed body → 401 sign error from Exchange1
2. Partial close ignores `trigger_price`, always sends `closeType: "all"`
3. Only long positions supported (no shorts)
4. Status map uses lowercase keys; Exchange1 returns uppercase ("NEW", "ENTRY", "TRANSACTED")
5. `get_positions` looks in "spot" biz account; base-token balances live in "asset" biz
6. `SL`/`SL-M` order types map to `positionType=limit` but never add `price` → Exchange1 500

Additionally, several pre-existing test bugs in `test_brokers.py` are fixed as part of this work.

---

## File Structure

| File | What changes |
|------|-------------|
| `backend/app/brokers/base.py` | Add `position_side: Literal["long","short"] \| None = None` to `OrderRequest` |
| `backend/app/brokers/exchange1.py` | Replace `_open_futures_long` + `_close_futures_position` with `_open_futures(order, side)` + `_close_futures(order)`; update `_place_futures_order` dispatch; fix status map; fix `get_positions` |
| `backend/tests/test_exchange1.py` | Fix `_BALANCE_RESPONSE` fixture (flat list → nested accounts); update portfolio tests; add tests for short, TP/SL rejection, partial close, uppercase status |
| `backend/tests/test_brokers.py` | Fix pre-existing broken tests (wrong order ID format, wrong positionModel, TP/SL test inverted); add short-position routing tests |

---

## Task 1: Add `position_side` to `OrderRequest`

**Files:**
- Modify: `backend/app/brokers/base.py:21-37`
- Modify: `backend/tests/test_brokers.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_brokers.py` after the existing simulated broker tests:

```python
def test_order_request_position_side_defaults_to_none():
    order = OrderRequest(
        symbol="BTCUSDT", exchange="EXCHANGE1", action="BUY",
        quantity=Decimal("1"), order_type="LIMIT", price=Decimal("60000"),
        product_type="FUTURES",
    )
    assert order.position_side is None


def test_order_request_position_side_accepts_long_and_short():
    long_order = OrderRequest(
        symbol="BTCUSDT", exchange="EXCHANGE1", action="BUY",
        quantity=Decimal("1"), order_type="LIMIT", price=Decimal("60000"),
        product_type="FUTURES", position_side="long",
    )
    short_order = OrderRequest(
        symbol="BTCUSDT", exchange="EXCHANGE1", action="SELL",
        quantity=Decimal("1"), order_type="MARKET", price=Decimal("0"),
        product_type="FUTURES", position_side="short",
    )
    assert long_order.position_side == "long"
    assert short_order.position_side == "short"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_brokers.py::test_order_request_position_side_defaults_to_none tests/test_brokers.py::test_order_request_position_side_accepts_long_and_short -v
```

Expected: `FAILED` with `ValidationError` or `TypeError` — `position_side` doesn't exist yet.

- [ ] **Step 3: Add `position_side` to `OrderRequest` in `base.py`**

In `backend/app/brokers/base.py`, the `OrderRequest` class currently ends at line ~37. Add one field after `stop_loss`:

```python
class OrderRequest(BaseModel):
    """Incoming order to be placed with a broker."""

    symbol: str
    exchange: str
    action: Literal["BUY", "SELL"]
    quantity: Decimal
    order_type: Literal["MARKET", "LIMIT", "SL", "SL-M"]
    price: Decimal
    product_type: Literal["INTRADAY", "DELIVERY", "CNC", "MIS", "FUTURES"]
    trigger_price: Decimal | None = None

    # Futures-specific (ignored by spot adapters)
    leverage: int | None = None          # e.g. 20
    position_model: str | None = None    # "isolated" → "fix", "cross" → "cross"
    take_profit: Decimal | None = None   # TP price
    stop_loss: Decimal | None = None     # SL price
    position_side: Literal["long", "short"] | None = None  # None = default for action
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_brokers.py::test_order_request_position_side_defaults_to_none tests/test_brokers.py::test_order_request_position_side_accepts_long_and_short -v
```

Expected: `2 passed`

- [ ] **Step 5: Run full test suite to confirm no regressions**

```bash
pytest tests/test_exchange1.py tests/test_brokers.py -v
```

Expected: same pass/fail count as before this task (some tests were already failing before this task — that's expected and fixed in later tasks).

- [ ] **Step 6: Commit**

```bash
git add backend/app/brokers/base.py backend/tests/test_brokers.py
git commit -m "feat(brokers): add position_side field to OrderRequest"
```

---

## Task 2: Futures routing refactor — unified `_open_futures` + dispatch table

**Files:**
- Modify: `backend/app/brokers/exchange1.py:282-375`
- Modify: `backend/tests/test_brokers.py`

This task replaces `_open_futures_long` with `_open_futures(order, position_side)` and rewrites `_place_futures_order` as a 4-row dispatch table. Short-position routes are added but the short-open endpoint call is not yet wired (Task 3). TP/SL removal and SL/SL-M fix come in Task 4.

- [ ] **Step 1: Write failing tests for the new dispatch table**

Add to `backend/tests/test_brokers.py` (after existing Exchange1 tests):

```python
@pytest.mark.asyncio
async def test_exchange1_buy_long_routes_to_create_with_long_side():
    """BUY + position_side=None (default) → /futures/order/create with positionSide=long."""
    broker = _make_exchange1()
    broker._post.return_value = {"data": "100001"}

    order = OrderRequest(
        symbol="BTCUSDT", exchange="exchange1", action="BUY",
        quantity=Decimal("1"), order_type="LIMIT", price=Decimal("60000"),
        product_type="FUTURES", leverage=10, position_model="cross",
    )
    resp = await broker.place_order(order)

    call_args = broker._post.call_args
    assert call_args.args[0] == "/openapi/v1/futures/order/create"
    body = call_args.kwargs["body"]
    assert body["positionSide"] == "long"
    assert body["positionModel"] == "cross"
    assert body["leverage"] == "10"
    assert body["price"] == "60000"
    assert resp.status == "open"
    assert resp.order_id == "futures:limit:btc:100001"


@pytest.mark.asyncio
async def test_exchange1_buy_explicit_long_side():
    """BUY + position_side='long' → same as default."""
    broker = _make_exchange1()
    broker._post.return_value = {"data": "100002"}

    order = OrderRequest(
        symbol="BTCUSDT", exchange="exchange1", action="BUY",
        quantity=Decimal("1"), order_type="MARKET", price=Decimal("0"),
        product_type="FUTURES", position_side="long",
    )
    resp = await broker.place_order(order)

    body = broker._post.call_args.kwargs["body"]
    assert body["positionSide"] == "long"
    assert resp.status == "filled"
    assert resp.order_id == "futures:market:btc:100002"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_brokers.py::test_exchange1_buy_long_routes_to_create_with_long_side tests/test_brokers.py::test_exchange1_buy_explicit_long_side -v
```

Expected: `FAILED` — the tests assert `resp.order_id == "futures:limit:btc:100001"` but current code doesn't include `positionSide` in the right way and the order_id format differs.

- [ ] **Step 3: Rewrite the futures routing methods in `exchange1.py`**

Replace the `_place_futures_order` method and `_open_futures_long` method entirely. Also rename `_close_futures_position` to `_close_futures`.

The complete replacement for the section from `_place_futures_order` through `_close_futures_position` (lines 282–416):

```python
async def _place_futures_order(self, order: OrderRequest) -> OrderResponse:
    """Perpetual futures order routing.

    Dispatch table (position_side defaults to 'long' when None):

      BUY  + long  → _open_futures(order, 'long')   open long
      SELL + short → _open_futures(order, 'short')  open short
      SELL + long  → _close_futures(order)           close long
      BUY  + short → _close_futures(order)           close short
    """
    side = order.position_side or "long"
    if order.action == "BUY" and side == "long":
        return await self._open_futures(order, "long")
    if order.action == "SELL" and side == "short":
        return await self._open_futures(order, "short")
    return await self._close_futures(order)

@staticmethod
def _api_position_model(position_model: str | None) -> str:
    """Normalise position_model from user-friendly names to Exchange1 API values.

    "isolated" → "fix"   (Exchange1 term for isolated margin)
    "cross"    → "cross"
    None/other → "cross" (safe default: 'fix' requires per-symbol
                           isolated wallets which aren't initialised
                           by default and triggers a "9257 null" error)
    """
    if position_model and position_model.lower() in ("fix", "isolated"):
        return "fix"
    return "cross"

@staticmethod
def _translate_futures_error(raw: str) -> str:
    """Turn cryptic Exchange1 error codes into actionable messages."""
    if "9257" in raw:
        return (
            "Exchange1 rejected the order (9257): no isolated-margin wallet "
            "for this symbol. Fund the isolated wallet on Exchange1 or "
            "switch the order to Cross margin."
        )
    return raw

async def _open_futures(self, order: OrderRequest, position_side: str) -> OrderResponse:
    """Open a new long or short position via /openapi/v1/futures/order/create.

    position_side must be 'long' or 'short'.
    """
    if order.take_profit:
        return OrderResponse(
            order_id="", status="rejected",
            message=(
                "Exchange1 does not support take_profit at order creation time. "
                "Remove it or configure TP on the Exchange1 platform after the order is placed."
            ),
        )
    if order.stop_loss:
        return OrderResponse(
            order_id="", status="rejected",
            message=(
                "Exchange1 does not support stop_loss at order creation time. "
                "Remove it or configure SL on the Exchange1 platform after the order is placed."
            ),
        )

    symbol = self._futures_symbol(order.symbol)
    position_type = "market" if order.order_type == "MARKET" else "limit"
    pos_model = self._api_position_model(order.position_model)

    if order.order_type != "MARKET" and (order.price is None or order.price <= 0):
        msg = "Non-MARKET futures order requires a positive price"
        logger.error(
            "exchange1_futures_open_rejected",
            symbol=symbol, position_type=position_type, error=msg,
        )
        return OrderResponse(order_id="", status="rejected", message=msg)

    body: dict[str, Any] = {
        "symbol": symbol,
        "positionType": position_type,
        "positionSide": position_side,
        "quantity": str(order.quantity),
        "quantityUnit": "cont",
        "positionModel": pos_model,
    }
    body["leverage"] = str(order.leverage) if order.leverage else "10"
    if order.order_type != "MARKET":
        body["price"] = str(order.price)

    try:
        data = await self._post("/openapi/v1/futures/order/create", body=body, signed=True)
    except RuntimeError as exc:
        logger.error(
            "exchange1_futures_open_rejected",
            symbol=symbol,
            position_type=position_type,
            position_model=pos_model,
            position_side=position_side,
            quantity=str(order.quantity),
            leverage=body["leverage"],
            error=str(exc),
        )
        return OrderResponse(
            order_id="", status="rejected",
            message=self._translate_futures_error(str(exc)),
        )

    raw_id = str(data.get("data", ""))
    order_id = _encode_futures_order_id(raw_id, symbol, position_type) if raw_id else ""
    status = "filled" if order.order_type == "MARKET" else "open"
    return OrderResponse(order_id=order_id, status=status, fill_price=Decimal("0"), fill_quantity=Decimal("0"))

async def _close_futures(self, order: OrderRequest) -> OrderResponse:
    """Close an existing position via /openapi/v1/futures/order/close.

    Full close (default): closeType='all'.
    Partial close: set order.trigger_price to the position ID returned by
    /openapi/v1/futures/order/positions; closeNum is set to order.quantity.
    """
    symbol = self._futures_symbol(order.symbol)
    position_type = "market" if order.order_type == "MARKET" else "limit"

    body: dict[str, Any] = {
        "symbol": symbol,
        "positionType": position_type,
        "closeType": str(order.trigger_price) if order.trigger_price else "all",
    }
    if order.trigger_price:
        body["closeNum"] = str(order.quantity)
    if order.order_type != "MARKET" and order.price:
        body["price"] = str(order.price)

    try:
        data = await self._post("/openapi/v1/futures/order/close", body=body, signed=True)
    except RuntimeError as exc:
        logger.error(
            "exchange1_futures_close_rejected",
            symbol=symbol,
            position_type=position_type,
            error=str(exc),
        )
        return OrderResponse(
            order_id="", status="rejected",
            message=self._translate_futures_error(str(exc)),
        )

    raw_id = str(data.get("data", ""))
    order_id = _encode_futures_order_id(raw_id, symbol, position_type) if raw_id else ""
    status = "filled" if order.order_type == "MARKET" else "open"
    return OrderResponse(order_id=order_id, status=status, fill_price=Decimal("0"), fill_quantity=Decimal("0"))
```

- [ ] **Step 4: Run the two new tests to verify they pass**

```bash
pytest tests/test_brokers.py::test_exchange1_buy_long_routes_to_create_with_long_side tests/test_brokers.py::test_exchange1_buy_explicit_long_side -v
```

Expected: `2 passed`

- [ ] **Step 5: Run full futures-related tests**

```bash
pytest tests/test_exchange1.py tests/test_brokers.py -v
```

Some pre-existing tests in `test_brokers.py` will still fail (they test old behaviour — they are fixed in Task 8). The tests in `test_exchange1.py` should all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/brokers/exchange1.py backend/tests/test_brokers.py
git commit -m "refactor(exchange1): unified _open_futures + explicit dispatch table"
```

---

## Task 3: Short position support

**Files:**
- Modify: `backend/tests/test_brokers.py`
- No new implementation needed — `_open_futures(order, "short")` and `_close_futures` from Task 2 already handle this

- [ ] **Step 1: Write failing tests for short open and short close**

Add to `backend/tests/test_brokers.py`:

```python
@pytest.mark.asyncio
async def test_exchange1_open_short_routes_to_create_with_short_side():
    """SELL + position_side='short' → /futures/order/create with positionSide=short."""
    broker = _make_exchange1()
    broker._post.return_value = {"data": "200001"}

    order = OrderRequest(
        symbol="BTCUSDT", exchange="exchange1", action="SELL",
        quantity=Decimal("1"), order_type="LIMIT", price=Decimal("80000"),
        product_type="FUTURES", leverage=5, position_model="cross",
        position_side="short",
    )
    resp = await broker.place_order(order)

    call_args = broker._post.call_args
    assert call_args.args[0] == "/openapi/v1/futures/order/create"
    body = call_args.kwargs["body"]
    assert body["positionSide"] == "short"
    assert body["positionModel"] == "cross"
    assert body["price"] == "80000"
    assert resp.status == "open"
    assert resp.order_id == "futures:limit:btc:200001"


@pytest.mark.asyncio
async def test_exchange1_close_short_routes_to_close():
    """BUY + position_side='short' → /futures/order/close (close the short)."""
    broker = _make_exchange1()
    broker._post.return_value = {"data": "200002"}

    order = OrderRequest(
        symbol="BTCUSDT", exchange="exchange1", action="BUY",
        quantity=Decimal("1"), order_type="MARKET", price=Decimal("0"),
        product_type="FUTURES", position_side="short",
    )
    resp = await broker.place_order(order)

    call_args = broker._post.call_args
    assert call_args.args[0] == "/openapi/v1/futures/order/close"
    body = call_args.kwargs["body"]
    assert body["closeType"] == "all"
    assert resp.status == "filled"
    assert resp.order_id == "futures:market:btc:200002"
```

- [ ] **Step 2: Run tests to verify they pass immediately** (the dispatch table from Task 2 already routes correctly)

```bash
pytest tests/test_brokers.py::test_exchange1_open_short_routes_to_create_with_short_side tests/test_brokers.py::test_exchange1_close_short_routes_to_close -v
```

Expected: `2 passed`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_brokers.py
git commit -m "test(exchange1): verify short position open and close routing"
```

---

## Task 4: TP/SL rejection + SL/SL-M price fix + partial close

**Files:**
- Modify: `backend/tests/test_brokers.py`
- Modify: `backend/tests/test_exchange1.py`

These were already implemented in `_open_futures` and `_close_futures` in Task 2. This task adds the tests to verify the behaviour and fixes the pre-existing broken `test_exchange1_futures_tp_sl` test in `test_brokers.py`.

- [ ] **Step 1: Add tests for TP/SL rejection**

Add to `backend/tests/test_brokers.py`:

```python
@pytest.mark.asyncio
async def test_exchange1_futures_take_profit_rejected():
    """take_profit on a futures order → rejected before any API call."""
    broker = _make_exchange1()

    order = OrderRequest(
        symbol="BTCUSDT", exchange="exchange1", action="BUY",
        quantity=Decimal("1"), order_type="LIMIT", price=Decimal("65000"),
        product_type="FUTURES", take_profit=Decimal("70000"),
    )
    resp = await broker.place_order(order)

    broker._post.assert_not_called()
    assert resp.status == "rejected"
    assert "take_profit" in resp.message.lower()


@pytest.mark.asyncio
async def test_exchange1_futures_stop_loss_rejected():
    """stop_loss on a futures order → rejected before any API call."""
    broker = _make_exchange1()

    order = OrderRequest(
        symbol="BTCUSDT", exchange="exchange1", action="BUY",
        quantity=Decimal("1"), order_type="LIMIT", price=Decimal("65000"),
        product_type="FUTURES", stop_loss=Decimal("62000"),
    )
    resp = await broker.place_order(order)

    broker._post.assert_not_called()
    assert resp.status == "rejected"
    assert "stop_loss" in resp.message.lower()
```

- [ ] **Step 2: Add tests for SL/SL-M order types include price**

Add to `backend/tests/test_brokers.py`:

```python
@pytest.mark.asyncio
async def test_exchange1_futures_sl_order_type_sends_price():
    """order_type='SL' maps to positionType='limit' and must include price."""
    broker = _make_exchange1()
    broker._post.return_value = {"data": "300001"}

    order = OrderRequest(
        symbol="BTCUSDT", exchange="exchange1", action="BUY",
        quantity=Decimal("1"), order_type="SL", price=Decimal("58000"),
        product_type="FUTURES", leverage=10, position_model="cross",
        trigger_price=Decimal("59000"),
    )
    resp = await broker.place_order(order)

    body = broker._post.call_args.kwargs["body"]
    assert body["positionType"] == "limit"
    assert body["price"] == "58000"
    assert resp.status == "open"


@pytest.mark.asyncio
async def test_exchange1_futures_sl_m_order_type_sends_price():
    """order_type='SL-M' maps to positionType='limit' and must include price."""
    broker = _make_exchange1()
    broker._post.return_value = {"data": "300002"}

    order = OrderRequest(
        symbol="BTCUSDT", exchange="exchange1", action="BUY",
        quantity=Decimal("1"), order_type="SL-M", price=Decimal("57000"),
        product_type="FUTURES", leverage=10, position_model="cross",
    )
    resp = await broker.place_order(order)

    body = broker._post.call_args.kwargs["body"]
    assert body["positionType"] == "limit"
    assert body["price"] == "57000"
```

- [ ] **Step 3: Add test for partial close**

Add to `backend/tests/test_brokers.py`:

```python
@pytest.mark.asyncio
async def test_exchange1_futures_partial_close_uses_trigger_price_as_position_id():
    """trigger_price on a close order → closeType=<position_id>, closeNum set."""
    broker = _make_exchange1()
    broker._post.return_value = {"data": "300003"}

    order = OrderRequest(
        symbol="BTCUSDT", exchange="exchange1", action="SELL",
        quantity=Decimal("2"), order_type="MARKET", price=Decimal("0"),
        product_type="FUTURES",
        trigger_price=Decimal("700340577325424640"),  # position ID from Exchange1
    )
    resp = await broker.place_order(order)

    body = broker._post.call_args.kwargs["body"]
    assert body["closeType"] == "700340577325424640"
    assert body["closeNum"] == "2"
    assert resp.status == "filled"
```

- [ ] **Step 4: Run the new tests to verify they pass**

```bash
pytest tests/test_brokers.py::test_exchange1_futures_take_profit_rejected tests/test_brokers.py::test_exchange1_futures_stop_loss_rejected tests/test_brokers.py::test_exchange1_futures_sl_order_type_sends_price tests/test_brokers.py::test_exchange1_futures_sl_m_order_type_sends_price tests/test_brokers.py::test_exchange1_futures_partial_close_uses_trigger_price_as_position_id -v
```

Expected: `5 passed`

- [ ] **Step 5: Add TP/SL rejection tests to `test_exchange1.py`**

In `backend/tests/test_exchange1.py`, add these two tests inside `class TestOrders`:

```python
@respx.mock
@pytest.mark.asyncio
async def test_futures_take_profit_rejected_before_api(self):
    """take_profit on futures → rejected with no HTTP call made."""
    broker = _make_authenticated_broker()
    order = OrderRequest(
        symbol="BTCUSDT", exchange="EXCHANGE1", action="BUY",
        quantity=Decimal("1"), order_type="LIMIT", price=Decimal("65000"),
        product_type="FUTURES", take_profit=Decimal("70000"),
    )
    resp = await broker.place_order(order)
    await broker.close()

    assert resp.status == "rejected"
    assert "take_profit" in resp.message.lower()

@respx.mock
@pytest.mark.asyncio
async def test_futures_stop_loss_rejected_before_api(self):
    """stop_loss on futures → rejected with no HTTP call made."""
    broker = _make_authenticated_broker()
    order = OrderRequest(
        symbol="BTCUSDT", exchange="EXCHANGE1", action="BUY",
        quantity=Decimal("1"), order_type="LIMIT", price=Decimal("65000"),
        product_type="FUTURES", stop_loss=Decimal("62000"),
    )
    resp = await broker.place_order(order)
    await broker.close()

    assert resp.status == "rejected"
    assert "stop_loss" in resp.message.lower()
```

- [ ] **Step 6: Run all tests**

```bash
pytest tests/test_exchange1.py tests/test_brokers.py -v
```

- [ ] **Step 7: Commit**

```bash
git add backend/tests/test_brokers.py backend/tests/test_exchange1.py
git commit -m "test(exchange1): TP/SL rejection, SL/SL-M price, partial close"
```

---

## Task 5: Status map uppercase fix

**Files:**
- Modify: `backend/app/brokers/exchange1.py:46-54` (the `_STATUS_MAP` constant)
- Modify: `backend/app/brokers/exchange1.py` (`get_order_status` method, ~line 437)
- Modify: `backend/tests/test_exchange1.py`

- [ ] **Step 1: Write failing tests**

Add inside `class TestCancelAndStatus` in `backend/tests/test_exchange1.py`:

```python
@respx.mock
@pytest.mark.asyncio
async def test_get_order_status_uppercase_entry_maps_to_open(self):
    """Exchange1 returns uppercase 'ENTRY' for an open order."""
    respx.get(f"{BASE_URL}/openapi/v1/spot/order/detail").mock(
        return_value=httpx.Response(200, json={
            "code": 200,
            "data": {
                "id": "855200",
                "state": "ENTRY",
                "quantity": "0.001",
            },
        })
    )

    broker = _make_authenticated_broker()
    status = await broker.get_order_status("855200")
    await broker.close()

    assert status.status == "open"

@respx.mock
@pytest.mark.asyncio
async def test_get_order_status_uppercase_transacted_maps_to_filled(self):
    """Exchange1 returns uppercase 'TRANSACTED' for a filled order."""
    respx.get(f"{BASE_URL}/openapi/v1/spot/order/detail").mock(
        return_value=httpx.Response(200, json={
            "code": 200,
            "data": {
                "id": "855201",
                "state": "TRANSACTED",
                "tradePrice": "66000.00",
                "doneQuantity": "0.001",
                "quantity": "0.001",
            },
        })
    )

    broker = _make_authenticated_broker()
    status = await broker.get_order_status("855201")
    await broker.close()

    assert status.status == "filled"

@respx.mock
@pytest.mark.asyncio
async def test_get_order_status_uppercase_new_maps_to_open(self):
    """Exchange1 returns uppercase 'NEW' for an unfilled order."""
    respx.get(f"{BASE_URL}/openapi/v1/spot/order/detail").mock(
        return_value=httpx.Response(200, json={
            "code": 200,
            "data": {
                "id": "855202",
                "state": "NEW",
                "quantity": "0.001",
            },
        })
    )

    broker = _make_authenticated_broker()
    status = await broker.get_order_status("855202")
    await broker.close()

    assert status.status == "open"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_exchange1.py::TestCancelAndStatus::test_get_order_status_uppercase_entry_maps_to_open tests/test_exchange1.py::TestCancelAndStatus::test_get_order_status_uppercase_transacted_maps_to_filled tests/test_exchange1.py::TestCancelAndStatus::test_get_order_status_uppercase_new_maps_to_open -v
```

Expected: `FAILED` — "ENTRY", "TRANSACTED", "NEW" are not in the map and `state.lower()` is not called.

- [ ] **Step 3: Update `_STATUS_MAP` and lowercase state lookup in `exchange1.py`**

Replace the `_STATUS_MAP` constant at the top of `exchange1.py`:

```python
_STATUS_MAP: dict[str, str] = {
    "new": "open",
    "entry": "open",
    "freezed": "open",
    "partially_filled": "open",
    "filled": "filled",
    "transacted": "filled",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "rejected": "rejected",
    "expired": "cancelled",
}
```

Then in `get_order_status`, find the line that reads the state for spot orders:

```python
state = detail.get("state", "")
status = _STATUS_MAP.get(state, "open")
```

Replace it with:

```python
state = detail.get("state", "").lower()
status = _STATUS_MAP.get(state, "open")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_exchange1.py::TestCancelAndStatus::test_get_order_status_uppercase_entry_maps_to_open tests/test_exchange1.py::TestCancelAndStatus::test_get_order_status_uppercase_transacted_maps_to_filled tests/test_exchange1.py::TestCancelAndStatus::test_get_order_status_uppercase_new_maps_to_open -v
```

Expected: `3 passed`

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/test_exchange1.py tests/test_brokers.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/brokers/exchange1.py backend/tests/test_exchange1.py
git commit -m "fix(exchange1): normalise status map for uppercase Exchange1 states"
```

---

## Task 6: Fix `get_positions` + fix `_BALANCE_RESPONSE` fixture

**Files:**
- Modify: `backend/app/brokers/exchange1.py` (`get_positions` method, ~line 597)
- Modify: `backend/tests/test_exchange1.py` (`_BALANCE_RESPONSE` fixture + portfolio tests)

The current `_BALANCE_RESPONSE` fixture uses a flat `"data": [...]` list, but `_get_balance_data` expects `"data": {"accounts": [...]}`. This has been silently broken. This task fixes both the fixture and the `"spot"` → `"asset"` filter in `get_positions`.

- [ ] **Step 1: Replace `_BALANCE_RESPONSE` in `test_exchange1.py`**

Find and replace the entire `_BALANCE_RESPONSE` constant (around line 556):

```python
# Represents the real Exchange1 /openapi/v1/balance response shape.
# "asset" biz → base-token holdings (BTC, ETH, SOL)
# "spot"  biz → quote currency (USDT, USDC)
# "cfd"   biz → perpetual futures margin account
_BALANCE_RESPONSE = {
    "code": 200,
    "data": {
        "accounts": [
            {
                "biz": {"name": "asset"},
                "currencies": [
                    {
                        "displayCode": "BTC",
                        "balance": {
                            "available": "0.5",
                            "hold": "0.1",
                            "total": "0.6",
                            "availableMargin": "0.5",
                        },
                    },
                    {
                        "displayCode": "ETH",
                        "balance": {
                            "available": "10.0",
                            "hold": "0.0",
                            "total": "10.0",
                            "availableMargin": "10.0",
                        },
                    },
                    {
                        "displayCode": "SOL",
                        "balance": {
                            "available": "0.0",
                            "hold": "0.0",
                            "total": "0.0",
                            "availableMargin": "0.0",
                        },
                    },
                ],
            },
            {
                "biz": {"name": "spot"},
                "currencies": [
                    {
                        "displayCode": "USDT",
                        "balance": {
                            "available": "5000.00",
                            "hold": "1000.00",
                            "total": "6000.00",
                            "availableMargin": "5000.00",
                        },
                    },
                    {
                        "displayCode": "USDC",
                        "balance": {
                            "available": "2000.00",
                            "hold": "0.0",
                            "total": "2000.00",
                            "availableMargin": "2000.00",
                        },
                    },
                ],
            },
            {
                "biz": {"name": "cfd"},
                "currencies": [
                    {
                        "displayCode": "USDT",
                        "balance": {
                            "available": "0.0",
                            "hold": "0.0",
                            "total": "0.0",
                            "availableMargin": "0.0",
                        },
                    },
                ],
            },
        ]
    },
}
```

- [ ] **Step 2: Update `test_get_balance_extracts_usdt` to reflect correct legacy path**

With the new fixture, `get_balance()` (no product_type) uses the legacy priority:
1. CFD with non-zero availableMargin → CFD has 0.0, skip
2. Asset with non-zero available → BTC has 0.5, returns BTC balance

The test name and assertion need updating. Replace `test_get_balance_extracts_usdt` with:

```python
@respx.mock
@pytest.mark.asyncio
async def test_get_balance_default_returns_first_asset(self):
    """get_balance() with no product_type → first 'asset' account with funds (BTC)."""
    respx.get(f"{BASE_URL}/openapi/v1/balance").mock(
        return_value=httpx.Response(200, json=_BALANCE_RESPONSE)
    )

    broker = _make_authenticated_broker()
    balance = await broker.get_balance()
    await broker.close()

    # Legacy path #2: first asset with non-zero available → BTC (0.5 available)
    assert balance.available == Decimal("0.5")
    assert balance.used_margin == Decimal("0.1")
    assert balance.total == Decimal("0.6")
```

Also add a test for the SPOT product_type path (uses "asset" biz with INR — the fixture doesn't have INR so returns zero):

```python
@respx.mock
@pytest.mark.asyncio
async def test_get_balance_futures_returns_cfd_margin(self):
    """get_balance(product_type='FUTURES') → CFD account availableMargin."""
    cfd_response = {
        "code": 200,
        "data": {
            "accounts": [
                {
                    "biz": {"name": "cfd"},
                    "currencies": [
                        {
                            "displayCode": "USDT",
                            "balance": {
                                "available": "3000.00",
                                "hold": "500.00",
                                "total": "3500.00",
                                "availableMargin": "3000.00",
                            },
                        }
                    ],
                }
            ]
        },
    }
    respx.get(f"{BASE_URL}/openapi/v1/balance").mock(
        return_value=httpx.Response(200, json=cfd_response)
    )

    broker = _make_authenticated_broker()
    balance = await broker.get_balance(product_type="FUTURES")
    await broker.close()

    assert balance.available == Decimal("3000.00")
    assert balance.used_margin == Decimal("500.00")
    assert balance.total == Decimal("3500.00")
```

- [ ] **Step 3: Run portfolio tests to verify they fail first**

```bash
pytest tests/test_exchange1.py::TestPortfolio -v
```

Expected: `test_get_balance_default_returns_first_asset` fails (implementation not changed yet), others may fail too due to fixture format mismatch.

- [ ] **Step 4: Fix `get_positions` in `exchange1.py`**

In `get_positions` (~line 597), find:

```python
        # --- Spot positions (non-zero, non-quote asset balances) ---
        accounts = await self._get_balance_data()
        for acc in accounts:
            if acc.get("account_type") != "spot":
                continue
```

Replace with:

```python
        # --- Spot positions (non-zero, non-quote asset balances) ---
        # Base-token holdings live in the "asset" biz account, not "spot".
        accounts = await self._get_balance_data()
        for acc in accounts:
            if acc.get("account_type") != "asset":
                continue
```

- [ ] **Step 5: Run portfolio tests to verify they pass**

```bash
pytest tests/test_exchange1.py::TestPortfolio -v
```

Expected: all `TestPortfolio` tests pass.

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/test_exchange1.py tests/test_brokers.py -v
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/brokers/exchange1.py backend/tests/test_exchange1.py
git commit -m "fix(exchange1): get_positions reads asset biz; fix balance fixture"
```

---

## Task 7: Fix pre-existing broken tests in `test_brokers.py`

**Files:**
- Modify: `backend/tests/test_brokers.py`

These tests were written against old behaviour that no longer exists (old 2-part order ID format, old TP/SL behaviour, old default positionModel). They must be updated to match the current code.

- [ ] **Step 1: Run to see which tests currently fail**

```bash
pytest tests/test_brokers.py -v 2>&1 | grep -E "FAILED|ERROR"
```

Expected failures (pre-existing):
- `test_exchange1_futures_buy_builds_correct_body` — wrong positionModel ("fix" instead of "cross"), wrong order_id format ("futures:98765" instead of "futures:limit:btc:98765"), missing `leverage` in assertion
- `test_exchange1_futures_tp_sl` — asserts TP/SL are sent to API; after fix they are rejected before any API call
- `test_exchange1_futures_sell_closes_position` — wrong order_id ("futures:11111" instead of "futures:market:btc:11111")
- `test_exchange1_futures_cancel_routes_correctly` — uses 2-part ID "futures:42" which now raises ValueError
- `test_exchange1_futures_order_status_filled_when_absent` — uses 2-part ID "futures:999"; response mock has wrong key `"list"` instead of `"rows"`

- [ ] **Step 2: Replace the five broken tests**

Replace `test_exchange1_futures_buy_builds_correct_body` with:

```python
@pytest.mark.asyncio
async def test_exchange1_futures_buy_builds_correct_body():
    broker = _make_exchange1()
    broker._post.return_value = {"data": "98765"}

    order = OrderRequest(
        symbol="BTCUSDT",
        exchange="exchange1",
        action="BUY",
        quantity=Decimal("2"),
        order_type="LIMIT",
        price=Decimal("66000"),
        product_type="FUTURES",
        # position_model omitted → defaults to "cross"
    )
    resp = await broker.place_order(order)

    broker._post.assert_called_once_with(
        "/openapi/v1/futures/order/create",
        body={
            "symbol": "btc",
            "positionType": "limit",
            "positionSide": "long",
            "quantity": "2",
            "quantityUnit": "cont",
            "positionModel": "cross",
            "leverage": "10",
            "price": "66000",
        },
        signed=True,
    )
    assert resp.status == "open"
    assert resp.order_id == "futures:limit:btc:98765"
```

Replace `test_exchange1_futures_tp_sl` with:

```python
@pytest.mark.asyncio
async def test_exchange1_futures_tp_sl_both_rejected():
    """TP or SL on futures → rejected before any API call (Exchange1 sign error)."""
    broker = _make_exchange1()

    order = OrderRequest(
        symbol="BTCUSDT",
        exchange="exchange1",
        action="BUY",
        quantity=Decimal("1"),
        order_type="LIMIT",
        price=Decimal("65000"),
        product_type="FUTURES",
        leverage=10,
        take_profit=Decimal("70000"),
        stop_loss=Decimal("62000"),
    )
    resp = await broker.place_order(order)

    # take_profit is checked first — no API call made
    broker._post.assert_not_called()
    assert resp.status == "rejected"
    assert "take_profit" in resp.message.lower()
```

Replace `test_exchange1_futures_sell_closes_position` with:

```python
@pytest.mark.asyncio
async def test_exchange1_futures_sell_closes_position():
    """SELL on futures (default long side) → close via /openapi/v1/futures/order/close."""
    broker = _make_exchange1()
    broker._post.return_value = {"data": "11111"}

    order = OrderRequest(
        symbol="BTCUSDT",
        exchange="exchange1",
        action="SELL",
        quantity=Decimal("1"),
        order_type="MARKET",
        price=Decimal("0"),
        product_type="FUTURES",
    )
    resp = await broker.place_order(order)

    broker._post.assert_called_once_with(
        "/openapi/v1/futures/order/close",
        body={"symbol": "btc", "positionType": "market", "closeType": "all"},
        signed=True,
    )
    assert resp.order_id == "futures:market:btc:11111"
```

Replace `test_exchange1_futures_cancel_routes_correctly` with:

```python
@pytest.mark.asyncio
async def test_exchange1_futures_cancel_routes_correctly():
    broker = _make_exchange1()
    broker._post.return_value = {}

    await broker.cancel_order("futures:limit:btc:42")
    broker._post.assert_called_once_with(
        "/openapi/v1/futures/order/cancel",
        body={"id": "42", "symbol": "btc", "positionType": "limit"},
        signed=True,
    )
```

Replace `test_exchange1_futures_order_status_filled_when_absent` with:

```python
@pytest.mark.asyncio
async def test_exchange1_futures_order_status_filled_when_absent():
    """Order not in current orders list → treat as filled."""
    broker = _make_exchange1()
    # Exchange1 returns rows under "data.rows", not "data.list"
    broker._get.return_value = {"data": {"rows": []}}

    status = await broker.get_order_status("futures:market:btc:999")

    assert status.status == "filled"
    assert status.order_id == "futures:market:btc:999"
```

- [ ] **Step 3: Run all tests to verify they pass**

```bash
pytest tests/test_exchange1.py tests/test_brokers.py -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_brokers.py
git commit -m "fix(tests): update test_brokers for current exchange1 behaviour"
```

---

## Final verification

- [ ] **Run the complete test suite one last time**

```bash
pytest tests/test_exchange1.py tests/test_brokers.py -v --tb=short
```

Expected: all tests pass, no failures.

- [ ] **Verify the adapter still authenticates and handles the live cancel flow**

The order ID encoding is unchanged: `futures:{positionType}:{symbol}:{raw_id}`. Existing stored order IDs in the DB remain cancellable.
