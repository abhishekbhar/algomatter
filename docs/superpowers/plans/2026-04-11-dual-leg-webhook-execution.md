# Dual-Leg Webhook Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a webhook signal arrives for a live strategy with `dual_leg.enabled`, automatically close the existing opposite position before opening a new one, respecting stop conditions (max_trades, trading_hours).

**Architecture:** All dual-leg logic lives in `executor.py` as `_execute_dual_leg()`, called from the existing `execute()` live branch. Redis tracks per-strategy `position_side` and `trade_count`. New Redis helpers live in `processor.py` following existing patterns. `_place_live_order()` gains an `update_redis` flag so dual-leg can manage its own state.

**Tech Stack:** Python 3.13, FastAPI, Redis (aioredis), pytest-asyncio, unittest.mock

---

## File Map

| File | Change |
|---|---|
| `backend/app/webhooks/processor.py` | Add 4 Redis helper functions for dual-leg state |
| `backend/app/webhooks/executor.py` | Add `update_redis` param to `_place_live_order`, add `_execute_dual_leg`, wire into `execute()` |
| `backend/tests/test_webhook_processor.py` | Add dual-leg Redis helper tests |
| `backend/tests/test_webhook_executor.py` | Update live-mode test + add dual-leg scenario tests |

---

## Task 1: Redis helpers for dual-leg state

**Files:**
- Modify: `backend/app/webhooks/processor.py`
- Test: `backend/tests/test_webhook_processor.py`

### Context

`processor.py` already contains Redis helpers following the same pattern:
- Keys use `f"wh:..."` prefix with strategy_id
- TTL uses midnight IST expiry via `expireat`
- All functions are `async`, `best-effort` (swallow exceptions, never fail the webhook)

Dual-leg adds 4 new helpers:
- `get_dual_leg_state(redis, strategy_id)` → `tuple[str, int]` — reads `(position_side, trade_count)` in one `mget`
- `set_dual_leg_position(redis, strategy_id, side)` — sets position_side with 24h TTL
- `clear_dual_leg_position(redis, strategy_id)` — sets position_side to `""`
- `increment_dual_leg_trade_count(redis, strategy_id)` — incr trade_count with midnight IST TTL

Redis key names:
```
dual_leg:{strategy_id}:position_side   →  "" | "long" | "short"
dual_leg:{strategy_id}:trade_count     →  int
```

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_webhook_processor.py` (or append if it exists). Add:

```python
# backend/tests/test_webhook_processor.py
import pytest
from unittest.mock import AsyncMock, call, patch
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

from app.webhooks.processor import (
    get_dual_leg_state,
    set_dual_leg_position,
    clear_dual_leg_position,
    increment_dual_leg_trade_count,
)

_IST = ZoneInfo("Asia/Kolkata")


@pytest.mark.asyncio
async def test_get_dual_leg_state_returns_defaults_when_missing():
    redis = AsyncMock()
    redis.mget.return_value = [None, None]
    side, count = await get_dual_leg_state(redis, "strat-1")
    assert side == ""
    assert count == 0


@pytest.mark.asyncio
async def test_get_dual_leg_state_returns_stored_values():
    redis = AsyncMock()
    redis.mget.return_value = [b"long", b"3"]
    side, count = await get_dual_leg_state(redis, "strat-1")
    assert side == "long"
    assert count == 3


@pytest.mark.asyncio
async def test_get_dual_leg_state_returns_defaults_on_redis_error():
    redis = AsyncMock()
    redis.mget.side_effect = Exception("redis down")
    side, count = await get_dual_leg_state(redis, "strat-1")
    assert side == ""
    assert count == 0


@pytest.mark.asyncio
async def test_set_dual_leg_position_sets_key_with_ttl():
    redis = AsyncMock()
    await set_dual_leg_position(redis, "strat-1", "long")
    redis.set.assert_called_once()
    args, kwargs = redis.set.call_args
    assert args[0] == "dual_leg:strat-1:position_side"
    assert args[1] == "long"
    assert "ex" in kwargs  # TTL set


@pytest.mark.asyncio
async def test_clear_dual_leg_position_sets_empty_string():
    redis = AsyncMock()
    await clear_dual_leg_position(redis, "strat-1")
    redis.set.assert_called_once()
    args, kwargs = redis.set.call_args
    assert args[0] == "dual_leg:strat-1:position_side"
    assert args[1] == ""


