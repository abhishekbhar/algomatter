"use client";
import {
  Box, Heading, Flex, Button, Tabs, TabList, TabPanels, Tab, TabPanel,
  FormControl, FormLabel, Input, Select, Textarea, NumberInput, NumberInputField,
  VStack, SimpleGrid, useToast, Spinner, Text,
} from "@chakra-ui/react";
import { useState, useRef, useCallback, useEffect } from "react";
import { StatCard } from "@/components/shared/StatCard";
import { DataTable, Column } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { EquityCurve } from "@/components/charts/EquityCurve";
import { useAllStrategies, useBacktests } from "@/lib/hooks/useApi";
import { apiClient } from "@/lib/api/client";
import { formatDate, formatCurrency, formatPercent } from "@/lib/utils/formatters";
import { POLLING_INTERVALS } from "@/lib/utils/constants";

import type { BacktestResult as BacktestResultType } from "@/lib/api/types";

type BacktestDisplay = {
  id: string;
  status: string;
  metrics?: {
    total_return: number;
    sharpe_ratio: number;
    max_drawdown: number;
    win_rate: number;
    total_trades: number;
    profit_factor: number;
  };
  equity_curve?: Array<{ time: string; value: number }>;
  trades?: Array<Record<string, unknown>>;
};

function normalizeBacktest(data: unknown): BacktestDisplay {
  const raw = data as Record<string, unknown>;
  const out: BacktestDisplay = {
    id: String(raw.id ?? ""),
    status: String(raw.status ?? ""),
    metrics: raw.metrics as BacktestDisplay["metrics"],
  };
  // equity_curve: {timestamp,equity} → {time,value}, deduplicate by time (keep last)
  const ec = raw.equity_curve as Array<Record<string, unknown>> | undefined;
  if (ec) {
    const byTime = new Map<string, { time: string; value: number }>();
    for (const p of ec) {
      const raw = p.time ?? p.timestamp;
      if (!raw) continue; // skip entries with no timestamp (e.g. initial equity point)
      const time = String(raw).split("T")[0].split(" ")[0];
      if (!time || !/^\d{4}-\d{2}-\d{2}/.test(time)) continue;
      byTime.set(time, { time, value: Number(p.value ?? p.equity ?? 0) });
    }
    out.equity_curve = Array.from(byTime.values());
  }
  // trade_log → trades, map fill_price → price
  const trades = (raw.trades ?? raw.trade_log) as Array<Record<string, unknown>> | undefined;
  if (trades) {
    out.trades = trades.map((t) => ({ ...t, price: t.price ?? t.fill_price }));
  }
  return out;
}

