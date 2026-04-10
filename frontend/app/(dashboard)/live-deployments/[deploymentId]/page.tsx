"use client";
import {
  Box, Heading, HStack, Grid, GridItem, Tabs, TabList, Tab, TabPanels, TabPanel, Button, useDisclosure,
  Skeleton, Flex, ButtonGroup, Text, useColorModeValue,
} from "@chakra-ui/react";
import { useParams } from "next/navigation";
import { useDeployment, useDeploymentPosition, useDeploymentMetrics, useDeploymentComparison, useOhlcv, useDeploymentTrades } from "@/lib/hooks/useApi";
import { DeploymentBadge } from "@/components/shared/DeploymentBadge";
import { LogViewer } from "@/components/shared/LogViewer";
import { PositionCard } from "@/components/live-trading/PositionCard";
import { PendingOrdersList } from "@/components/live-trading/PendingOrdersList";
import { TradeHistoryTable } from "@/components/live-trading/TradeHistoryTable";
import { ManualOrderModal } from "@/components/live-trading/ManualOrderModal";
import { MetricsGrid } from "@/components/live-trading/MetricsGrid";
import { ComparisonTable } from "@/components/live-trading/ComparisonTable";
import { apiClient } from "@/lib/api/client";
import { useState, useMemo } from "react";
import { CandlestickChart } from "@/components/charts/CandlestickChart";
import type { TradeMarker } from "@/lib/api/types";

