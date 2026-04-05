# Webhook Parameter Builder — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the raw JSON `mapping_template` textarea in the webhook strategy creation form with a guided parameter builder UI that auto-generates both the backend `mapping_template` and a TradingView alert JSON.

**Architecture:** Three new components (`ParameterRow`, `TradingViewPreview`, `WebhookParameterBuilder`) under `components/strategies/`. `WebhookParameterBuilder` holds all row state internally and calls `onChange` with a computed `mapping_template` object on every change. No backend changes — the output format is identical to what the existing form produced.

**Tech Stack:** Next.js 14, Chakra UI v2, TypeScript, `@testing-library/react` + Jest (jsdom), Chakra `ChakraProvider` wrapper in tests.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/components/strategies/ParameterRow.tsx` | Create | Single row: label + Fixed/Signal toggle + value input |
| `frontend/components/strategies/TradingViewPreview.tsx` | Create | Right panel: webhook URL + TradingView JSON preview + how-to |
| `frontend/components/strategies/WebhookParameterBuilder.tsx` | Create | Orchestrator: holds row state, computes mapping_template, renders layout |
| `frontend/__tests__/components/ParameterRow.test.tsx` | Create | Toggle behavior, value input rendering, signal field input |
| `frontend/__tests__/components/TradingViewPreview.test.tsx` | Create | JSON generation from mapping_template |
| `frontend/__tests__/components/WebhookParameterBuilder.test.tsx` | Create | onChange called with correct mapping_template; tab switching |
| `frontend/app/(dashboard)/strategies/new/page.tsx` | Modify | Swap Textarea for WebhookParameterBuilder, update form state |

---

## Task 1: `ParameterRow` component

**Files:**
- Create: `frontend/components/strategies/ParameterRow.tsx`
- Create: `frontend/__tests__/components/ParameterRow.test.tsx`

- [ ] **Step 1.1 — Write the failing test**

Create `frontend/__tests__/components/ParameterRow.test.tsx`:

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { ParameterRow } from "@/components/strategies/ParameterRow";

const wrap = (ui: React.ReactElement) =>
  render(<ChakraProvider>{ui}</ChakraProvider>);

const baseProps = {
  label: "Action",
  fieldKey: "action",
  required: true,
  source: "signal" as const,
  fixedValue: "BUY",
  signalField: "action",
  inputType: "select" as const,
  selectOptions: [
    { value: "BUY", label: "BUY" },
    { value: "SELL", label: "SELL" },
  ],
  onSourceChange: jest.fn(),
  onFixedChange: jest.fn(),
  onSignalFieldChange: jest.fn(),
};

describe("ParameterRow", () => {
  beforeEach(() => jest.clearAllMocks());

  it("renders the label", () => {
    wrap(<ParameterRow {...baseProps} />);
    expect(screen.getByText("Action")).toBeInTheDocument();
  });

  it("renders signal input when source is signal", () => {
    wrap(<ParameterRow {...baseProps} source="signal" />);
    expect(screen.getByTestId("action-signal-input")).toBeInTheDocument();
    expect(screen.queryByTestId("action-select")).not.toBeInTheDocument();
  });

  it("renders select when source is fixed and inputType is select", () => {
    wrap(<ParameterRow {...baseProps} source="fixed" />);
    expect(screen.getByTestId("action-select")).toBeInTheDocument();
    expect(screen.queryByTestId("action-signal-input")).not.toBeInTheDocument();
  });

  it("calls onSourceChange with 'fixed' when Fixed button clicked", () => {
    wrap(<ParameterRow {...baseProps} source="signal" />);
    fireEvent.click(screen.getByTestId("action-fixed-btn"));
    expect(baseProps.onSourceChange).toHaveBeenCalledWith("fixed");
  });

  it("calls onSourceChange with 'signal' when From signal button clicked", () => {
    wrap(<ParameterRow {...baseProps} source="fixed" />);
    fireEvent.click(screen.getByTestId("action-signal-btn"));
    expect(baseProps.onSourceChange).toHaveBeenCalledWith("signal");
  });

  it("calls onSignalFieldChange when signal input changes", () => {
    wrap(<ParameterRow {...baseProps} source="signal" signalField="" />);
    fireEvent.change(screen.getByTestId("action-signal-input"), {
      target: { value: "direction" },
    });
    expect(baseProps.onSignalFieldChange).toHaveBeenCalledWith("direction");
  });

  it("shows price error helper text when showPriceError is true and source is signal", () => {
    wrap(
      <ParameterRow
        {...baseProps}
        fieldKey="price"
        label="Price"
        source="signal"
        signalField=""
        inputType="number"
        showPriceError
      />
    );
    expect(
      screen.getByText(/required when order type is limit/i)
    ).toBeInTheDocument();
  });

  it("renders NumberInput when inputType is number and source is fixed", () => {
    wrap(
      <ParameterRow
        {...baseProps}
        fieldKey="quantity"
        label="Quantity"
        source="fixed"
        fixedValue={5}
        inputType="number"
      />
    );
    expect(screen.getByTestId("quantity-number-input")).toBeInTheDocument();
  });

  it("renders custom fixed input when provided and source is fixed", () => {
    wrap(
      <ParameterRow
        {...baseProps}
        source="fixed"
        customFixedInput={<div data-testid="custom-input">Custom</div>}
      />
    );
    expect(screen.getByTestId("custom-input")).toBeInTheDocument();
  });
});
```