@pytest.mark.asyncio
async def test_increment_dual_leg_trade_count_increments_with_ttl():
    redis = AsyncMock()
    await increment_dual_leg_trade_count(redis, "strat-1")
    redis.incr.assert_called_once_with("dual_leg:strat-1:trade_count")
    redis.expireat.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_webhook_processor.py -k "dual_leg" -v 2>&1 | tail -20
```

Expected: `ImportError` or `AttributeError` — functions don't exist yet.

- [ ] **Step 3: Implement the 4 helper functions**

Append to the bottom of `backend/app/webhooks/processor.py`:

```python
async def get_dual_leg_state(redis, strategy_id: str) -> tuple[str, int]:
    """Return (position_side, trade_count) for dual-leg tracking.

    position_side: "" | "long" | "short"
    trade_count: number of open legs placed today
    Falls back to ("", 0) if Redis is unavailable.
    """
    try:
        side_key = f"dual_leg:{strategy_id}:position_side"
        count_key = f"dual_leg:{strategy_id}:trade_count"
        side, count = await redis.mget(side_key, count_key)
        return (side.decode() if side else "", int(count or 0))
    except Exception:
        return ("", 0)


async def set_dual_leg_position(redis, strategy_id: str, side: str) -> None:
    """Set position_side with 24-hour TTL."""
    try:
        key = f"dual_leg:{strategy_id}:position_side"
        await redis.set(key, side, ex=86400)
    except Exception:
        pass


async def clear_dual_leg_position(redis, strategy_id: str) -> None:
    """Clear position_side (set to empty string) with 24-hour TTL."""
    try:
        key = f"dual_leg:{strategy_id}:position_side"
        await redis.set(key, "", ex=86400)
    except Exception:
        pass


async def increment_dual_leg_trade_count(redis, strategy_id: str) -> None:
    """Increment trade_count; auto-expires at midnight IST."""
    try:
        key = f"dual_leg:{strategy_id}:trade_count"
        await redis.incr(key)
        now = datetime.now(_IST)
        midnight = datetime.combine(
            now.date() + timedelta(days=1),
            time.min,
            tzinfo=_IST,
        )
        await redis.expireat(key, int(midnight.timestamp()))
    except Exception:
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && .venv/bin/pytest tests/test_webhook_processor.py -k "dual_leg" -v 2>&1 | tail -20
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/webhooks/processor.py backend/tests/test_webhook_processor.py
git commit -m "feat: add dual-leg Redis state helpers to processor"
```

---

## Task 2: Add `update_redis` flag to `_place_live_order`

**Files:**
- Modify: `backend/app/webhooks/executor.py`
- Test: `backend/tests/test_webhook_executor.py`

### Context

`_place_live_order` currently updates Redis position counters unconditionally on success:

```python
# at the bottom of _place_live_order:
if redis and execution_result in ("filled", "accepted"):
    await update_position_count(redis, strategy_id, signal.action)
    await increment_signals_today(redis, strategy_id)
```

Dual-leg calls `_place_live_order` for both the close leg and open leg, but manages its own Redis state. Adding `update_redis: bool = True` lets dual-leg pass `False` to skip these updates.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_webhook_executor.py`:

```python
@pytest.mark.asyncio
async def test_place_live_order_skips_redis_update_when_flag_false():
    """When update_redis=False, position count and signals_today are not updated."""
    broker_id = str(uuid.uuid4())
    tenant_id = uuid.uuid4()
    strategy_id = str(uuid.uuid4())
    redis = AsyncMock()

    signal = StandardSignal(
        symbol="BTCUSDT",
        exchange="EXCHANGE1",
        action="BUY",
        quantity="1",
        order_type="MARKET",
        product_type="FUTURES",
    )

    mock_order_response = MagicMock()
    mock_order_response.status = "filled"
    mock_order_response.model_dump.return_value = {"status": "filled", "order_id": "123"}

    with patch("app.webhooks.executor.async_session_factory") as mock_factory, \
         patch("app.webhooks.executor.get_broker", new_callable=AsyncMock) as mock_broker_fn:

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: MagicMock(
            broker_type="exchange1", credentials=b"enc", id=uuid.UUID(broker_id), tenant_id=tenant_id
        )))
        mock_factory.return_value = mock_session

        mock_broker = AsyncMock()
        mock_broker.place_order = AsyncMock(return_value=mock_order_response)
        mock_broker.close = AsyncMock()
        mock_broker_fn.return_value = mock_broker

        with patch("app.webhooks.executor.decrypt_credentials", return_value={}):
            from app.webhooks.executor import _place_live_order
            result, detail = await _place_live_order(
                broker_id, tenant_id, strategy_id, signal, redis, update_redis=False
            )

    assert result == "filled"
    redis.incr.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && .venv/bin/pytest tests/test_webhook_executor.py::test_place_live_order_skips_redis_update_when_flag_false -v 2>&1 | tail -10
```

