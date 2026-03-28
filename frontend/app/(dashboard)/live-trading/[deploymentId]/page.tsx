"use client";
import {
  Box, Heading, HStack, Grid, GridItem, Tabs, TabList, Tab, TabPanels, TabPanel, Button, useDisclosure,
} from "@chakra-ui/react";
import { useParams } from "next/navigation";
import { useDeployment, useDeploymentPosition, useDeploymentMetrics, useDeploymentComparison } from "@/lib/hooks/useApi";
import { DeploymentBadge } from "@/components/shared/DeploymentBadge";
import { LogViewer } from "@/components/shared/LogViewer";
import { PositionCard } from "@/components/live-trading/PositionCard";
import { PendingOrdersList } from "@/components/live-trading/PendingOrdersList";
import { TradeHistoryTable } from "@/components/live-trading/TradeHistoryTable";
import { ManualOrderModal } from "@/components/live-trading/ManualOrderModal";
import { MetricsGrid } from "@/components/live-trading/MetricsGrid";
import { ComparisonTable } from "@/components/live-trading/ComparisonTable";
import { apiClient } from "@/lib/api/client";

export default function DeploymentDetailPage() {
  const { deploymentId } = useParams<{ deploymentId: string }>();
  const { data: deployment, mutate: refreshDeployment } = useDeployment(deploymentId);
  const { data: position, mutate: refreshPosition } = useDeploymentPosition(deploymentId);
  const { data: metrics } = useDeploymentMetrics(deploymentId);
  const { data: comparison } = useDeploymentComparison(deploymentId);
  const orderModal = useDisclosure();

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
      />
    </Box>
  );
}