export default function BacktestingPage() {
  const toast = useToast();
  const strategies = useAllStrategies();
  const { data: backtests, mutate: mutateBacktests } = useBacktests();

  // Form state
  const [strategyId, setStrategyId] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [capital, setCapital] = useState(100000);
  const [slippage, setSlippage] = useState(0.1);
  const [commission, setCommission] = useState(0.03);
  const [signalsCsv, setSignalsCsv] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Run state
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<BacktestDisplay | null>(null);
  const [tabIndex, setTabIndex] = useState(0);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  const pollBacktest = useCallback((id: string) => {
    pollingRef.current = setInterval(async () => {
      try {
        const data = await apiClient<BacktestDisplay>(`/api/v1/backtests/${id}`);
        if (data.status === "completed" || data.status === "failed") {
          if (pollingRef.current) clearInterval(pollingRef.current);
          pollingRef.current = null;
          setRunning(false);
          setResult(normalizeBacktest(data));
          mutateBacktests();
          if (data.status === "failed") {
            toast({ title: "Backtest failed", status: "error", duration: 3000 });
          }
        }
      } catch {
        if (pollingRef.current) clearInterval(pollingRef.current);
        pollingRef.current = null;
        setRunning(false);
        toast({ title: "Error polling backtest", status: "error", duration: 3000 });
      }
    }, POLLING_INTERVALS.BACKTEST_STATUS);
  }, [mutateBacktests, toast]);

  const handleRun = async () => {
    if (!strategyId || !startDate || !endDate) return;
    setRunning(true);
    setResult(null);
    try {
      const data = await apiClient<{ id: string }>("/api/v1/backtests", {
        method: "POST",
        body: {
          strategy_id: strategyId,
          start_date: startDate,
          end_date: endDate,
          capital,
          slippage_pct: slippage,
          commission_pct: commission,
          signals_csv: signalsCsv || undefined,
        },
      });
      pollBacktest(data.id);
    } catch {
      setRunning(false);
      toast({ title: "Failed to start backtest", status: "error", duration: 3000 });
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      setSignalsCsv(evt.target?.result as string);
    };
    reader.readAsText(file);
  };

  const handleViewBacktest = async (row: BacktestResultType) => {
    try {
      const data = await apiClient<Record<string, unknown>>(`/api/v1/backtests/${row.id}`);
      setResult(normalizeBacktest(data));
      // Restore form parameters from config
      const cfg = data.config as Record<string, unknown> | undefined;
      if (cfg) {
        if (cfg.start_date) setStartDate(String(cfg.start_date));
        if (cfg.end_date) setEndDate(String(cfg.end_date));
        if (cfg.capital != null) setCapital(Number(cfg.capital));
        if (cfg.slippage_pct != null) setSlippage(Number(cfg.slippage_pct));
        if (cfg.commission_pct != null) setCommission(Number(cfg.commission_pct));
      }
      if (data.strategy_id) setStrategyId(String(data.strategy_id));
      setTabIndex(0);
    } catch {
      toast({ title: "Failed to load backtest", status: "error", duration: 3000 });
    }
  };

  const handleDeleteBacktest = async (id: string) => {
    try {
      await apiClient(`/api/v1/backtests/${id}`, { method: "DELETE" });
      toast({ title: "Backtest deleted", status: "success", duration: 3000 });
      mutateBacktests();
    } catch {
      toast({ title: "Failed to delete backtest", status: "error", duration: 3000 });
    }
  };

  const strategyMap: Record<string, string> = {};
  strategies.forEach((s) => { strategyMap[s.id] = s.name; });

  const historyColumns: Column<BacktestResultType>[] = [
    {
      key: "created_at", header: "Date", sortable: true,
      render: (v) => formatDate(String(v ?? "")),
    },
    {
      key: "strategy_name", header: "Strategy",
      render: (v, row) => String(v ?? strategyMap[String(row.strategy_id)] ?? row.strategy_id ?? "—"),
    },
    {
      key: "status", header: "Status",
      render: (v) => {
        const s = String(v ?? "");
        const variant = s === "completed" ? "success" : s === "failed" ? "error" : "info";
        return <StatusBadge variant={variant} text={s} />;
      },
    },
    {
      key: "id", header: "",
      render: (v) => (
        <Button size="xs" colorScheme="red" variant="ghost" onClick={(e) => { e.stopPropagation(); handleDeleteBacktest(String(v)); }}>
          Delete
        </Button>
      ),
    },
  ];

  const tradeColumns: Column<Record<string, unknown>>[] = [
    { key: "timestamp", header: "Time", sortable: true, render: (v) => formatDate(String(v ?? "")) },
    { key: "symbol", header: "Symbol" },
    {
      key: "action", header: "Action",
      render: (v) => {
        const a = String(v ?? "").toUpperCase();
        return <StatusBadge variant={a === "BUY" ? "success" : "error"} text={a} />;
      },
    },
    { key: "quantity", header: "Qty" },
    { key: "price", header: "Price", render: (v) => formatCurrency(Number(v)) },
    {
      key: "pnl", header: "P&L",
      render: (v) => {
        const val = Number(v ?? 0);
        return <Text color={val >= 0 ? "green.500" : "red.500"}>{formatCurrency(val)}</Text>;
      },
    },
  ];

  const metrics = result?.metrics;

  return (
    <Box>
      <Heading size="lg" mb={6}>Backtesting</Heading>

      <Tabs variant="enclosed" index={tabIndex} onChange={setTabIndex}>
        <TabList>
          <Tab>Run Backtest</Tab>
          <Tab>History</Tab>
        </TabList>
        <TabPanels>
          <TabPanel px={0}>
            <Flex gap={6} direction={{ base: "column", lg: "row" }}>
              {/* Left panel: Form */}
              <Box flex={1} maxW={{ lg: "400px" }}>
                <VStack spacing={4} align="stretch">
                  <FormControl isRequired>
                    <FormLabel>Strategy</FormLabel>
                    <Select placeholder="Select strategy" value={strategyId} onChange={(e) => setStrategyId(e.target.value)}>
                      {strategies.map((s) => (
                        <option key={s.id} value={s.id}>{s.name} ({s.type})</option>
                      ))}
                    </Select>
                  </FormControl>

                  <FormControl isRequired>
                    <FormLabel>Start Date</FormLabel>
                    <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
                  </FormControl>

                  <FormControl isRequired>
                    <FormLabel>End Date</FormLabel>
                    <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
                  </FormControl>

                  <FormControl>
                    <FormLabel>Initial Capital</FormLabel>
                    <NumberInput min={1000} value={capital} onChange={(_, val) => setCapital(val || 100000)}>
                      <NumberInputField />
                    </NumberInput>
                  </FormControl>

                  <FormControl>
                    <FormLabel>Slippage %</FormLabel>
                    <NumberInput min={0} step={0.01} value={slippage} onChange={(_, val) => setSlippage(val || 0)}>
                      <NumberInputField />
                    </NumberInput>
                  </FormControl>

                  <FormControl>
                    <FormLabel>Commission %</FormLabel>
                    <NumberInput min={0} step={0.01} value={commission} onChange={(_, val) => setCommission(val || 0)}>
                      <NumberInputField />
                    </NumberInput>
                  </FormControl>

                  <FormControl>
                    <FormLabel>Signal CSV</FormLabel>
                    <Textarea
                      placeholder="Paste CSV signals here..."
                      value={signalsCsv}
                      onChange={(e) => setSignalsCsv(e.target.value)}
                      rows={4}
                    />
                    <Input
                      type="file"
                      accept=".csv"
                      ref={fileInputRef}
                      mt={2}
                      size="sm"
                      onChange={handleFileUpload}
                    />
                  </FormControl>

                  <Button
                    colorScheme="blue"
                    onClick={handleRun}
                    isLoading={running}
                    isDisabled={!strategyId || !startDate || !endDate}
                  >
                    Run Backtest
                  </Button>
                </VStack>
              </Box>

              {/* Right panel: Results */}
              <Box flex={2}>
                {running && (
                  <Flex justify="center" align="center" py={16}>
                    <VStack spacing={4}>
                      <Spinner size="xl" />
                      <Text color="gray.500">Running backtest...</Text>
                    </VStack>
                  </Flex>
                )}

                {!running && !result && (
                  <Flex justify="center" align="center" py={16}>
                    <Text color="gray.500">Configure and run a backtest to see results.</Text>
                  </Flex>
                )}

                {!running && result && result.status === "completed" && metrics && (
                  <VStack spacing={6} align="stretch">
                    <SimpleGrid columns={{ base: 2, md: 3 }} spacing={4}>
                      <StatCard label="Total Return" value={formatPercent(metrics.total_return ?? 0)} />
                      <StatCard label="Sharpe Ratio" value={(metrics.sharpe_ratio ?? 0).toFixed(2)} />
                      <StatCard label="Max Drawdown" value={formatPercent(metrics.max_drawdown ?? 0)} />
                      <StatCard label="Win Rate" value={formatPercent(metrics.win_rate ?? 0)} />
                      <StatCard label="Total Trades" value={String(metrics.total_trades ?? 0)} />
                      <StatCard label="Profit Factor" value={(metrics.profit_factor ?? 0).toFixed(2)} />
                    </SimpleGrid>

                    {result.equity_curve && result.equity_curve.length > 0 && (
                      <Box>
                        <Heading size="sm" mb={2}>Equity Curve</Heading>
                        <EquityCurve data={result.equity_curve} />
                      </Box>
                    )}

                    {result.trades && result.trades.length > 0 && (
                      <Box>
                        <Heading size="sm" mb={2}>Trade Log</Heading>
                        <DataTable
                          columns={tradeColumns}
                          data={result.trades}
                          emptyMessage="No trades."
                        />
                      </Box>
                    )}
                  </VStack>
                )}
              </Box>
            </Flex>
          </TabPanel>

          <TabPanel px={0}>
            <DataTable<BacktestResultType>
              columns={historyColumns}
              data={backtests ?? []}
              onRowClick={handleViewBacktest}
              emptyMessage="No backtests yet."
            />
          </TabPanel>
        </TabPanels>
      </Tabs>
    </Box>
  );
}