Expected: `TypeError: _place_live_order() got an unexpected keyword argument 'update_redis'`

- [ ] **Step 3: Add the `update_redis` parameter**

In `backend/app/webhooks/executor.py`, change the signature and body of `_place_live_order`:

```python
async def _place_live_order(
    broker_connection_id: str,
    tenant_id: uuid.UUID,
    strategy_id: str,
    signal: StandardSignal,
    redis,
    update_redis: bool = True,
) -> tuple[str, dict]:
    """Open own DB session, decrypt credentials, call broker.place_order().

    Returns (execution_result, execution_detail).
    When update_redis=True (default), updates Redis position/signal counters on success.
    Pass update_redis=False when the caller (e.g. _execute_dual_leg) manages Redis state.
    Does NOT write to the WebhookSignal table (that is the router's job).
    """
```

And update the Redis block at the bottom of `_place_live_order`:

```python
    # Update Redis position counter
    if update_redis and redis and execution_result in ("filled", "accepted"):
        await update_position_count(redis, strategy_id, signal.action)
        await increment_signals_today(redis, strategy_id)

    return execution_result, execution_detail
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && .venv/bin/pytest tests/test_webhook_executor.py::test_place_live_order_skips_redis_update_when_flag_false -v 2>&1 | tail -10
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/webhooks/executor.py backend/tests/test_webhook_executor.py
git commit -m "feat: add update_redis flag to _place_live_order"
```

---

## Task 3: Implement `_execute_dual_leg()`

**Files:**
- Modify: `backend/app/webhooks/executor.py`
- Test: `backend/tests/test_webhook_executor.py`

### Context

`_execute_dual_leg` orchestrates the two-leg execution for one strategy signal:
1. Read Redis state (`position_side`, `trade_count`)
2. Evaluate stop condition
3. Decide which legs to run (decision table from spec)
4. Execute close leg first (if needed), then open leg
5. Handle Exchange1 error 9012 (position not found) as already-closed
6. Update Redis state
7. Return `(execution_result, execution_detail)`

**Decision table** (from spec Section 3):

| position_side | stop | action | close_needed | open_needed |
|---|---|---|---|---|
| `""` | false | BUY | no | yes |
| `""` | false | SELL | no | yes |
| `""` | true | any | no | no → `"no_action"` |
| `"long"` | false | BUY | no (already long) | no → `"no_action"` |
| `"long"` | false | SELL | yes (close long) | yes (open short) |
| `"long"` | true | any | yes (close long) | no |
| `"short"` | false | SELL | no (already short) | no → `"no_action"` |
| `"short"` | false | BUY | yes (close short) | yes (open long) |
| `"short"` | true | any | yes (close short) | no |

**Stop condition** — either:
- `trade_count >= dual_leg_config["max_trades"]`
- Current time outside `strategy["rules"]["trading_hours"]` (reuse existing `evaluate_rules` trading_hours logic)

**9012 detection** — Exchange1 returns error 9012 as a broker_error with message containing "9012":
```python
def _is_position_not_found(execution_detail: dict) -> bool:
    return "9012" in execution_detail.get("error", "")
```

**Imports needed** at top of executor.py (add to existing imports):
```python
from app.webhooks.processor import (
    ...existing...,
    get_dual_leg_state,
    set_dual_leg_position,
    clear_dual_leg_position,
    increment_dual_leg_trade_count,
)
```

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_webhook_executor.py`:

```python
def _make_dual_leg_strategy(action="BUY", max_trades=5, broker_id=None):
    return {
        "id": str(uuid.uuid4()),
        "name": "DL Strategy",
        "mode": "live",
        "mapping_template": {
            "symbol": "$.ticker",
            "exchange": "$.exchange",
            "action": "$.action",
            "quantity": "$.qty",
            "order_type": "MARKET",
            "product_type": "FUTURES",
        },
        "rules": {
            "dual_leg": {"enabled": True, "max_trades": max_trades},
        },
        "broker_connection_id": str(broker_id or uuid.uuid4()),
        "is_active": True,
    }


