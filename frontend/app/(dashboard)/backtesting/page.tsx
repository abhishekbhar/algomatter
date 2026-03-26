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
import { useStrategies, useBacktests } from "@/lib/hooks/useApi";
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

export default function BacktestingPage() {
  const toast = useToast();
  const { data: strategies } = useStrategies();
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
          setResult(data);
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
  (strategies ?? []).forEach((s) => { strategyMap[s.id] = s.name; });

  const historyColumns: Column<BacktestResultType>[] = [
    {
      key: "created_at", header: "Date", sortable: true,
      render: (v) => formatDate(String(v ?? "")),
    },
    {
      key: "strategy_id", header: "Strategy",
      render: (v) => strategyMap[String(v)] ?? String(v),
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

      <Tabs variant="enclosed">
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
                      {(strategies ?? []).map((s) => (
                        <option key={s.id} value={s.id}>{s.name}</option>
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
                      <StatCard label="Total Return" value={formatPercent(metrics.total_return)} />
                      <StatCard label="Sharpe Ratio" value={metrics.sharpe_ratio.toFixed(2)} />
                      <StatCard label="Max Drawdown" value={formatPercent(metrics.max_drawdown)} />
                      <StatCard label="Win Rate" value={formatPercent(metrics.win_rate)} />
                      <StatCard label="Total Trades" value={String(metrics.total_trades)} />
                      <StatCard label="Profit Factor" value={metrics.profit_factor.toFixed(2)} />
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
              emptyMessage="No backtests yet."
            />
          </TabPanel>
        </TabPanels>
      </Tabs>
    </Box>
  );
}