export default function DeploymentDetailPage() {
  const { deploymentId } = useParams<{ deploymentId: string }>();
  const { data: deployment, mutate: refreshDeployment } = useDeployment(deploymentId);
  const { data: position, mutate: refreshPosition } = useDeploymentPosition(deploymentId);
  const { data: metrics } = useDeploymentMetrics(deploymentId);
  const { data: comparison } = useDeploymentComparison(deploymentId);
  const orderModal = useDisclosure();
  const chartBg = useColorModeValue("white", "gray.800");
  const [selectedInterval, setSelectedInterval] = useState<string | null>(null);
  const [timeframe, setTimeframe] = useState<"1W" | "1M" | "3M" | "ALL">("1M");
  const interval = selectedInterval ?? deployment?.interval ?? "1h";
  const isLive = deployment?.status === "running" || deployment?.status === "paused";
  const { data: ohlcv, isLoading: ohlcvLoading } = useOhlcv(
    deployment?.symbol,
    interval,
    deployment?.exchange,
    timeframe,
    isLive,
  );
  const { data: tradesData } = useDeploymentTrades(deploymentId, 0, 500);

  const tradeMarkers = useMemo<TradeMarker[]>(
    () => (tradesData?.trades ?? [])
      .filter((t) => t.fill_price != null)
      .map((t) => {
        const action = t.action.toUpperCase();
        if (action !== "BUY" && action !== "SELL") return null;
        return {
          time: t.filled_at ?? t.created_at,
          price: t.fill_price!,
          action: action as "BUY" | "SELL",
        };
      })
      .filter((m): m is TradeMarker => m !== null),
    [tradesData],
  );

  if (!deployment) return <Box p={6}>Loading...</Box>;

  const canPause = deployment.status === "running";
  const canResume = deployment.status === "paused";
  const canStop = deployment.status === "running" || deployment.status === "paused";

  const handleAction = async (action: string) => {
    await apiClient(`/api/v1/deployments/${deploymentId}/${action}`, { method: "POST" });
    refreshDeployment();
  };

  const handleClosePosition = async () => {
    if (!position?.position) return;
    const qty = Math.abs(position.position.quantity);
    const action = position.position.quantity > 0 ? "sell" : "buy";
    await apiClient(`/api/v1/deployments/${deploymentId}/manual-order`, {
      method: "POST",
      body: { action, quantity: qty, order_type: "market" },
    });
    refreshPosition();
  };

  const openOrders = position?.open_orders ?? [];

  return (
    <Box p={6}>
      <HStack justify="space-between" mb={4}>
        <HStack spacing={3}>
          <Heading size="md">{deployment.strategy_name}</Heading>
          <DeploymentBadge mode={deployment.mode} status={deployment.status} />
        </HStack>
        <HStack>
          {canPause && <Button size="sm" onClick={() => handleAction("pause")}>Pause</Button>}
          {canResume && <Button size="sm" colorScheme="green" onClick={() => handleAction("resume")}>Resume</Button>}
          {canStop && <Button size="sm" colorScheme="orange" onClick={() => handleAction("stop")}>Stop</Button>}
        </HStack>
      </HStack>

      {/* Market Chart */}
      <Box bg={chartBg} p={4} borderRadius="lg" shadow="sm" mb={6}>
        <Flex justify="space-between" mb={2}>
          <ButtonGroup size="xs" variant="outline">
            {(() => {
              const standard = ["1m", "5m", "15m", "1h", "1d"];
              const deploymentInterval = deployment.interval;
              const intervals = standard.includes(deploymentInterval)
                ? standard
                : [deploymentInterval, ...standard];
              return intervals.map((iv) => (
                <Button
                  key={iv}
                  onClick={() => setSelectedInterval(iv)}
                  variant={interval === iv ? "solid" : "outline"}
                  colorScheme={interval === iv ? "blue" : "gray"}
                >
                  {iv}
                </Button>
              ));
            })()}
          </ButtonGroup>
          <ButtonGroup size="xs" variant="outline">
            {(["1W", "1M", "3M", "ALL"] as const).map((tf) => (
              <Button
                key={tf}
                onClick={() => setTimeframe(tf)}
                variant={timeframe === tf ? "solid" : "outline"}
                colorScheme={timeframe === tf ? "blue" : "gray"}
              >
                {tf}
              </Button>
            ))}
          </ButtonGroup>
        </Flex>
        {ohlcvLoading ? (
          <Skeleton height="400px" borderRadius="lg" />
        ) : !ohlcv || ohlcv.length === 0 ? (
          <Flex h="400px" align="center" justify="center">
            <Text color="gray.500">No market data available for {deployment.symbol}</Text>
          </Flex>
        ) : (
          <CandlestickChart data={ohlcv} trades={tradeMarkers} height={400} />
        )}
      </Box>

      <Grid templateColumns={{ base: "1fr", md: "1fr 1fr" }} gap={6}>
        <GridItem>
          <PositionCard position={position ?? undefined} onClosePosition={handleClosePosition} />
          <Box mt={4}>
            <PendingOrdersList
              deploymentId={deploymentId}
              orders={openOrders}
              onPlaceOrder={orderModal.onOpen}
              onOrderCancelled={refreshPosition}
            />
          </Box>
          <Box mt={4}>
            <TradeHistoryTable deploymentId={deploymentId} />
          </Box>
        </GridItem>

        <GridItem>
          <Tabs size="sm" variant="enclosed">
            <TabList>
              <Tab>Analytics</Tab>
              <Tab>Compare</Tab>
              <Tab>Logs</Tab>
            </TabList>
            <TabPanels>
              <TabPanel>
                <MetricsGrid metrics={metrics ?? undefined} />
              </TabPanel>
              <TabPanel>
                <ComparisonTable comparison={comparison} />
              </TabPanel>
              <TabPanel>
                <LogViewer deploymentId={deploymentId} />
              </TabPanel>
            </TabPanels>
          </Tabs>
        </GridItem>
      </Grid>

      <ManualOrderModal
        isOpen={orderModal.isOpen}
        onClose={orderModal.onClose}
        deploymentId={deploymentId}
        onOrderPlaced={refreshPosition}
        currentPrice={ohlcv?.length ? ohlcv[ohlcv.length - 1].close : null}
        availableBalance={position?.portfolio?.available_margin ?? null}
      />
    </Box>
  );
}