def _make_futures_signal(action="BUY"):
    return StandardSignal(
        symbol="BTCUSDT",
        exchange="EXCHANGE1",
        action=action,
        quantity="1",
        order_type="MARKET",
        product_type="FUTURES",
    )


def _mock_place_live_order(result="filled", detail=None):
    """Patch _place_live_order to return a fixed result."""
    return patch(
        "app.webhooks.executor._place_live_order",
        new_callable=AsyncMock,
        return_value=(result, detail or {"status": result, "order_id": "abc"}),
    )


@pytest.mark.asyncio
async def test_dual_leg_first_signal_opens_only():
    """No existing position → only open leg runs."""
    from app.webhooks.executor import _execute_dual_leg

    redis = AsyncMock()
    strategy = _make_dual_leg_strategy(max_trades=5)
    signal = _make_futures_signal(action="BUY")

    with patch("app.webhooks.executor.get_dual_leg_state", new_callable=AsyncMock, return_value=("", 0)), \
         _mock_place_live_order("filled") as mock_place, \
         patch("app.webhooks.executor.set_dual_leg_position", new_callable=AsyncMock) as mock_set, \
         patch("app.webhooks.executor.increment_dual_leg_trade_count", new_callable=AsyncMock) as mock_incr:

        result, detail = await _execute_dual_leg(
            strategy, signal, uuid.uuid4(), redis,
            {"enabled": True, "max_trades": 5},
        )

    assert result == "opened"
    assert detail["close"] is None
    assert detail["open"] is not None
    mock_place.assert_called_once()  # only open leg
    mock_set.assert_called_once()
    mock_incr.assert_called_once()


@pytest.mark.asyncio
async def test_dual_leg_reversal_closes_then_opens():
    """Existing long position + SELL signal → close long, open short."""
    from app.webhooks.executor import _execute_dual_leg

    redis = AsyncMock()
    strategy = _make_dual_leg_strategy(max_trades=5)
    signal = _make_futures_signal(action="SELL")

    with patch("app.webhooks.executor.get_dual_leg_state", new_callable=AsyncMock, return_value=("long", 1)), \
         _mock_place_live_order("filled") as mock_place, \
         patch("app.webhooks.executor.clear_dual_leg_position", new_callable=AsyncMock) as mock_clear, \
         patch("app.webhooks.executor.set_dual_leg_position", new_callable=AsyncMock) as mock_set, \
         patch("app.webhooks.executor.increment_dual_leg_trade_count", new_callable=AsyncMock):

        result, detail = await _execute_dual_leg(
            strategy, signal, uuid.uuid4(), redis,
            {"enabled": True, "max_trades": 5},
        )

    assert result == "reversed"
    assert detail["close"] is not None
    assert detail["open"] is not None
    assert mock_place.call_count == 2
    mock_clear.assert_called_once()
    mock_set.assert_called_once()


@pytest.mark.asyncio
async def test_dual_leg_stop_condition_closes_only():
    """Max trades reached + existing position → close only, no open."""
    from app.webhooks.executor import _execute_dual_leg

    redis = AsyncMock()
    strategy = _make_dual_leg_strategy(max_trades=3)
    signal = _make_futures_signal(action="BUY")

    with patch("app.webhooks.executor.get_dual_leg_state", new_callable=AsyncMock, return_value=("short", 3)), \
         _mock_place_live_order("filled") as mock_place, \
         patch("app.webhooks.executor.clear_dual_leg_position", new_callable=AsyncMock) as mock_clear, \
         patch("app.webhooks.executor.set_dual_leg_position", new_callable=AsyncMock) as mock_set, \
         patch("app.webhooks.executor.increment_dual_leg_trade_count", new_callable=AsyncMock) as mock_incr:

        result, detail = await _execute_dual_leg(
            strategy, signal, uuid.uuid4(), redis,
            {"enabled": True, "max_trades": 3},
        )

    assert result == "closed"
    assert detail["close"] is not None
    assert detail["open"] is None
    mock_place.assert_called_once()  # only close leg
    mock_clear.assert_called_once()
    mock_set.assert_not_called()
    mock_incr.assert_not_called()


