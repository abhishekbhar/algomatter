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

**Example output of the builder (backend mapping_template):**
```json
{
  "symbol": "BTCUSDT",
  "exchange": "EXCHANGE1",
  "action": "$.action",
  "order_type": "MARKET",
  "quantity": "$.qty",
  "product_type": "FUTURES",
  "leverage": 10
}
```

**Example TradingView alert message (separate output, same state):**
```json
{
  "action": "{{action}}",
  "qty": "{{qty}}"
}
```

The TradingView JSON uses only the "From signal" fields. The key is the user-entered field name (the signal side), not the parameter name. Fixed values are not included — TradingView doesn't need them since they're hardcoded in the template.

---

## StandardSignal field names

The builder maps to `StandardSignal` (backend schema). Use exactly these field names as keys in `mapping_template`:

| Field | Type | Notes |
|-------|------|-------|
| `symbol` | str | Required |
| `exchange` | str | Required |
| `action` | str | BUY or SELL |
| `quantity` | Decimal | Required |
| `order_type` | str | MARKET, LIMIT |
| `product_type` | str | INTRADAY, DELIVERY, FUTURES |
| `price` | Decimal? | LIMIT orders only |
| `leverage` | int? | Futures only, emitted as JS number |
| `position_model` | str? | "isolated" or "cross" |
| `take_profit` | Decimal? | Futures only |
| `stop_loss` | Decimal? | Futures only |

---

## Order Types

Two modes, selectable via tab:

### Futures (default)
| Parameter | UI Label | `mapping_template` key | Required | Input type | Notes |
|-----------|----------|------------------------|----------|------------|-------|
| symbol | Symbol | `symbol` | Yes | SymbolSelect (exchange="EXCHANGE1") | |
| exchange | Exchange | `exchange` | Yes | Hidden fixed = "EXCHANGE1" | Always fixed, not shown to user |
| action | Action | `action` | Yes | Select (BUY/SELL) or From signal | |
| order_type | Order Type | `order_type` | Yes | Select (MARKET/LIMIT) | |
| quantity | Quantity | `quantity` | Yes | NumberInput or From signal | Emits JS number when fixed |
| product_type | — | `product_type` | Yes | Hidden fixed = "FUTURES" | Always fixed, not shown to user |
| leverage | Leverage | `leverage` | Yes | Select (1–100×), default 10 | Emits JS number (not string) |
| position_model | Margin Mode | `position_model` | No | Select (isolated/cross), always emitted | Default "isolated"; always emitted even if not changed |
| price | Price | `price` | No | NumberInput or From signal | Show only when order_type=LIMIT |
| take_profit | Take Profit | `take_profit` | No | NumberInput or From signal | Optional, in collapsible section |
| stop_loss | Stop Loss | `stop_loss` | No | NumberInput or From signal | Optional, in collapsible section |

### Spot
| Parameter | UI Label | `mapping_template` key | Required | Input type | Notes |
|-----------|----------|------------------------|----------|------------|-------|
| symbol | Symbol | `symbol` | Yes | SymbolSelect (exchange="EXCHANGE1") | |
| exchange | Exchange | `exchange` | Yes | Hidden fixed = "EXCHANGE1" | Always fixed |
| action | Action | `action` | Yes | Select or From signal | |
| order_type | Order Type | `order_type` | Yes | Select (MARKET/LIMIT) | |
| quantity | Quantity | `quantity` | Yes | NumberInput or From signal | |
| product_type | — | `product_type` | Yes | Hidden fixed = "DELIVERY" | Always fixed |
| price | Price | `price` | No | NumberInput or From signal | Show only when order_type=LIMIT |

---

## Component Structure

```
components/strategies/
  WebhookParameterBuilder.tsx   # Main builder — renders form + preview side-by-side
  ParameterRow.tsx              # Single row: name + Fixed/Signal toggle + value input
  TradingViewPreview.tsx        # JSON preview panel + webhook URL
```

### `WebhookParameterBuilder` props
```ts
interface Props {
  value: Record<string, unknown> | null;           // current mapping_template object
  onChange: (value: Record<string, unknown>) => void;
  webhookUrl?: string;                             // passed from parent via useWebhookConfig()
}
```

