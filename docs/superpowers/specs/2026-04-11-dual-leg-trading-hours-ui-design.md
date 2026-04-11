# Dual-Leg & Trading Hours — Strategy Form UI

**Date:** 2026-04-11
**Scope:** Add dual-leg and trading hours configuration to strategy create and edit pages

---

## 1. Context

The backend already supports two `rules` fields that have no UI:

- `rules.trading_hours` — restricts signal execution to a time window; used by both the general signal processor and `_is_stop_condition` in dual-leg execution
- `rules.dual_leg` — enables reverse-trade mode (close opposite position, open new one)

Neither field is exposed in the frontend. This spec adds collapsible UI panels for both in the Rules section of the strategy create and edit pages.

---

## 2. Backend Contract

Both fields live inside the `rules` JSON column:

```json
{
  "rules": {
    "symbol_whitelist": [],
    "symbol_blacklist": [],
    "max_positions": 10,
    "max_signals_per_day": 50,
    "trading_hours": {
      "start": "09:15",
      "end": "15:30",
      "timezone": "Asia/Kolkata"
    },
    "dual_leg": {
      "enabled": true,
      "max_trades": 5
    }
  }
}
```

- `trading_hours` is omitted from the payload when the panel is disabled
- `dual_leg` is omitted from the payload when the panel is disabled
- `max_trades: 0` means unlimited

---

## 3. Form State

Both `new/page.tsx` and `edit/page.tsx` extend their `StrategyForm` interface with:

```typescript
// Trading hours
trading_hours_enabled: boolean      // default: false
trading_hours_start: string         // default: "09:15"
trading_hours_end: string           // default: "15:30"
trading_hours_timezone: string      // default: "Asia/Kolkata"

// Dual-leg
dual_leg_enabled: boolean           // default: false
dual_leg_max_trades: number         // default: 5
```

**Create page defaults:** all off, time defaults pre-filled so the user only needs to flip the toggle.

**Edit page initialization** (inside existing `useEffect`):
```typescript
const dualLeg = (rules.dual_leg ?? {}) as Record<string, unknown>;
const tradingHours = (rules.trading_hours ?? null) as Record<string, unknown> | null;

trading_hours_enabled: !!tradingHours,
trading_hours_start: String(tradingHours?.start ?? "09:15"),
trading_hours_end: String(tradingHours?.end ?? "15:30"),
trading_hours_timezone: String(tradingHours?.timezone ?? "Asia/Kolkata"),
dual_leg_enabled: Boolean(dualLeg.enabled),
dual_leg_max_trades: Number(dualLeg.max_trades ?? 5),
```

**Submit payload construction** (conditional inclusion):
```typescript
rules: {
  // existing fields...
  ...(form.trading_hours_enabled
    ? { trading_hours: { start: form.trading_hours_start, end: form.trading_hours_end, timezone: form.trading_hours_timezone } }
    : {}),
  ...(form.dual_leg_enabled
    ? { dual_leg: { enabled: true, max_trades: form.dual_leg_max_trades } }
    : {}),
}
```

---

## 4. UI Layout

Both panels are added inside the existing Rules card, after `max_signals_per_day`. Each panel uses a collapsible pattern matching the existing "Show optional parameters" UX in `WebhookParameterBuilder`.

### Trading Hours Panel

```
▼ Trading Hours                          [Switch]
   Start   [09:15]    End   [15:30]
   Timezone  [Asia/Kolkata ▾]
```

- Panel expands on header click OR when Switch is turned on
- Time inputs use `type="time"` (native HH:MM browser picker, no dependency)
- Inputs are disabled (greyed out) when Switch is off
- Timezone select options: `Asia/Kolkata`, `UTC`, `US/Eastern`, `US/Pacific`

### Dual-Leg Execution Panel

```
▼ Dual-Leg Execution                     [Switch]
   Max Trades   [5]
   (0 = unlimited)
```

- `max_trades` input is only visible when Switch is on
- `type="number"`, `min={0}`, integer only

Both panels are collapsed by default when the corresponding rule is not set.

---

## 5. Validation

Applied on form submit, consistent with existing form validation style (toast notifications):

- If `trading_hours_enabled` and `start >= end`: show toast — "Trading hours: start time must be before end time"
- `max_trades`: browser-enforced `min={0}`, no additional toast needed
- Disabling a panel entirely is always valid (fields are optional)

---

## 6. Files Changed

| File | Change |
|------|--------|
| `frontend/app/(dashboard)/strategies/new/page.tsx` | Extend form state, add panels, update submit payload |
| `frontend/app/(dashboard)/strategies/[id]/edit/page.tsx` | Extend form state, update useEffect, add panels, update submit payload |

No new components, no new API hooks — changes are self-contained within the two page files.