@pytest.mark.asyncio
async def test_dual_leg_no_action_when_stop_and_no_position():
    """Max trades reached + no open position → no-op."""
    from app.webhooks.executor import _execute_dual_leg

    redis = AsyncMock()
    strategy = _make_dual_leg_strategy(max_trades=3)
    signal = _make_futures_signal(action="BUY")

    with patch("app.webhooks.executor.get_dual_leg_state", new_callable=AsyncMock, return_value=("", 3)), \
         _mock_place_live_order("filled") as mock_place:

        result, detail = await _execute_dual_leg(
            strategy, signal, uuid.uuid4(), redis,
            {"enabled": True, "max_trades": 3},
        )

    assert result == "no_action"
    mock_place.assert_not_called()


@pytest.mark.asyncio
async def test_dual_leg_close_fails_aborts_open():
    """Close leg broker error → abort, do not open."""
    from app.webhooks.executor import _execute_dual_leg

    redis = AsyncMock()
    strategy = _make_dual_leg_strategy(max_trades=5)
    signal = _make_futures_signal(action="SELL")

    with patch("app.webhooks.executor.get_dual_leg_state", new_callable=AsyncMock, return_value=("long", 1)), \
         patch("app.webhooks.executor._place_live_order", new_callable=AsyncMock,
               return_value=("broker_error", {"error": "connection timeout"})) as mock_place, \
         patch("app.webhooks.executor.clear_dual_leg_position", new_callable=AsyncMock) as mock_clear:

        result, detail = await _execute_dual_leg(
            strategy, signal, uuid.uuid4(), redis,
            {"enabled": True, "max_trades": 5},
        )

    assert result == "close_failed"
    assert detail["open"] is None
    mock_place.assert_called_once()  # only close attempt
    mock_clear.assert_not_called()  # position_side unchanged


@pytest.mark.asyncio
async def test_dual_leg_9012_treated_as_already_closed():
    """Close returns 9012 (position not found) → treat as already closed, proceed to open."""
    from app.webhooks.executor import _execute_dual_leg

    redis = AsyncMock()
    strategy = _make_dual_leg_strategy(max_trades=5)
    signal = _make_futures_signal(action="SELL")

    close_detail = {"error": "Exchange1 API error 500: {\"code\":500,\"data\":\"9012 The position was not found\"}"}
    open_detail = {"status": "filled", "order_id": "xyz"}

    with patch("app.webhooks.executor.get_dual_leg_state", new_callable=AsyncMock, return_value=("long", 1)), \
         patch("app.webhooks.executor._place_live_order", new_callable=AsyncMock,
               side_effect=[("broker_error", close_detail), ("filled", open_detail)]) as mock_place, \
         patch("app.webhooks.executor.clear_dual_leg_position", new_callable=AsyncMock) as mock_clear, \
         patch("app.webhooks.executor.set_dual_leg_position", new_callable=AsyncMock) as mock_set, \
         patch("app.webhooks.executor.increment_dual_leg_trade_count", new_callable=AsyncMock):

        result, detail = await _execute_dual_leg(
            strategy, signal, uuid.uuid4(), redis,
            {"enabled": True, "max_trades": 5},
        )

    assert result == "reversed"
    assert detail["close"] == {"status": "already_closed"}
    assert detail["open"] == open_detail
    assert mock_place.call_count == 2
    mock_clear.assert_called_once()
    mock_set.assert_called_once()


@pytest.mark.asyncio
async def test_dual_leg_no_action_when_same_side():
    """Already long + BUY signal → no-op (already in correct position)."""
    from app.webhooks.executor import _execute_dual_leg

    redis = AsyncMock()
    strategy = _make_dual_leg_strategy(max_trades=5)
    signal = _make_futures_signal(action="BUY")

    with patch("app.webhooks.executor.get_dual_leg_state", new_callable=AsyncMock, return_value=("long", 1)), \
         _mock_place_live_order("filled") as mock_place:

        result, detail = await _execute_dual_leg(
            strategy, signal, uuid.uuid4(), redis,
            {"enabled": True, "max_trades": 5},
        )

    assert result == "no_action"
    mock_place.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_webhook_executor.py -k "dual_leg" -v 2>&1 | tail -15
