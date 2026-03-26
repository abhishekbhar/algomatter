"use client";
import {
  Box, Heading, Flex, Button, SimpleGrid, Tabs, TabList, TabPanels, Tab, TabPanel,
  useDisclosure, useToast, Spinner, Text,
} from "@chakra-ui/react";
import { useParams, useRouter } from "next/navigation";
import { useState, useMemo } from "react";
import { StatCard } from "@/components/shared/StatCard";
import { DataTable, Column } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ConfirmModal } from "@/components/shared/ConfirmModal";
import { EquityCurve } from "@/components/charts/EquityCurve";
import { usePaperSession } from "@/lib/hooks/useApi";
import { apiClient } from "@/lib/api/client";
import { formatCurrency, formatDate } from "@/lib/utils/formatters";

type Position = {
  symbol: string;
  side: string;
  quantity: number;
  avg_entry_price: number;
  unrealized_pnl: number;
  [key: string]: unknown;
};

type Trade = {
  id: string;
  timestamp: string;
  symbol: string;
  action: string;
  quantity: number;
  fill_price: number;
  pnl: number;
  commission: number;
  [key: string]: unknown;
};

export default function PaperTradingDetailPage() {
  const params = useParams();
  const router = useRouter();
  const toast = useToast();
  const id = params?.id as string;
  const { data: session, isLoading, mutate } = usePaperSession(id ?? null);
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [stopping, setStopping] = useState(false);

  const sessionData = session as Record<string, unknown> | undefined;
  const positions = (sessionData?.positions ?? []) as Position[];
  const trades = (sessionData?.trades ?? []) as Trade[];

  const equityData = useMemo(() => {
    if (!trades.length) return [];
    let equity = Number(sessionData?.initial_capital ?? 100000);
    return trades
      .sort((a, b) => a.timestamp.localeCompare(b.timestamp))
      .map((t) => {
        equity += (t.pnl ?? 0) - (t.commission ?? 0);
        return { time: t.timestamp.split("T")[0], value: equity };
      });
  }, [trades, sessionData?.initial_capital]);

  const handleStop = async () => {
    setStopping(true);
    try {
      await apiClient(`/api/v1/paper-trading/sessions/${id}/stop`, { method: "POST" });
      toast({ title: "Session stopped", status: "success", duration: 3000 });
      mutate();
    } catch {
      toast({ title: "Failed to stop session", status: "error", duration: 3000 });
    } finally {
      setStopping(false);
      onClose();
    }
  };

  if (isLoading || !sessionData) {
    return <Box py={8} textAlign="center"><Spinner /></Box>;
  }

  const initialCapital = Number(sessionData.initial_capital ?? 0);
  const currentEquity = Number(sessionData.current_balance ?? 0);
  const realizedPnl = trades.reduce((sum, t) => sum + (t.pnl ?? 0), 0);
  const unrealizedPnl = positions.reduce((sum, p) => sum + (p.unrealized_pnl ?? 0), 0);

  const positionColumns: Column<Position>[] = [
    { key: "symbol", header: "Symbol" },
    {
      key: "side", header: "Side",
      render: (v) => {
        const side = String(v ?? "").toUpperCase();
        return <StatusBadge variant={side === "LONG" ? "success" : "error"} text={side} />;
      },
    },
    { key: "quantity", header: "Quantity" },
    {
      key: "avg_entry_price", header: "Avg Entry Price",
      render: (v) => formatCurrency(Number(v)),
    },
    {
      key: "unrealized_pnl", header: "Unrealized P&L",
      render: (v) => {
        const val = Number(v);
        return <Text color={val >= 0 ? "green.500" : "red.500"}>{formatCurrency(val)}</Text>;
      },
    },
  ];

  const tradeColumns: Column<Trade>[] = [
    {
      key: "timestamp", header: "Time", sortable: true,
      render: (v) => formatDate(String(v ?? "")),
    },
    { key: "symbol", header: "Symbol" },
    {
      key: "action", header: "Action",
      render: (v) => {
        const action = String(v ?? "").toUpperCase();
        return <StatusBadge variant={action === "BUY" ? "success" : "error"} text={action} />;
      },
    },
    { key: "quantity", header: "Quantity" },
    {
      key: "fill_price", header: "Fill Price",
      render: (v) => formatCurrency(Number(v)),
    },
    {
      key: "pnl", header: "P&L",
      render: (v) => {
        const val = Number(v);
        return <Text color={val >= 0 ? "green.500" : "red.500"}>{formatCurrency(val)}</Text>;
      },
    },
    {
      key: "commission", header: "Commission",
      render: (v) => formatCurrency(Number(v)),
    },
  ];

  return (
    <Box>
      <Flex justify="space-between" align="center" mb={6}>
        <Heading size="lg">Session Detail</Heading>
        {sessionData.status === "active" && (
          <Button size="sm" colorScheme="red" onClick={onOpen}>Stop Session</Button>
        )}
      </Flex>

      <SimpleGrid columns={{ base: 2, md: 3, lg: 5 }} spacing={4} mb={6}>
        <StatCard label="Initial Capital" value={formatCurrency(initialCapital)} />
        <StatCard label="Current Equity" value={formatCurrency(currentEquity)} />
        <StatCard label="Unrealized P&L" value={formatCurrency(unrealizedPnl)} />
        <StatCard label="Realized P&L" value={formatCurrency(realizedPnl)} />
        <StatCard label="Open Positions" value={String(positions.length)} />
      </SimpleGrid>

      <Tabs variant="enclosed" mb={6}>
        <TabList>
          <Tab>Positions</Tab>
          <Tab>Trades</Tab>
        </TabList>
        <TabPanels>
          <TabPanel px={0}>
            <DataTable<Position>
              columns={positionColumns}
              data={positions}
              emptyMessage="No open positions."
            />
          </TabPanel>
          <TabPanel px={0}>
            <DataTable<Trade>
              columns={tradeColumns}
              data={trades}
              emptyMessage="No trades yet."
            />
          </TabPanel>
        </TabPanels>
      </Tabs>

      {equityData.length > 0 && (
        <Box>
          <Heading size="md" mb={4}>Equity Curve</Heading>
          <EquityCurve data={equityData} />
        </Box>
      )}

      <ConfirmModal
        isOpen={isOpen}
        onClose={onClose}
        onConfirm={handleStop}
        title="Stop Session"
        message="Are you sure you want to stop this paper trading session? All open positions will be closed."
        confirmLabel="Stop"
        isLoading={stopping}
      />
    </Box>
  );
}