- [ ] **Step 1.2 — Run test to confirm it fails**

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/frontend
npm test -- --testPathPattern=ParameterRow --no-coverage 2>&1 | tail -10
```

Expected: FAIL — `Cannot find module '@/components/strategies/ParameterRow'`

- [ ] **Step 1.3 — Create `ParameterRow.tsx`**

Create `frontend/components/strategies/ParameterRow.tsx`:

```tsx
"use client";
import {
  Box,
  Button,
  ButtonGroup,
  FormHelperText,
  Grid,
  Input,
  NumberInput,
  NumberInputField,
  Select,
  Text,
  useColorModeValue,
} from "@chakra-ui/react";

export interface ParameterRowProps {
  label: string;
  fieldKey: string;
  required?: boolean;
  source: "fixed" | "signal";
  fixedValue: string | number | null;
  signalField: string;
  inputType: "text" | "number" | "select";
  selectOptions?: { value: string; label: string }[];
  showPriceError?: boolean;
  onSourceChange: (source: "fixed" | "signal") => void;
  onFixedChange: (value: string | number) => void;
  onSignalFieldChange: (fieldName: string) => void;
  customFixedInput?: React.ReactNode;
}

export function ParameterRow({
  label,
  fieldKey,
  required,
  source,
  fixedValue,
  signalField,
  inputType,
  selectOptions,
  showPriceError,
  onSourceChange,
  onFixedChange,
  onSignalFieldChange,
  customFixedInput,
}: ParameterRowProps) {
  const labelColor = useColorModeValue("gray.700", "gray.300");
  const reqColor = useColorModeValue("red.500", "red.400");

  return (
    <Grid
      templateColumns={{ base: "1fr", md: "160px 200px 1fr" }}
      gap={3}
      alignItems="center"
      data-testid={`param-row-${fieldKey}`}
    >
      {/* Label */}
      <Text fontSize="sm" color={labelColor} fontWeight="medium">
        {label}
        {required && (
          <Text as="span" color={reqColor} ml={1} fontSize="xs">
            *
          </Text>
        )}
      </Text>

      {/* Source toggle */}
      <ButtonGroup size="sm" isAttached variant="outline">
        <Button
          colorScheme={source === "fixed" ? "green" : "gray"}
          variant={source === "fixed" ? "solid" : "outline"}
          onClick={() => onSourceChange("fixed")}
          data-testid={`${fieldKey}-fixed-btn`}
        >
          Fixed
        </Button>
        <Button
          colorScheme={source === "signal" ? "orange" : "gray"}
          variant={source === "signal" ? "solid" : "outline"}
          onClick={() => onSourceChange("signal")}
          data-testid={`${fieldKey}-signal-btn`}
        >
          From signal
        </Button>
      </ButtonGroup>

      {/* Value input */}
      <Box>
        {source === "fixed" ? (
          customFixedInput ? (
            customFixedInput
          ) : inputType === "select" && selectOptions ? (
            <Select
              size="sm"
              value={String(fixedValue ?? "")}
              onChange={(e) => onFixedChange(e.target.value)}
              data-testid={`${fieldKey}-select`}
            >
              {selectOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </Select>
          ) : inputType === "number" ? (
            <NumberInput
              size="sm"
              value={fixedValue as number ?? 0}
              onChange={(_, valAsNumber) =>
                onFixedChange(isNaN(valAsNumber) ? 0 : valAsNumber)
              }
              min={0}
            >
              <NumberInputField data-testid={`${fieldKey}-number-input`} />
            </NumberInput>
          ) : (
            <Input
              size="sm"
              value={String(fixedValue ?? "")}
              onChange={(e) => onFixedChange(e.target.value)}
              data-testid={`${fieldKey}-text-input`}
            />
          )
        ) : (
          <Box>
            <Input
              size="sm"
              placeholder="field name in signal"
              value={signalField}
              onChange={(e) => onSignalFieldChange(e.target.value)}
              data-testid={`${fieldKey}-signal-input`}
            />
            {showPriceError && (
              <FormHelperText color="red.400" fontSize="xs">
                Required when order type is LIMIT
              </FormHelperText>
            )}
          </Box>
        )}
        {source === "fixed" && showPriceError && (
          <FormHelperText color="red.400" fontSize="xs">
            Required when order type is LIMIT
          </FormHelperText>
        )}
      </Box>
    </Grid>
  );
}
```

- [ ] **Step 1.4 — Run tests to confirm pass**

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/frontend
npm test -- --testPathPattern=ParameterRow --no-coverage 2>&1 | tail -15
```

Expected: All 9 tests PASS.

- [ ] **Step 1.5 — Commit**

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter
git add frontend/components/strategies/ParameterRow.tsx \
        frontend/__tests__/components/ParameterRow.test.tsx
git commit -m "feat: add ParameterRow component for webhook parameter builder"
```

---

## Task 2: `TradingViewPreview` component

**Files:**
- Create: `frontend/components/strategies/TradingViewPreview.tsx`
- Create: `frontend/__tests__/components/TradingViewPreview.test.tsx`

- [ ] **Step 2.1 — Write the failing test**

Create `frontend/__tests__/components/TradingViewPreview.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { TradingViewPreview } from "@/components/strategies/TradingViewPreview";

const wrap = (ui: React.ReactElement) =>
  render(<ChakraProvider>{ui}</ChakraProvider>);

describe("TradingViewPreview", () => {
  it("shows only signal fields in the TradingView JSON", () => {
    const mapping = {
      exchange: "EXCHANGE1",
      product_type: "FUTURES",
      symbol: "BTCUSDT",          // fixed — plain string
      action: "$.action",          // signal — JSONPath
      quantity: "$.qty",           // signal — JSONPath
      leverage: 10,                // fixed — number
    };
    wrap(<TradingViewPreview mappingTemplate={mapping} />);
    const preview = screen.getByTestId("tv-json-preview");
    const json = JSON.parse(preview.textContent!);
    // Only signal fields ($.xxx) should appear
    expect(json).toEqual({
      action: "{{action}}",
      qty: "{{qty}}",
    });
    // Fixed fields must NOT appear
    expect(json).not.toHaveProperty("symbol");
    expect(json).not.toHaveProperty("leverage");
    expect(json).not.toHaveProperty("exchange");
  });

  it("uses the signal field name (after $.) as both key and template placeholder", () => {
    const mapping = { quantity: "$.qty" };
    wrap(<TradingViewPreview mappingTemplate={mapping} />);
    const json = JSON.parse(screen.getByTestId("tv-json-preview").textContent!);
    // key = "qty" (after $.), value = "{{qty}}"
    expect(json.qty).toBe("{{qty}}");
    expect(json).not.toHaveProperty("quantity");
  });

  it("shows webhook URL and Copy button when webhookUrl is provided", () => {
    wrap(
      <TradingViewPreview
        mappingTemplate={{}}
        webhookUrl="https://algomatter.in/api/v1/webhook/abc123"
      />
    );
    expect(
      screen.getByText("https://algomatter.in/api/v1/webhook/abc123")
    ).toBeInTheDocument();
    // Two copy buttons: one for URL, one for JSON
    expect(screen.getAllByRole("button", { name: /copy/i })).toHaveLength(2);
  });

  it("hides webhook URL section when webhookUrl is not provided", () => {
    wrap(<TradingViewPreview mappingTemplate={{}} />);
    expect(screen.queryByText(/webhook url/i)).not.toBeInTheDocument();
    // Only one copy button (for JSON)
    expect(screen.getAllByRole("button", { name: /copy/i })).toHaveLength(1);
  });

  it("shows empty JSON object when all fields are fixed", () => {
    const mapping = { symbol: "BTCUSDT", leverage: 10, exchange: "EXCHANGE1" };
    wrap(<TradingViewPreview mappingTemplate={mapping} />);
    const json = JSON.parse(screen.getByTestId("tv-json-preview").textContent!);
    expect(json).toEqual({});
  });

  it("shows how-to instructions", () => {
    wrap(<TradingViewPreview mappingTemplate={{}} />);
    // "How to use in TradingView" heading is always rendered (not conditional on webhookUrl)
    expect(screen.getByText(/how to use in tradingview/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2.2 — Run test to confirm it fails**

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/frontend
npm test -- --testPathPattern=TradingViewPreview --no-coverage 2>&1 | tail -10
```

Expected: FAIL — `Cannot find module '@/components/strategies/TradingViewPreview'`

- [ ] **Step 2.3 — Create `TradingViewPreview.tsx`**

Create `frontend/components/strategies/TradingViewPreview.tsx`:

```tsx
"use client";
import {
  Box,
  Button,
  Code,
  Heading,
  HStack,
  Text,
  useClipboard,
  useColorModeValue,
  VStack,
} from "@chakra-ui/react";

interface Props {
  mappingTemplate: Record<string, unknown>;
  webhookUrl?: string;
}

function buildTradingViewJson(
  mappingTemplate: Record<string, unknown>
): Record<string, string> {
  const tv: Record<string, string> = {};
  for (const value of Object.values(mappingTemplate)) {
    if (typeof value === "string" && value.startsWith("$.")) {
      const fieldName = value.slice(2); // strip "$."
      tv[fieldName] = `{{${fieldName}}}`;
    }
  }
  return tv;
}

export function TradingViewPreview({ mappingTemplate, webhookUrl }: Props) {
  const tvJson = buildTradingViewJson(mappingTemplate);
  const tvJsonStr = JSON.stringify(tvJson, null, 2);
  const { hasCopied: copiedJson, onCopy: onCopyJson } = useClipboard(tvJsonStr);
  const { hasCopied: copiedUrl, onCopy: onCopyUrl } = useClipboard(
    webhookUrl ?? ""
  );
  const borderColor = useColorModeValue("gray.200", "gray.700");
  const preBg = useColorModeValue("gray.50", "gray.900");
  const preColor = useColorModeValue("gray.800", "gray.100");

  return (
    <VStack spacing={4} align="stretch">
      {/* Webhook URL */}
      {webhookUrl && (
        <Box borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
          <Text
            fontSize="xs"
            fontWeight="semibold"
            color="gray.500"
            mb={2}
            textTransform="uppercase"
          >
            Webhook URL
          </Text>
          <HStack>
            <Text fontSize="xs" fontFamily="mono" flex={1} noOfLines={1} wordBreak="break-all">
              {webhookUrl}
            </Text>
            <Button
              size="xs"
              onClick={onCopyUrl}
              colorScheme={copiedUrl ? "green" : "gray"}
            >
              {copiedUrl ? "Copied!" : "Copy"}
            </Button>
          </HStack>
        </Box>
      )}

      {/* TradingView JSON preview */}
      <Box borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
        <HStack justify="space-between" mb={3}>
          <Heading
            size="xs"
            color="gray.500"
            textTransform="uppercase"
          >
            TradingView Alert Message
          </Heading>
          <Button
            size="xs"
            onClick={onCopyJson}
            colorScheme={copiedJson ? "green" : "blue"}
          >
            {copiedJson ? "Copied!" : "Copy JSON"}
          </Button>
        </HStack>
        <Box
          as="pre"
          fontSize="xs"
          fontFamily="mono"
          whiteSpace="pre-wrap"
          bg={preBg}
          color={preColor}
          p={3}
          borderRadius="sm"
          data-testid="tv-json-preview"
        >
          {tvJsonStr}
        </Box>
        <Text
          fontSize="xs"
          color="gray.500"
          mt={3}
          borderTopWidth={1}
          borderColor={borderColor}
          pt={2}
        >
          Paste this as your TradingView alert "Message" — copy once, works forever.
        </Text>
      </Box>

      {/* How to use */}
      <Box borderWidth={1} borderColor={borderColor} borderRadius="md" p={4}>
        <Heading
          size="xs"
          mb={3}
          color="gray.500"
          textTransform="uppercase"
        >
          How to use in TradingView
        </Heading>
        <VStack
          align="start"
          spacing={2}
          fontSize="sm"
          color={useColorModeValue("gray.700", "gray.300")}
        >
          <Text>1. In your Pine Script strategy, add an alert</Text>
          <Text>
            2. Set <Code fontSize="xs">Webhook URL</Code> to the URL above
          </Text>
          <Text>
            3. Set <Code fontSize="xs">Message</Code> to the JSON above
          </Text>
          <Text>4. Every alert fires a trade automatically</Text>
        </VStack>
      </Box>
    </VStack>
  );
}
```

- [ ] **Step 2.4 — Run tests to confirm pass**

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/frontend
npm test -- --testPathPattern=TradingViewPreview --no-coverage 2>&1 | tail -15
```

Expected: All 6 tests PASS.

- [ ] **Step 2.5 — Commit**

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter
git add frontend/components/strategies/TradingViewPreview.tsx \
        frontend/__tests__/components/TradingViewPreview.test.tsx
git commit -m "feat: add TradingViewPreview component for webhook builder"
```

---

## Task 3: `WebhookParameterBuilder` component

**Files:**
- Create: `frontend/components/strategies/WebhookParameterBuilder.tsx`
- Create: `frontend/__tests__/components/WebhookParameterBuilder.test.tsx`

- [ ] **Step 3.1 — Write the failing test**

Create `frontend/__tests__/components/WebhookParameterBuilder.test.tsx`:

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { WebhookParameterBuilder } from "@/components/strategies/WebhookParameterBuilder";

// Mock SymbolSelect — not testing the instrument dropdown here
jest.mock("@/components/shared/SymbolSelect", () => ({
  SymbolSelect: ({ value, onChange }: { value: string; onChange: (s: string) => void }) => (
    <input
      data-testid="symbol-select"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  ),
}));

// Mock useWebhookConfig (not used inside builder directly, but TradingViewPreview is rendered)
const wrap = (ui: React.ReactElement) =>
  render(<ChakraProvider>{ui}</ChakraProvider>);

describe("WebhookParameterBuilder", () => {
  it("calls onChange on mount with a valid futures mapping_template", async () => {
    const onChange = jest.fn();
    wrap(<WebhookParameterBuilder value={null} onChange={onChange} />);
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    // Hidden fixed fields always present
    expect(lastCall.exchange).toBe("EXCHANGE1");
    expect(lastCall.product_type).toBe("FUTURES");
    // Default: action is "From signal"
    expect(lastCall.action).toBe("$.action");
    // Default: symbol is Fixed = "BTCUSDT"
    expect(lastCall.symbol).toBe("BTCUSDT");
    // Default: leverage is Fixed = 10 (number)
    expect(lastCall.leverage).toBe(10);
  });

  it("emits DELIVERY product_type when Spot tab is selected", async () => {
    const onChange = jest.fn();
    wrap(<WebhookParameterBuilder value={null} onChange={onChange} />);
    fireEvent.click(screen.getByRole("tab", { name: "Spot" }));
    await waitFor(() => {
      const calls = onChange.mock.calls;
      const lastCall = calls[calls.length - 1][0];
      expect(lastCall.product_type).toBe("DELIVERY");
    });
  });

  it("emits fixed value (not JSONPath) when source is Fixed", async () => {
    const onChange = jest.fn();
    wrap(<WebhookParameterBuilder value={null} onChange={onChange} />);
    // Order type defaults to Fixed=MARKET — verify no JSONPath
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(lastCall.order_type).toBe("MARKET");
    expect(String(lastCall.order_type).startsWith("$.")).toBe(false);
  });

  it("emits JSONPath when source is toggled to From signal", async () => {
    const onChange = jest.fn();
    wrap(<WebhookParameterBuilder value={null} onChange={onChange} />);
    // Toggle order_type to "From signal"
    fireEvent.click(screen.getByTestId("order_type-signal-btn"));
    await waitFor(() => {
      const calls = onChange.mock.calls;
      const lastCall = calls[calls.length - 1][0];
      expect(lastCall.order_type).toBe("$.order_type");
    });
  });

  it("does not include optional fields when show optional is collapsed", async () => {
    const onChange = jest.fn();
    wrap(<WebhookParameterBuilder value={null} onChange={onChange} />);
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(lastCall).not.toHaveProperty("price");
    expect(lastCall).not.toHaveProperty("take_profit");
    expect(lastCall).not.toHaveProperty("stop_loss");
  });

  it("includes optional fields after expanding optional section", async () => {
    const onChange = jest.fn();
    wrap(<WebhookParameterBuilder value={null} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: /show optional/i }));
    // After expanding, fill in the price signal field
    fireEvent.change(screen.getByTestId("price-signal-input"), {
      target: { value: "close" },
    });
    await waitFor(() => {
      const calls = onChange.mock.calls;
      const lastCall = calls[calls.length - 1][0];
      expect(lastCall.price).toBe("$.close");
    });
  });

  it("emits leverage as a JS number, not a string", async () => {
    const onChange = jest.fn();
    wrap(<WebhookParameterBuilder value={null} onChange={onChange} />);
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(typeof lastCall.leverage).toBe("number");
  });
});
```

- [ ] **Step 3.2 — Run test to confirm it fails**

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/frontend
npm test -- --testPathPattern=WebhookParameterBuilder --no-coverage 2>&1 | tail -10
```

Expected: FAIL — `Cannot find module '@/components/strategies/WebhookParameterBuilder'`

- [ ] **Step 3.3 — Create `WebhookParameterBuilder.tsx`**

Create `frontend/components/strategies/WebhookParameterBuilder.tsx`:

```tsx
"use client";
import { useEffect, useState } from "react";
import {
  Box,
  Button,
  Divider,
  Grid,
  GridItem,
  Tab,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
  VStack,
} from "@chakra-ui/react";
import { ParameterRow } from "./ParameterRow";
import { TradingViewPreview } from "./TradingViewPreview";
import { SymbolSelect } from "@/components/shared/SymbolSelect";

type Source = "fixed" | "signal";

interface RowState {
  source: Source;
  fixedValue: string | number | null;
  signalField: string;
}

type BuilderRows = Record<string, RowState>;

interface Props {
  value: Record<string, unknown> | null;
  onChange: (value: Record<string, unknown>) => void;
  webhookUrl?: string;
}

// Numeric fields: stored as strings in select/input state,
// coerced to JS number in computeMapping output
const NUMERIC_KEYS = new Set(["leverage", "quantity", "price", "take_profit", "stop_loss"]);

const DEFAULT_FUTURES_ROWS: BuilderRows = {
  symbol:         { source: "fixed",  fixedValue: "BTCUSDT",  signalField: "symbol" },
  action:         { source: "signal", fixedValue: "BUY",      signalField: "action" },
  order_type:     { source: "fixed",  fixedValue: "MARKET",   signalField: "order_type" },
  quantity:       { source: "signal", fixedValue: 1,          signalField: "qty" },
  leverage:       { source: "fixed",  fixedValue: "10",       signalField: "leverage" },
  position_model: { source: "fixed",  fixedValue: "isolated", signalField: "position_model" },
};

const DEFAULT_SPOT_ROWS: BuilderRows = {
  symbol:     { source: "fixed",  fixedValue: "BTCUSDT",  signalField: "symbol" },
  action:     { source: "signal", fixedValue: "BUY",      signalField: "action" },
  order_type: { source: "fixed",  fixedValue: "MARKET",   signalField: "order_type" },
  quantity:   { source: "signal", fixedValue: 1,          signalField: "qty" },
};

const EMPTY_ROW: RowState = { source: "signal", fixedValue: null, signalField: "" };

const DEFAULT_FUTURES_OPTIONAL: BuilderRows = {
  price:        { ...EMPTY_ROW },
  take_profit:  { ...EMPTY_ROW },
  stop_loss:    { ...EMPTY_ROW },
};

const DEFAULT_SPOT_OPTIONAL: BuilderRows = {
  price: { ...EMPTY_ROW },
};

function computeMapping(
  mode: "futures" | "spot",
  rows: BuilderRows,
  optionalRows: BuilderRows
): Record<string, unknown> {
  const template: Record<string, unknown> = {
    exchange: "EXCHANGE1",
    product_type: mode === "futures" ? "FUTURES" : "DELIVERY",
  };
  const allRows = { ...rows, ...optionalRows };
  for (const [key, row] of Object.entries(allRows)) {
    if (row.source === "signal") {
      if (!row.signalField) continue; // skip empty optional signal fields
      template[key] = `$.${row.signalField}`;
    } else {
      const raw = row.fixedValue;
      if (NUMERIC_KEYS.has(key) && raw !== null && raw !== "") {
        const n = Number(raw);
        template[key] = isNaN(n) ? raw : n;
      } else {
        template[key] = raw;
      }
    }
  }
  return template;
}

export function WebhookParameterBuilder({ onChange, webhookUrl }: Props) {
  const [mode, setMode] = useState<"futures" | "spot">("futures");
  const [futuresRows, setFuturesRows] = useState<BuilderRows>(DEFAULT_FUTURES_ROWS);
  const [spotRows, setSpotRows] = useState<BuilderRows>(DEFAULT_SPOT_ROWS);
  const [futuresOptional, setFuturesOptional] = useState<BuilderRows>(
    DEFAULT_FUTURES_OPTIONAL
  );
  const [spotOptional, setSpotOptional] = useState<BuilderRows>(DEFAULT_SPOT_OPTIONAL);
  const [showOptional, setShowOptional] = useState(false);

  const rows = mode === "futures" ? futuresRows : spotRows;
  const setRows = mode === "futures" ? setFuturesRows : setSpotRows;
  const optionalRows = mode === "futures" ? futuresOptional : spotOptional;
  const setOptionalRows =
    mode === "futures" ? setFuturesOptional : setSpotOptional;
  const optionalKeys =
    mode === "futures"
      ? (["price", "take_profit", "stop_loss"] as const)
      : (["price"] as const);

  useEffect(() => {
    onChange(
      computeMapping(mode, rows, showOptional ? optionalRows : {})
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, futuresRows, spotRows, futuresOptional, spotOptional, showOptional]);

  function updateRow(
    key: string,
    update: Partial<RowState>,
    isOptional = false
  ) {
    if (isOptional) {
      setOptionalRows((prev) => ({
        ...prev,
        [key]: { ...prev[key], ...update },
      }));
    } else {
      setRows((prev) => ({
        ...prev,
        [key]: { ...prev[key], ...update },
      }));
    }
  }

  const isLimitFixed =
    rows.order_type?.source === "fixed" &&
    rows.order_type?.fixedValue === "LIMIT";

  const currentMapping = computeMapping(
    mode,
    rows,
    showOptional ? optionalRows : {}
  );

  function renderRow(key: string, rowState: RowState, isOptional = false) {
    const handlers = {
      onSourceChange: (s: Source) => updateRow(key, { source: s }, isOptional),
      onFixedChange: (v: string | number) =>
        updateRow(key, { fixedValue: v }, isOptional),
      onSignalFieldChange: (f: string) =>
        updateRow(key, { signalField: f }, isOptional),
    };

    const commonProps = {
      fieldKey: key,
      source: rowState.source,
      fixedValue: rowState.fixedValue,
      signalField: rowState.signalField,
      ...handlers,
    };

    switch (key) {
      case "symbol":
        return (
          <ParameterRow
            key={key}
            label="Symbol"
            required
            inputType="text"
            {...commonProps}
            customFixedInput={
              rowState.source === "fixed" ? (
                <SymbolSelect
                  exchange="EXCHANGE1"
                  value={String(rowState.fixedValue ?? "")}
                  onChange={(s) =>
                    updateRow(key, { fixedValue: s }, isOptional)
                  }
                  placeholder="Search symbol…"
                />
              ) : undefined
            }
          />
        );
      case "action":
        return (
          <ParameterRow
            key={key}
            label="Action"
            required
            inputType="select"
            selectOptions={[
              { value: "BUY", label: "BUY" },
              { value: "SELL", label: "SELL" },
            ]}
            {...commonProps}
          />
        );
      case "order_type":
        return (
          <ParameterRow
            key={key}
            label="Order Type"
            required
            inputType="select"
            selectOptions={[
              { value: "MARKET", label: "MARKET" },
              { value: "LIMIT", label: "LIMIT" },
            ]}
            {...commonProps}
          />
        );
      case "quantity":
        return (
          <ParameterRow
            key={key}
            label="Quantity"
            required
            inputType="number"
            {...commonProps}
          />
        );
      case "leverage":
        return (
          <ParameterRow
            key={key}
            label="Leverage"
            required
            inputType="select"
            selectOptions={[1, 2, 3, 5, 10, 15, 20, 25, 50, 100].map((n) => ({
              value: String(n),
              label: `${n}×`,
            }))}
            {...commonProps}
          />
        );
      case "position_model":
        return (
          <ParameterRow
            key={key}
            label="Margin Mode"
            inputType="select"
            selectOptions={[
              { value: "isolated", label: "Isolated" },
              { value: "cross", label: "Cross" },
            ]}
            {...commonProps}
          />
        );
      case "price":
        return (
          <ParameterRow
            key={key}
            label="Price"
            inputType="number"
            showPriceError={
              isLimitFixed &&
              !rowState.signalField &&
              !rowState.fixedValue
            }
            {...commonProps}
          />
        );
      case "take_profit":
        return (
          <ParameterRow
            key={key}
            label="Take Profit"
            inputType="number"
            {...commonProps}
          />
        );
      case "stop_loss":
        return (
          <ParameterRow
            key={key}
            label="Stop Loss"
            inputType="number"
            {...commonProps}
          />
        );
      default:
        return null;
    }
  }

  return (
    <Grid
      templateColumns={{ base: "1fr", lg: "1fr 320px" }}
      gap={6}
      alignItems="start"
    >
      {/* Left: form */}
      <GridItem>
        <Tabs
          colorScheme="blue"
          onChange={(i) => setMode(i === 0 ? "futures" : "spot")}
        >
          <TabList>
            <Tab>Futures</Tab>
            <Tab>Spot</Tab>
          </TabList>
          <TabPanels>
            {/* Futures */}
            <TabPanel px={0} pt={4}>
              <VStack spacing={3} align="stretch">
                {Object.keys(DEFAULT_FUTURES_ROWS).map((key) =>
                  renderRow(key, futuresRows[key])
                )}
                <Divider />
                <Button
                  size="xs"
                  variant="link"
                  colorScheme="blue"
                  alignSelf="flex-start"
                  onClick={() => setShowOptional((v) => !v)}
                >
                  {showOptional ? "▾ Hide" : "▸ Show"} optional parameters (TP
                  / SL / Price)
                </Button>
                {showOptional &&
                  optionalKeys.map((key) =>
                    renderRow(key, futuresOptional[key], true)
                  )}
              </VStack>
            </TabPanel>
            {/* Spot */}
            <TabPanel px={0} pt={4}>
              <VStack spacing={3} align="stretch">
                {Object.keys(DEFAULT_SPOT_ROWS).map((key) =>
                  renderRow(key, spotRows[key])
                )}
                <Divider />
                <Button
                  size="xs"
                  variant="link"
                  colorScheme="blue"
                  alignSelf="flex-start"
                  onClick={() => setShowOptional((v) => !v)}
                >
                  {showOptional ? "▾ Hide" : "▸ Show"} optional parameter
                  (Price)
                </Button>
                {showOptional &&
                  (["price"] as const).map((key) =>
                    renderRow(key, spotOptional[key], true)
                  )}
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>
      </GridItem>

      {/* Right: sticky preview */}
      <GridItem>
        <Box position="sticky" top={4}>
          <TradingViewPreview
            mappingTemplate={currentMapping}
            webhookUrl={webhookUrl}
          />
        </Box>
      </GridItem>
    </Grid>
  );
}
```

- [ ] **Step 3.4 — Run tests to confirm pass**

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/frontend
npm test -- --testPathPattern=WebhookParameterBuilder --no-coverage 2>&1 | tail -20
```

Expected: All 7 tests PASS.

- [ ] **Step 3.5 — Run all component tests to confirm no regressions**

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/frontend
npm test -- --no-coverage 2>&1 | tail -20
```

Expected: All suites pass.

- [ ] **Step 3.6 — Commit**

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter
git add frontend/components/strategies/WebhookParameterBuilder.tsx \
        frontend/__tests__/components/WebhookParameterBuilder.test.tsx
git commit -m "feat: add WebhookParameterBuilder orchestrator component"
```

---

## Task 4: Integrate into `new/page.tsx`

**Files:**
- Modify: `frontend/app/(dashboard)/strategies/new/page.tsx`

> No new test file — the page-level integration test would require mocking SWR, routing, and API calls. The existing `WebhookParameterBuilder` tests cover the core logic. Manually verify in the browser after deploy.

- [ ] **Step 4.1 — Update `StrategyForm` interface**

In `frontend/app/(dashboard)/strategies/new/page.tsx`, replace:
```ts
interface StrategyForm {
  name: string;
  broker_connection_id: string;
  mode: string;
  is_active: boolean;
  mapping_template: string;
  symbol_whitelist: string;
  symbol_blacklist: string;
  max_positions: number;
  max_signals_per_day: number;
}
```

With:
```ts
interface StrategyForm {
  name: string;
  broker_connection_id: string;
  mode: string;
  is_active: boolean;
  mapping_template_obj: Record<string, unknown> | null;
  symbol_whitelist: string;
  symbol_blacklist: string;
  max_positions: number;
  max_signals_per_day: number;
}
```

- [ ] **Step 4.2 — Update imports and initial state**

Update the Chakra import block — remove `Textarea` (no longer used), and add `Box`, `Text` if not already present:
```tsx
// Remove Textarea from the import:
import {
  Box, Heading, FormControl, FormLabel, Input, Select, Radio, RadioGroup,
  Stack, Switch, Button, VStack, useToast, NumberInput,
  NumberInputField, Divider, Text, Flex,
} from "@chakra-ui/react";
```

Add new imports:
```tsx
import { WebhookParameterBuilder } from "@/components/strategies/WebhookParameterBuilder";
import { useWebhookConfig } from "@/lib/hooks/useApi";
```

Update the `useState` initial value:
```ts
// Change:
mapping_template: "",
// To:
mapping_template_obj: null,
```

Add below the existing `useBrokers()` call:
```ts
const { data: webhookConfig } = useWebhookConfig();
```

- [ ] **Step 4.3 — Update `handleSubmit`**

Replace:
```ts
mapping_template: form.mapping_template ? JSON.parse(form.mapping_template) : null,
```

With:
```ts
mapping_template: form.mapping_template_obj ?? undefined,
```

Also add a LIMIT price guard at the top of `handleSubmit`, before `setSubmitting(true)`:
```ts
// Guard: if order_type is fixed LIMIT, price must be configured
const mt = form.mapping_template_obj ?? {};
if (mt.order_type === "LIMIT" && !mt.price) {
  toast({
    title: "Price required",
    description: "Set a price value or signal field when order type is LIMIT.",
    status: "error",
    duration: 4000,
  });
  return;
}
```

- [ ] **Step 4.4 — Replace the Textarea with `WebhookParameterBuilder`**

Remove:
```tsx
<FormControl>
  <FormLabel>Mapping Template (JSON)</FormLabel>
  <Textarea
    value={form.mapping_template}
    onChange={(e) => setForm({ ...form, mapping_template: e.target.value })}
    placeholder='{"symbol": "$.ticker", "action": "$.side"}'
    rows={4}
  />
</FormControl>
```

Add:
```tsx
<Box>
  <Text fontWeight="medium" mb={3}>Signal Mapping</Text>
  <WebhookParameterBuilder
    value={form.mapping_template_obj}
    onChange={(val) => setForm({ ...form, mapping_template_obj: val })}
    webhookUrl={webhookConfig?.webhook_url}
  />
</Box>
```

- [ ] **Step 4.5 — Widen the page container**

Change:
```tsx
<Box maxW="600px">
```

To:
```tsx
<Box maxW="900px">
```

- [ ] **Step 4.6 — TypeScript build check**

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/frontend
npx tsc --noEmit 2>&1 | grep -E "error|warning" | head -20
```

Expected: No errors. Fix any TypeScript errors before continuing.

- [ ] **Step 4.7 — Run full test suite**

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter/frontend
npm test -- --no-coverage 2>&1 | tail -20
```

Expected: All suites pass.

- [ ] **Step 4.8 — Commit**

```bash
cd /Users/abhishekbhar/projects/algomatter-worktree/algomatter
git add frontend/app/\(dashboard\)/strategies/new/page.tsx
git commit -m "feat: integrate WebhookParameterBuilder into new strategy form"
```

- [ ] **Step 4.9 — Deploy and verify**

```bash
# Run /deploy frontend
```

Navigate to `https://algomatter.in/app/strategies/new` and verify:
- Futures/Spot tabs visible
- Each row shows Fixed / From signal toggle
- Right panel shows TradingView JSON updating as you change toggles
- Copy JSON button works
- Webhook URL is visible

---

## Done

All 4 tasks complete. The raw JSON textarea is replaced by the guided parameter builder. The TradingView alert message is auto-generated and ready to copy.