```

Expected: `ImportError` — `_execute_dual_leg` not defined yet.

- [ ] **Step 3: Add imports to executor.py**

In `backend/app/webhooks/executor.py`, update the import from `processor`:

```python
from app.webhooks.processor import (
    evaluate_rules,
    get_strategy_counts,
    increment_signals_today,
    update_position_count,
    get_dual_leg_state,
    set_dual_leg_position,
    clear_dual_leg_position,
    increment_dual_leg_trade_count,
)
```

- [ ] **Step 4: Add `_is_position_not_found` helper and `_execute_dual_leg` to executor.py**

Add after `_execute_paper` and before `execute()`:

```python
def _is_position_not_found(execution_detail: dict) -> bool:
    """Return True if broker error indicates the position was already closed (Exchange1 9012)."""
    return "9012" in execution_detail.get("error", "")


def _is_stop_condition(dual_leg_config: dict, strategy: dict, trade_count: int) -> bool:
    """Return True if no new open legs should be placed."""
    max_trades = dual_leg_config.get("max_trades", 0)
    if max_trades and trade_count >= max_trades:
        return True
    if hours := strategy.get("rules", {}).get("trading_hours"):
        from zoneinfo import ZoneInfo
        from datetime import datetime
        tz = ZoneInfo(hours.get("timezone", "Asia/Kolkata"))
        now_time = datetime.now(tz).time()
        from datetime import datetime as dt
        start = dt.strptime(hours["start"], "%H:%M").time()
        end = dt.strptime(hours["end"], "%H:%M").time()
        if not (start <= now_time <= end):
            return True
    return False


async def _execute_dual_leg(
    strategy: dict,
    signal: StandardSignal,
    tenant_id: uuid.UUID,
    redis,
    dual_leg_config: dict,
) -> tuple[str, dict]:
    """Execute close-then-open legs for a dual-leg strategy.

    Returns (execution_result, execution_detail) where:
    - execution_result: "opened" | "reversed" | "closed" | "close_failed" |
                        "open_failed" | "no_action"
    - execution_detail: {"close": OrderResponse|None, "open": OrderResponse|None}
    """
    strategy_id = strategy["id"]
    broker_connection_id = strategy["broker_connection_id"]
    action = signal.action.upper()  # "BUY" or "SELL"
    opposite_action = "SELL" if action == "BUY" else "BUY"
    new_side = "long" if action == "BUY" else "short"
    current_side_map = {"BUY": "long", "SELL": "short"}
    existing_side_for_action = current_side_map[action]

    position_side, trade_count = await get_dual_leg_state(redis, strategy_id)
    stop = _is_stop_condition(dual_leg_config, strategy, trade_count)

    # Determine what to do
    need_close = (
        position_side != ""
        and (stop or position_side != existing_side_for_action)
    )
    need_open = not stop and (
        position_side == "" or position_side != existing_side_for_action
    )
    same_side = (position_side == existing_side_for_action)

    if same_side and not stop:
        return "no_action", {"close": None, "open": None}

    if not need_close and not need_open:
        return "no_action", {"close": None, "open": None}

    close_detail = None
    open_detail = None

    # --- Close leg ---
    if need_close:
        close_signal = StandardSignal(
            symbol=signal.symbol,
            exchange=signal.exchange,
            action=opposite_action,
            quantity=signal.quantity,
            order_type="MARKET",
            product_type=signal.product_type,
            leverage=signal.leverage,
            position_model=signal.position_model,
        )
        exec_result, exec_detail = await _place_live_order(
            broker_connection_id, tenant_id, strategy_id, close_signal, redis,
            update_redis=False,
        )

        if exec_result in ("filled", "accepted"):
            close_detail = exec_detail
            await clear_dual_leg_position(redis, strategy_id)
        elif _is_position_not_found(exec_detail):
            # Position already closed on exchange — treat as success
            close_detail = {"status": "already_closed"}
            await clear_dual_leg_position(redis, strategy_id)
        else:
            # Close genuinely failed — abort
            logger.warning(
                "dual_leg_close_failed",
                strategy_id=strategy_id,
                error=exec_detail.get("error"),
            )
            return "close_failed", {"close": exec_detail, "open": None}

    # --- Open leg ---
    if need_open:
        exec_result, exec_detail = await _place_live_order(
            broker_connection_id, tenant_id, strategy_id, signal, redis,
            update_redis=False,
        )
        open_detail = exec_detail

        if exec_result in ("filled", "accepted"):
            await set_dual_leg_position(redis, strategy_id, new_side)
            await increment_dual_leg_trade_count(redis, strategy_id)
            await increment_signals_today(redis, strategy_id)
            outcome = "reversed" if need_close else "opened"
        else:
            logger.warning(
                "dual_leg_open_failed",
                strategy_id=strategy_id,
                error=exec_detail.get("error"),
            )
            outcome = "open_failed"

        return outcome, {"close": close_detail, "open": open_detail}

    # Only close leg ran (stop condition)
    await increment_signals_today(redis, strategy_id)
    return "closed", {"close": close_detail, "open": None}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && .venv/bin/pytest tests/test_webhook_executor.py -k "dual_leg" -v 2>&1 | tail -20
