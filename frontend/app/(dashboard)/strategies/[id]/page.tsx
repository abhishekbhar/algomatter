"use client";
import {
  Box, Heading, Text, Flex, Button, Tabs, TabList, TabPanels, Tab, TabPanel,
  Badge, useColorModeValue, Spinner, Center,
} from "@chakra-ui/react";
import { useRouter, useParams } from "next/navigation";
import { useMemo } from "react";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { DataTable, Column } from "@/components/shared/DataTable";
import { ChartContainer, filterByTimeframe, Timeframe } from "@/components/charts/ChartContainer";
import { EquityCurve } from "@/components/charts/EquityCurve";
import { WebhookTradesTable } from "@/components/strategies/WebhookTradesTable";
import {
  useStrategy,
  useStrategySignals,
  usePaperSessions,
  useStrategyMetrics,
  useStrategyEquityCurve,
} from "@/lib/hooks/useApi";
import { formatDate } from "@/lib/utils/formatters";
import type { WebhookSignal, PaperSession, EquityCurvePoint } from "@/lib/api/types";

function EquityCurveWithMemo({ chartData, tf }: { chartData: { time: string; value: number }[]; tf: Timeframe }) {
  const filtered = useMemo(() => filterByTimeframe(chartData, tf), [chartData, tf]);
  return <EquityCurve data={filtered} height={300} />;
}

const signalColumns: Column<WebhookSignal>[] = [
  { key: "received_at", header: "Time", sortable: true, render: (v) => v ? formatDate(String(v)) : "" },
  {
    key: "parsed_signal", header: "Action",
    render: (v) => {
      const sig = v as Record<string, unknown> | null;
      if (!sig?.action) return "—";
      const action = String(sig.action).toUpperCase();
      return (
        <Badge colorScheme={action === "BUY" ? "green" : action === "SELL" ? "red" : "gray"} size="sm">
          {action}
        </Badge>
      );
    },
  },
  {
    key: "status", header: "Rule",
    render: (v) => {
      const status = String(v ?? "");
      const variant = status === "passed" ? "success" : status === "blocked_by_rule" ? "error" : "warning";
      return <StatusBadge variant={variant} text={status} />;
    },
  },
  {
    key: "execution_result", header: "Execution",
    render: (v) => {
      if (!v) return "—";
      const r = String(v);
      const variant = r === "filled" ? "success" : r === "broker_error" ? "error" : "warning";
      return <StatusBadge variant={variant} text={r} />;
    },
  },
  {
    key: "execution_detail", header: "Fill Price",
    render: (v) => {
      const detail = v as WebhookSignal["execution_detail"];
      if (!detail?.fill_price) return "—";
      return Number(detail.fill_price).toFixed(2);
    },
  },
];

const sessionColumns: Column<PaperSession>[] = [
  { key: "id", header: "Session ID" },
  {
    key: "status", header: "Status",
    render: (v) => {
      const status = String(v ?? "");
      const variant = status === "running" ? "success" : status === "stopped" ? "neutral" : "warning";
      return <StatusBadge variant={variant} text={status} />;
    },
  },
  { key: "started_at", header: "Started", render: (v) => v ? formatDate(String(v)) : "" },
];

export default function StrategyDetailPage() {
  const router = useRouter();
  const params = useParams();
  const id = params.id as string;
  const cardBg = useColorModeValue("white", "gray.800");

  const { data: strategy, isLoading } = useStrategy(id);
  const { data: signals } = useStrategySignals(id);
  const { data: sessions } = usePaperSessions();
  const { data: metrics } = useStrategyMetrics(id);
  const { data: equityData } = useStrategyEquityCurve(id);

  const strategySessions = (sessions ?? []).filter((s) => s.strategy_id === id);

  if (isLoading) {
    return <Center py={20}><Spinner size="xl" /></Center>;
  }

  if (!strategy) {
    return (
      <Box textAlign="center" py={20}>
        <Text color="gray.500">Strategy not found</Text>
        <Button mt={4} onClick={() => router.push("/strategies")}>Back to Strategies</Button>
      </Box>
    );
  }

  const chartData = useMemo(
    () => (equityData ?? []).map((d: EquityCurvePoint) => ({
      time: d.timestamp.split("T")[0],
      value: d.equity,
    })),
    [equityData],
  );

  return (
    <Box>
      <Flex justify="space-between" align="center" mb={6}>
        <Flex align="center" gap={3}>
          <Heading size="lg">{strategy.name}</Heading>
          <StatusBadge
            variant={strategy.is_active ? "success" : "neutral"}
            text={strategy.is_active ? "Active" : "Inactive"}
          />
          <Badge colorScheme={strategy.mode === "live" ? "red" : "blue"}>
            {strategy.mode}
          </Badge>
        </Flex>
        <Flex gap={3}>
          <Button size="sm" onClick={() => router.push(`/strategies/${id}/edit`)}>
            Edit
          </Button>
          <Button size="sm" variant="ghost" onClick={() => router.push("/strategies")}>
            Back
          </Button>
        </Flex>
      </Flex>

      {/* Info Card */}
      <Box bg={cardBg} p={4} borderRadius="lg" shadow="sm" mb={6}>
        <Flex gap={8} wrap="wrap">
          <Box>
            <Text fontSize="sm" color="gray.500">Created</Text>
            <Text>{strategy.created_at ? formatDate(strategy.created_at) : "N/A"}</Text>
          </Box>
          <Box>
            <Text fontSize="sm" color="gray.500">Broker</Text>
            <Text>{strategy.broker_connection_id ?? "None"}</Text>
          </Box>
          <Box>
            <Text fontSize="sm" color="gray.500">Rules</Text>
            <Text>{strategy.rules ? JSON.stringify(strategy.rules) : "None"}</Text>
          </Box>
        </Flex>
      </Box>

      {/* Tabs */}
      <Tabs variant="enclosed">
        <TabList>
          <Tab>Signals</Tab>
          <Tab>Trades</Tab>
          <Tab>Paper Trading</Tab>
          <Tab>Analytics</Tab>
        </TabList>
        <TabPanels>
          <TabPanel px={0}>
            <DataTable<WebhookSignal>
              columns={signalColumns}
              data={signals ?? []}
              emptyMessage="No signals for this strategy"
            />
          </TabPanel>
          <TabPanel px={0}>
            <WebhookTradesTable strategyId={id} />
          </TabPanel>
          <TabPanel px={0}>
            <DataTable<PaperSession>
              columns={sessionColumns}
              data={strategySessions}
              emptyMessage="No paper trading sessions"
            />
          </TabPanel>
          <TabPanel px={0}>
            {chartData.length > 0 ? (
              <ChartContainer height={300}>
                {(tf) => <EquityCurveWithMemo chartData={chartData} tf={tf} />}
              </ChartContainer>
            ) : (
              <Text color="gray.500" textAlign="center" py={8}>
                No analytics data available yet
              </Text>
            )}
            {metrics != null && (
              <Box mt={4}>
                <Text fontSize="sm" color="gray.500">
                  Metrics: {JSON.stringify(metrics)}
                </Text>
              </Box>
            )}
          </TabPanel>
        </TabPanels>
      </Tabs>
    </Box>
  );
}
