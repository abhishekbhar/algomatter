"use client";
import { useEffect, useMemo, useState } from "react";
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

  const currentMapping = useMemo(
    () => computeMapping(mode, rows, showOptional ? optionalRows : {}),
    [mode, futuresRows, spotRows, futuresOptional, spotOptional, showOptional]
  );

  useEffect(() => {
    onChange(currentMapping);
  }, [currentMapping, onChange]);

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
              (rowState.fixedValue === null || rowState.fixedValue === "")
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
          isLazy
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
