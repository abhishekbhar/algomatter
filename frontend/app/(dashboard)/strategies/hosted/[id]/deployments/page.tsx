"use client";
import { useState } from "react";
import {
  Box, Heading, Flex, Button, SimpleGrid, Text, useDisclosure, Tabs, TabList, TabPanels, Tab, TabPanel,
} from "@chakra-ui/react";
import { useParams, useRouter } from "next/navigation";
import { DeploymentCard } from "@/components/deployments/DeploymentCard";
import { PromoteModal } from "@/components/deployments/PromoteModal";
import { LogViewer } from "@/components/shared/LogViewer";
import { useDeployments, useHostedStrategy } from "@/lib/hooks/useApi";
import type { Deployment } from "@/lib/api/types";

export default function DeploymentsPage() {
  const params = useParams();
  const router = useRouter();
  const strategyId = params.id as string;
  const { data: strategy } = useHostedStrategy(strategyId);
  const { data: deployments, mutate } = useDeployments(strategyId);
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [promoteTarget, setPromoteTarget] = useState<Deployment | null>(null);
  const [selectedDeployment, setSelectedDeployment] = useState<string | null>(null);

  const handlePromote = (d: Deployment) => {
    setPromoteTarget(d);
    onOpen();
  };

  const grouped = {
    backtest: (deployments ?? []).filter(d => d.mode === "backtest"),
    paper: (deployments ?? []).filter(d => d.mode === "paper"),
    live: (deployments ?? []).filter(d => d.mode === "live"),
  };

  return (
    <Box>
      <Flex justify="space-between" align="center" mb={6}>
        <Box>
          <Heading size="lg">Deployments</Heading>
          {strategy && <Text color="gray.500" fontSize="sm">{strategy.name}</Text>}
        </Box>
        <Flex gap={2}>
          <Button size="sm" variant="outline" onClick={() => router.push(`/strategies/hosted/${strategyId}`)}>
            Back to Editor
          </Button>
        </Flex>
      </Flex>

      <Tabs variant="line" mb={6}>
        <TabList>
          <Tab>All ({(deployments ?? []).length})</Tab>
          <Tab>Backtest ({grouped.backtest.length})</Tab>
          <Tab>Paper ({grouped.paper.length})</Tab>
          <Tab>Live ({grouped.live.length})</Tab>
        </TabList>
        <TabPanels>
          {[deployments ?? [], grouped.backtest, grouped.paper, grouped.live].map((list, i) => (
            <TabPanel key={i} px={0}>
              {list.length === 0 ? (
                <Text color="gray.500" textAlign="center" py={8}>No deployments</Text>
              ) : (
                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
                  {list.map((d) => (
                    <Box key={d.id} onClick={() => setSelectedDeployment(d.id === selectedDeployment ? null : d.id)} cursor="pointer">
                      <DeploymentCard deployment={d} onUpdate={() => mutate()} onPromote={handlePromote} />
                      {selectedDeployment === d.id && (
                        <Box mt={2}>
                          <LogViewer deploymentId={d.id} />
                        </Box>
                      )}
                    </Box>
                  ))}
                </SimpleGrid>
              )}
            </TabPanel>
          ))}
        </TabPanels>
      </Tabs>

      <PromoteModal
        isOpen={isOpen}
        onClose={() => { setPromoteTarget(null); onClose(); }}
        deployment={promoteTarget}
        onPromoted={() => mutate()}
      />
    </Box>
  );
}