### `ParameterRow` props
```ts
interface Props {
  label: string;
  fieldKey: string;              // mapping_template key (e.g. "action")
  required?: boolean;
  source: "fixed" | "signal";
  fixedValue: string | number | null;
  signalField: string;           // e.g. "action"
  inputType: "text" | "number" | "select";
  selectOptions?: { value: string; label: string }[];
  onSourceChange: (source: "fixed" | "signal") => void;
  onFixedChange: (value: string | number) => void;
  onSignalFieldChange: (fieldName: string) => void;
}
```

### `TradingViewPreview` props
```ts
interface Props {
  mappingTemplate: Record<string, unknown>;  // rendered as JSON
  webhookUrl?: string;
}
```

---

## Integration: `new/page.tsx` changes

### 1. Update `StrategyForm` interface
```ts
interface StrategyForm {
  name: string;
  broker_connection_id: string;
  mode: string;
  is_active: boolean;
  mapping_template_obj: Record<string, unknown> | null;  // replaces mapping_template: string
  symbol_whitelist: string;
  symbol_blacklist: string;
  max_positions: number;
  max_signals_per_day: number;
}
```

### 2. Update initial state
```ts
mapping_template_obj: null,
```

### 3. Fetch webhook URL in parent
```ts
const { data: webhookConfig } = useWebhookConfig();
```

### 4. Replace Textarea
```tsx
// Remove:
<FormControl>
  <FormLabel>Mapping Template (JSON)</FormLabel>
  <Textarea ... />
</FormControl>

// Add:
<WebhookParameterBuilder
  value={form.mapping_template_obj}
  onChange={(val) => setForm({ ...form, mapping_template_obj: val })}
  webhookUrl={webhookConfig?.webhook_url}
/>
```

### 5. Update handleSubmit
```ts
mapping_template: form.mapping_template_obj ?? undefined,
// (remove the old JSON.parse call)
```

### 6. Widen the page container
The parent `<Box maxW="600px">` will clip the two-column layout. Widen to `maxW="900px"`.

---

## Numeric type handling

Fields with `inputType: "number"` must emit JavaScript `number` values (not strings) when fixed:
- Use Chakra `NumberInput` + `onChange={(_, valAsNumber) => ...}` to get the numeric value
- Affected fields: `quantity`, `leverage`, `price`, `take_profit`, `stop_loss`
- `leverage` select: store the selected integer (e.g. `10`), not the display string (`"10×"`)

---

## LIMIT price validation

When `order_type` is fixed to "LIMIT", show an inline `<FormHelperText color="red.400">` on the price row if price source is "signal" and the signal field name is empty, or if price source is "fixed" and the value is empty. Block form submission with a toast if price is unconfigured when order_type=LIMIT.

---

## TradingView JSON generation (detailed)

Only "From signal" fields appear in the TradingView JSON. The key is the signal field name entered by the user, not the `mapping_template` key.

Example: parameter `quantity` (mapping key), user enters signal field `qty`:
- `mapping_template` output: `"quantity": "$.qty"`
- TradingView output: `"qty": "{{qty}}"`

The TradingView JSON is shown read-only in `TradingViewPreview` with syntax-coloring.

---

## UI Layout

```
<Grid templateColumns={{ base: "1fr", lg: "1fr 320px" }} gap={6}>
  <GridItem>  {/* Parameter form */}
    <Tabs colorScheme="blue">
      <TabList>
        <Tab>Futures</Tab>
        <Tab>Spot</Tab>
      </TabList>
      <TabPanels>
        <TabPanel><VStack>{/* futures rows */}</VStack></TabPanel>
        <TabPanel><VStack>{/* spot rows */}</VStack></TabPanel>
      </TabPanels>
    </Tabs>
  </GridItem>
  <GridItem>  {/* Sticky preview */}
    <TradingViewPreview ... />
  </GridItem>
</Grid>
```

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `components/strategies/WebhookParameterBuilder.tsx` | Create |
| `components/strategies/ParameterRow.tsx` | Create |
| `components/strategies/TradingViewPreview.tsx` | Create |
| `app/(dashboard)/strategies/new/page.tsx` | Modify |

---

## Out of Scope

- Editing existing strategies (new/page.tsx only)
- Supporting non-Exchange1 brokers
- Drag-and-drop field mapping
- Backend changes to `mapping_template` schema
