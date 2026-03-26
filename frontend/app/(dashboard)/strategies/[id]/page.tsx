"use client";
import {
  Box, Heading, Text, Flex, Button, Tabs, TabList, TabPanels, Tab, TabPanel,
  Badge, useColorModeValue, Spinner, Center,
} from "@chakra-ui/react";
import { useRouter, useParams } from "next/navigation";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { DataTable, Column } from "@/components/shared/DataTable";
import { ChartContainer } from "@/components/charts/ChartContainer";
import { EquityCurve } from "@/components/charts/EquityCurve";
import {
  useStrategy,
  useWebhookSignals,
  usePaperSessions,
  useStrategyMetrics,
  useStrategyEquityCurve,
} from "@/lib/hooks/useApi";
import { formatDate, formatCurrency } from "@/lib/utils/formatters";

type Signal = Record<string, unknown>;
type Session = Record<string, unknown>;

const signalColumns: Column<Signal>[] = [
  { key: "symbol", header: "Symbol", sortable: true },
  {
    key: "action", header: "Action",
    render: (v) => {
      const action = String(v ?? "");
      const variant = action.toLowerCase() === "buy" ? "success" : action.toLowerCase() === "sell" ? "error" : "neutral";
      return <StatusBadge variant={variant} text={action} />;
    },
  },
  { key: "price", header: "Price", sortable: true, render: (v) => formatCurrency(Number(v ?? 0)) },
  { key: "received_at", header: "Time", sortable: true, render: (v) => v ? formatDate(String(v)) : "" },
];

const sessionColumns: Column<Session>[] = [
  { key: "id", header: "Session ID" },
  {
    key: "status", header: "Status",
    render: (v) => {
      const status = String(v ?? "");
      const variant = status === "running" ? "success" : status === "stopped" ? "neutral" : "warning";
      return <StatusBadge variant={variant} text={status} />;
    },
  },
  { key: "created_at", header: "Started", render: (v) => v ? formatDate(String(v)) : "" },
];

export default function StrategyDetailPage() {
  const router = useRouter();
  const params = useParams();
  const id = params.id as string;
  const cardBg = useColorModeValue("white", "gray.800");

  const { data: strategy, isLoading } = useStrategy(id);
  const { data: signals } = useWebhookSignals();
  const { data: sessions } = usePaperSessions();
  const { data: metrics } = useStrategyMetrics(id);
  const { data: equityData } = useStrategyEquityCurve(id);

  const strat = strategy as Record<string, unknown> | undefined;
  const strategySignals = (signals ?? []).filter((s) => s.strategy_id === id);
  const strategySessions = (sessions ?? []).filter((s) => s.strategy_id === id);

  if (isLoading) {
    return <Center py={20}><Spinner size="xl" /></Center>;
  }

  if (!strat) {
    return (
      <Box textAlign="center" py={20}>
        <Text color="gray.500">Strategy not found</Text>
        <Button mt={4} onClick={() => router.push("/strategies")}>Back to Strategies</Button>
      </Box>
    );
  }

  return (
    <Box>
      <Flex justify="space-between" align="center" mb={6}>
        <Flex align="center" gap={3}>
          <Heading size="lg">{String(strat.name ?? "")}</Heading>
          <StatusBadge
            variant={strat.is_active ? "success" : "neutral"}
            text={strat.is_active ? "Active" : "Inactive"}
          />
          <Badge colorScheme={strat.mode === "live" ? "red" : "blue"}>
            {String(strat.mode ?? "")}
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
            <Text>{strat.created_at ? formatDate(String(strat.created_at)) : "N/A"}</Text>
          </Box>
          <Box>
            <Text fontSize="sm" color="gray.500">Broker</Text>
            <Text>{strat.broker_connection_id ? String(strat.broker_connection_id) : "None"}</Text>
          </Box>
          <Box>
            <Text fontSize="sm" color="gray.500">Rules</Text>
            <Text>{strat.rules ? JSON.stringify(strat.rules) : "None"}</Text>
          </Box>
        </Flex>
      </Box>

      {/* Tabs */}
      <Tabs variant="enclosed">
        <TabList>
          <Tab>Signals</Tab>
          <Tab>Paper Trading</Tab>
          <Tab>Analytics</Tab>
        </TabList>
        <TabPanels>
          <TabPanel px={0}>
            <DataTable<Signal>
              columns={signalColumns}
              data={strategySignals}
              emptyMessage="No signals for this strategy"
            />
          </TabPanel>
          <TabPanel px={0}>
            <DataTable<Session>
              columns={sessionColumns}
              data={strategySessions}
              emptyMessage="No paper trading sessions"
            />
          </TabPanel>
          <TabPanel px={0}>
            {equityData && (equityData as Array<{ time: string; value: number }>).length > 0 ? (
              <ChartContainer height={300}>
                {() => (
                  <EquityCurve
                    data={equityData as Array<{ time: string; value: number }>}
                    height={300}
                  />
                )}
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