```

Expected: all 7 dual-leg tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/webhooks/executor.py backend/tests/test_webhook_executor.py
git commit -m "feat: implement _execute_dual_leg with close-then-open logic"
```

---

## Task 4: Wire `_execute_dual_leg` into `execute()`

**Files:**
- Modify: `backend/app/webhooks/executor.py`
- Modify: `backend/tests/test_webhook_executor.py`

### Context

In `execute()`, the live branch currently builds asyncio Tasks for `_place_live_order` and gathers them. We extend this so that:

- If `dual_leg.enabled` → create task for `_execute_dual_leg` (returns `(str, dict)` same as `_place_live_order`)
- Otherwise → existing `_place_live_order` task (unchanged)

Both task types return `(execution_result, execution_detail)` so the gather loop handles them identically.

The existing test `test_execute_live_mode_enqueues_arq_job` tests for `arq_redis.enqueue_job` which no longer happens (we now call `_place_live_order` directly). Update it to test the new behaviour.

- [ ] **Step 1: Update the existing live-mode test**

In `backend/tests/test_webhook_executor.py`, replace `test_execute_live_mode_enqueues_arq_job` with:

```python
@pytest.mark.asyncio
async def test_execute_live_mode_places_order_synchronously():
    """Live mode calls _place_live_order directly (no ARQ queue)."""
    broker_id = uuid.uuid4()
    strategy = _make_strategy(mode="live", broker_connection_id=broker_id)
    redis = AsyncMock()
    redis.mget.return_value = [None, None]
    session = AsyncMock()

    with patch("app.webhooks.executor._place_live_order", new_callable=AsyncMock,
               return_value=("filled", {"status": "filled", "order_id": "abc"})) as mock_place:
        results = await execute([strategy], _make_payload(), redis, session, tenant_id=uuid.uuid4())

    assert results[0].execution_result == "filled"
    mock_place.assert_called_once()
```

- [ ] **Step 2: Add a test for dual-leg routing in `execute()`**

Append to `backend/tests/test_webhook_executor.py`:

```python
@pytest.mark.asyncio
async def test_execute_live_mode_routes_to_dual_leg_when_enabled():
    """execute() calls _execute_dual_leg when dual_leg.enabled is true."""
    broker_id = uuid.uuid4()
    strategy = _make_strategy(
        mode="live",
        broker_connection_id=broker_id,
        rules={"dual_leg": {"enabled": True, "max_trades": 5}},
    )
    redis = AsyncMock()
    redis.mget.return_value = [None, None]
    session = AsyncMock()

    with patch("app.webhooks.executor._execute_dual_leg", new_callable=AsyncMock,
               return_value=("opened", {"close": None, "open": {"status": "filled"}})) as mock_dual, \
         patch("app.webhooks.executor._place_live_order", new_callable=AsyncMock) as mock_single:

        results = await execute([strategy], _make_payload(), redis, session, tenant_id=uuid.uuid4())

    assert results[0].execution_result == "opened"
    mock_dual.assert_called_once()
    mock_single.assert_not_called()
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_webhook_executor.py::test_execute_live_mode_places_order_synchronously tests/test_webhook_executor.py::test_execute_live_mode_routes_to_dual_leg_when_enabled -v 2>&1 | tail -15
```

