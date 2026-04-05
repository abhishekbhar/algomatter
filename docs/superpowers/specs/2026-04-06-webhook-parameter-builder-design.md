# Webhook Strategy Parameter Builder — Design Spec

**Date:** 2026-04-06
**Status:** Approved

---

## Overview

Replace the raw JSON `mapping_template` textarea in the webhook strategy creation form with a guided parameter builder UI. Users configure each order parameter as either a fixed value or a field name from the incoming signal JSON. The UI auto-generates:
1. The `mapping_template` JSON sent to the backend (no backend changes)
2. A ready-to-paste TradingView alert message the user can copy

Target users are non-technical traders who use TradingView Pine Script alerts but don't know JSONPath.

---

## Architecture

### No backend changes required

The existing `mapping_template` field stores a JSON object where:
- A plain value (`"BTCUSDT"`, `10`) = fixed — always send this value
- A JSONPath string (`"$.action"`, `"$.qty"`) = from signal — read from incoming webhook payload

The new UI generates this same JSON structure. The backend webhook handler is untouched.

**Example output of the builder:**
```json
{
  "symbol": "BTCUSDT",
  "action": "$.action",
  "order_type": "MARKET",
  "quantity": "$.qty",
  "leverage": 10
}
```

---

## Order Types

Two modes, selectable via tab:

### Futures (default)
| Parameter | Required | Notes |
|-----------|----------|-------|
| symbol | Yes | Select from Exchange1 instrument list |
| action | Yes | BUY (open long) or SELL (close) |
| order_type | Yes | MARKET or LIMIT |
| quantity | Yes | Number of contracts |
| leverage | Yes | 1–100×, default 10× |
| position_model | No | Isolated (default) or Cross |
| price | No | Required if LIMIT |
| take_profit_price | No | Optional |
| stop_loss_price | No | Optional |

### Spot
| Parameter | Required | Notes |
|-----------|----------|-------|
| symbol | Yes | Select from Exchange1 instrument list |
| action | Yes | BUY or SELL |
| order_type | Yes | MARKET or LIMIT |
| quantity | Yes | Amount in base asset |
| price | No | Required if LIMIT |

---

## Component Structure

```
components/strategies/
  WebhookParameterBuilder.tsx   # Main builder component (replaces Textarea)
  ParameterRow.tsx              # Single row: name + Fixed/Signal toggle + value input
  TradingViewPreview.tsx        # Right-panel JSON preview with copy button
```

**`WebhookParameterBuilder` props:**
```ts
interface Props {
  value: Record<string, unknown> | null;          // current mapping_template value
  onChange: (value: Record<string, unknown>) => void; // emits on every change
}
```

The parent form (`new/page.tsx`) keeps `mapping_template` as `Record<string, unknown>` internally and serializes to JSON only at submit time (already done by `JSON.parse` in the existing handler — this will simplify it).

---

## UI Layout

Two-column layout on desktop, single column on mobile:

**Left column — Parameter form:**
- `Tabs` (Futures / Spot) — Chakra UI `Tabs` component with `colorScheme="blue"`
- Parameter rows in a `VStack`
- Each row: `Grid` with 3 columns — param name, source toggle, value input
- Optional parameters hidden behind a `<Button variant="link">` expand toggle
- Source toggle: two `Button` components — active one uses `colorScheme="green"` (Fixed) or `colorScheme="orange"` (From signal)

**Right column — Live preview:**
- `Box` with `bg="gray.900"` (dark mode) / `bg="gray.50"` (light)
- Webhook URL display with copy button
- JSON preview with color-coded values (green = fixed, orange = from signal)
- "How to use" accordion with TradingView steps

On mobile (`base`): stack vertically, preview below form.

---

## Integration Point

In `app/(dashboard)/strategies/new/page.tsx`:

Replace:
```tsx
<FormControl>
  <FormLabel>Mapping Template (JSON)</FormLabel>
  <Textarea ... />
</FormControl>
```

With:
```tsx
<WebhookParameterBuilder
  value={form.mapping_template_obj}
  onChange={(val) => setForm({ ...form, mapping_template_obj: val })}
/>
```

The form state changes from `mapping_template: string` to `mapping_template_obj: Record<string, unknown> | null`, serialized at submit.

---

## TradingView JSON Generation

For each "From signal" parameter with field name `foo`, emit `"{{foo}}"` (TradingView template syntax). For fixed parameters, emit the literal value.

Example (futures, action+qty from signal, everything else fixed):
```json
{
  "action": "{{action}}",
  "qty": "{{qty}}",
  "symbol": "BTCUSDT",
  "order_type": "MARKET",
  "leverage": 10
}
```

The right-panel shows this JSON. User copies it into their TradingView alert "Message" field.

Note: The `mapping_template` sent to the backend uses `"$.action"` JSONPath format, not TradingView `{{action}}` syntax. These are two separate outputs from the same form state.

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `components/strategies/WebhookParameterBuilder.tsx` | Create |
| `components/strategies/ParameterRow.tsx` | Create |
| `components/strategies/TradingViewPreview.tsx` | Create |
| `app/(dashboard)/strategies/new/page.tsx` | Modify — replace Textarea with builder |

---

## Out of Scope

- Editing existing strategies (can be added later; new/page.tsx is the focus)
- Supporting non-Exchange1 brokers (hardcode Exchange1 params for now)
- Drag-and-drop field mapping (Approach B — not chosen)
- Pre-built TradingView templates (Approach C — partially covered by the JSON preview)
- Backend changes to `mapping_template` schema

---

## Key Constraints

- Use Chakra UI v2 components only — no new UI libraries
- Follow existing patterns: `useDisclosure`, `apiClient`, `useToast`, Chakra color tokens
- `SymbolSelect` component already exists — reuse it for the symbol parameter
- Mobile-responsive: `Grid` columns collapse on small screens
- No new dependencies
