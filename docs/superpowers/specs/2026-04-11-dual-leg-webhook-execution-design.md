# Dual-Leg Webhook Execution Design

## Goal

When a webhook signal arrives, automatically close the opposite open position before opening a new one in the signal's direction. Controlled by a feature flag per strategy. Supports stop conditions (max trades, trading hours, strategy inactive) that switch the strategy to close-only mode.

## Architecture

All dual-leg logic lives inside `execute()` in `backend/app/webhooks/executor.py` as a pre-execution step before `_place_live_order`. No new files required. Existing single-leg behaviour is unchanged when the flag is off.

**Tech Stack:** FastAPI, SQLAlchemy, Redis (state), Exchange1 adapter (`closeType: "all"` for full close)

---

## Section 1: Configuration

`dual_leg` is an optional key inside the strategy's existing `rules` JSON column. No DB migration required.

```json
{
  "dual_leg": {
    "enabled": true,
    "max_trades": 5
  }
}
```

| Field | Type | Description |
|---|---|---|
| `enabled` | bool | Activates dual-leg mode for this strategy |
| `max_trades` | int | Max number of open legs placed. Close-only legs do not count. |

When `dual_leg` is absent or `enabled: false`, behaviour is identical to today.

Existing rules (`trading_hours`, `max_signals_per_day`, `max_open_positions`) continue to work independently and are evaluated before dual-leg logic runs.

---

## Section 2: Redis State

Two new keys per strategy, both with 24-hour TTL (reset daily):

```
dual_leg:{strategy_id}:position_side   →  "long" | "short" | ""
dual_leg:{strategy_id}:trade_count     →  int
```

- `position_side` — direction of the currently open position. Empty string means no open position.
- `trade_count` — number of open legs successfully placed today.
- Both keys are set/cleared atomically within the execution path.
- On broker error: state is NOT updated (Redis reflects last known good state).

---

## Section 3: Execution Flow

Triggered inside `execute()` for live-mode strategies where `dual_leg.enabled == true`.

### Step 1 — Read Redis state
```
position_side = await redis.get(f"dual_leg:{strategy_id}:position_side") or ""
trade_count   = int(await redis.get(f"dual_leg:{strategy_id}:trade_count") or 0)
```

### Step 2 — Evaluate stop condition
Stop condition is met when **any** of the following is true:
- `trade_count >= dual_leg.max_trades`
- Current time is outside `rules.trading_hours` (if configured)

> **Note:** `strategy.is_active == False` is not checked here — inactive strategies are filtered out by `_get_active_strategies()` (queries `Strategy.is_active.is_(True)`) before `execute()` is called. The routing layer handles deactivation.

### Step 3 — Determine legs to execute

| `position_side` | Stop condition | Signal action | Close leg | Open leg |
|---|---|---|---|---|
| `""` | false | BUY | — | open LONG |
| `""` | false | SELL | — | open SHORT |
| `""` | true | any | — | — (no-op) |
| `"long"` | false | BUY | — (already long) | — (no-op, skip) |
| `"long"` | false | SELL | close LONG | open SHORT |
| `"long"` | true | any | close LONG | — |
| `"short"` | false | SELL | — (already short) | — (no-op, skip) |
| `"short"` | false | BUY | close SHORT | open LONG |
| `"short"` | true | any | close SHORT | — |

### Step 4 — Execute legs (sequentially, close before open)

**Close leg** (when needed):
- Call `_place_live_order` with opposite action (`BUY`→`SELL`, `SELL`→`BUY`), same symbol/quantity
- Exchange1: uses `closeType: "all"` (full position close)
- If close fails → abort, do not attempt open leg

**Open leg** (when needed, only if close succeeded or no close required):
- Call `_place_live_order` with the signal's action
- If open fails → log error, do not increment `trade_count`

### Step 5 — Update Redis state

| Event | Redis update |
|---|---|
| Close succeeded | `position_side = ""` |
| Open succeeded | `position_side = "long"/"short"`, `trade_count += 1` |
| Close failed | No change |
| Open failed (close succeeded) | `position_side = ""` (close is reflected), no trade_count increment |
| No-op | No change |

---

## Section 4: Error Handling

**Close leg fails:**
- Abort — do not open new position
- `execution_result: "close_failed"`
- `execution_detail: { "close": { broker error }, "open": null }`
- Redis unchanged

**Close leg returns "position not found" (error 9012):**
- Position was already closed externally (manually on Exchange1 UI or by another system)
- Treat as "close succeeded" — clear `position_side` in Redis
- Proceed to open leg as normal
- `execution_result` reflects the open outcome (`"opened"` or `"open_failed"`)
- `execution_detail.close` records `{ "status": "already_closed" }`

**Open leg fails (after successful close):**
- `execution_result: "open_failed"`
- `execution_detail: { "close": { close result }, "open": { broker error } }`
- `position_side` cleared (close succeeded)
- `trade_count` NOT incremented

**No-op (already correct side, or stop condition + nothing open):**
- No broker calls
- `execution_result: "no_action"`
- Redis unchanged

**Multi-strategy / multi-user isolation:**
- Redis keys are scoped to `strategy_id` (UUID, unique per tenant)
- Multiple users or multiple strategies per user never share state, even when trading the same symbol

---

## Section 5: Signal Logging

Each dual-leg signal produces **one** `WebhookSignal` record:

| Field | Value |
|---|---|
| `parsed_signal` | Incoming signal as-is |
| `execution_result` | `"opened"` \| `"reversed"` \| `"closed"` \| `"close_failed"` \| `"open_failed"` \| `"no_action"` |
| `execution_detail` | `{ "close": OrderResponse or null, "open": OrderResponse or null }` |

`execution_result` values:
- `"opened"` — first signal, only open leg executed
- `"reversed"` — both legs executed (close + open)
- `"closed"` — stop condition met, only close leg executed
- `"close_failed"` — close leg failed, open aborted
- `"open_failed"` — close succeeded, open failed
- `"no_action"` — no-op (already correct side or stop condition + no open position)

---

## Section 6: Scope Boundaries

**In scope:**
- Live mode strategies only
- Exchange1 broker (full close via `closeType: "all"`)
- Backend execution logic only

**Out of scope:**
- Paper mode (paper trading keeps existing single-leg behaviour)
- Frontend UI for configuring `dual_leg` rules (configure via API/DB directly for now)
- Automatic position close at trading hours end (close happens on next incoming signal)
- Partial position close (always full close)

---

## Section 7: Files Changed

| File | Change |
|---|---|
| `backend/app/webhooks/executor.py` | Add `_execute_dual_leg()` helper, call from `execute()` live branch when `dual_leg.enabled` |
| `backend/app/webhooks/processor.py` | Add `get_dual_leg_state()` and `set_dual_leg_state()` Redis helpers |
| No DB migration required | `dual_leg` lives in existing `rules` JSON column |