Expected: both FAIL (old test checks ARQ enqueue; new routing test fails because dual_leg branch doesn't exist).

- [ ] **Step 4: Update the live branch in `execute()`**

In `backend/app/webhooks/executor.py`, find the `elif mode == "live":` block inside `execute()`. Replace it with:

```python
        elif mode == "live":
            if not strategy.get("broker_connection_id"):
                results.append(SignalResult(
                    strategy_id=strategy["id"],
                    rule_result="passed",
                    parsed_signal=signal.model_dump(mode="json"),
                    execution_result="no_broker_connection",
                ))
                continue

            if tenant_id is None:
                results.append(SignalResult(
                    strategy_id=strategy["id"],
                    rule_result="passed",
                    parsed_signal=signal.model_dump(mode="json"),
                    execution_result="no_tenant_id",
                ))
                continue

            signal_id = uuid.uuid4()
            idx = len(results)
            results.append(SignalResult(
                strategy_id=strategy["id"],
                rule_result="passed",
                parsed_signal=signal.model_dump(mode="json"),
                execution_result="pending",
                signal_id=signal_id,
            ))

            dual_leg_config = (strategy.get("rules") or {}).get("dual_leg", {})
            if dual_leg_config.get("enabled"):
                t = asyncio.create_task(
                    _execute_dual_leg(
                        strategy,
                        signal,
                        tenant_id,
                        redis,
                        dual_leg_config,
                    )
                )
            else:
                t = asyncio.create_task(
                    _place_live_order(
                        strategy["broker_connection_id"],
                        tenant_id,
                        strategy["id"],
                        signal,
                        redis,
                    )
                )
            logger.info(
                "live_order_started",
                strategy_id=strategy["id"],
                strategy=strategy.get("name"),
                symbol=signal.symbol,
                action=signal.action,
                dual_leg=bool(dual_leg_config.get("enabled")),
            )
            live_tasks.append(t)
            live_task_indices.append(idx)
```

- [ ] **Step 5: Run all executor tests**

```bash
cd backend && .venv/bin/pytest tests/test_webhook_executor.py -v 2>&1 | tail -25
```

Expected: all tests PASS. If `test_execute_live_mode_enqueues_arq_job` still exists and fails, delete it (it was renamed in Step 1).

- [ ] **Step 6: Run the full test suite to check for regressions**

```bash
cd backend && .venv/bin/pytest tests/ -x -q 2>&1 | tail -20
```

Expected: no failures unrelated to this feature.

- [ ] **Step 7: Commit**

```bash
git add backend/app/webhooks/executor.py backend/tests/test_webhook_executor.py
git commit -m "feat: route dual-leg strategies to _execute_dual_leg in execute()"
```

---

## Task 5: Deploy

- [ ] **Step 1: Rsync backend to server**

```bash
SERVER_PASS=$(grep '^password:' ../contabo-server.txt | awk '{print $2}')
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e rsync -avz --progress -e "ssh -o StrictHostKeyChecking=no" \
  --exclude=".venv" --exclude="__pycache__" --exclude=".pytest_cache" \
  --exclude="*.egg-info" --exclude=".env" \
  backend/ root@194.61.31.226:/opt/algomatter/backend/'
```

- [ ] **Step 2: Re-apply CORS patch**

```bash
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e ssh -o StrictHostKeyChecking=no root@194.61.31.226 \
  "sed -i '"'"'/\"http:\/\/127.0.0.1:5173\",/a\\        \"https://algomatter.in\",\n        \"https://www.algomatter.in\",\n        \"http://194.61.31.226\",'"'"' /opt/algomatter/backend/app/main.py"'
```

- [ ] **Step 3: Restart services**

```bash
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e ssh -o StrictHostKeyChecking=no root@194.61.31.226 \
  "systemctl restart algomatter-api algomatter-worker algomatter-strategy-runner"'
```

- [ ] **Step 4: Verify health**

```bash
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e ssh -o StrictHostKeyChecking=no root@194.61.31.226 \
  "sleep 8 && curl -s https://algomatter.in/api/v1/health"'
```

Expected: `{"database":"ok","redis":"ok"}`

- [ ] **Step 5: Enable dual-leg on a strategy for testing**

```bash
SSHPASS="$SERVER_PASS" nix-shell -p sshpass --run \
  'sshpass -e ssh -o StrictHostKeyChecking=no root@194.61.31.226 \
  "docker exec -i algomatter-postgres-1 psql -U algomatter -d algomatter -c \
  \"UPDATE strategies SET rules = rules || jsonb_build_object('"'"'dual_leg'"'"', jsonb_build_object('"'"'enabled'"'"', true, '"'"'max_trades'"'"', 10)) WHERE slug = '"'"'YOUR_STRATEGY_SLUG'"'"';\""'
```

Replace `YOUR_STRATEGY_SLUG` with the actual strategy slug.

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "chore: deploy dual-leg webhook execution to production"
```
