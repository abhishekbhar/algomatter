"use client";
import { Box, Heading, SimpleGrid, Spinner, Center } from "@chakra-ui/react";
import { useState } from "react";
import { useBacktestDeployments, useDeploymentResults, usePaperDeployments } from "@/lib/hooks/useApi";
import { BacktestDeploymentCard } from "@/components/backtest-deployments/BacktestDeploymentCard";
import { EmptyState } from "@/components/shared/EmptyState";
import { apiClient } from "@/lib/api/client";
import { useRouter } from "next/navigation";
import type { Deployment, DeploymentResult } from "@/lib/api/types";

const MAX_SPARKLINES = 10;

function CardWithResult({
  deployment,
  paperDeployments,
  onPromote,
  promotingId,
  index,
}: {
  deployment: Deployment;
  paperDeployments: Deployment[];
  onPromote: (id: string) => void;
  promotingId: string | null;
  index: number;
}) {
  const shouldFetch = deployment.status === "completed" && index < MAX_SPARKLINES;
  const { data: result } = useDeploymentResults(shouldFetch ? deployment.id : undefined);
  const isPromoted = paperDeployments.some((p) => p.promoted_from_id === deployment.id);

  return (
    <BacktestDeploymentCard
      deployment={deployment}
      result={shouldFetch ? result : null}
      isPromoted={isPromoted}
      onPromote={onPromote}
      isPromoting={promotingId === deployment.id}
    />
  );
}

export default function BacktestDeploymentsPage() {
  const { data: deployments, isLoading, mutate } = useBacktestDeployments();
  const { data: paperDeployments = [] } = usePaperDeployments();
  const [promotingId, setPromotingId] = useState<string | null>(null);
  const router = useRouter();

  const handlePromote = async (id: string) => {
    setPromotingId(id);
    try {
      await apiClient(`/api/v1/deployments/${id}/promote`, { method: "POST" });
      mutate();
      router.push("/paper-trading");
    } finally {
      setPromotingId(null);
    }
  };

  if (isLoading) {
    return (
      <Center h="40vh">
        <Spinner size="lg" />
      </Center>
    );
  }

  return (
    <Box p={6}>
      <Heading size="lg" mb={6}>
        Backtest Deployments
      </Heading>

      {!deployments || deployments.length === 0 ? (
        <EmptyState
          title="No backtest deployments yet"
          description="Deploy a hosted strategy as a backtest to see results here."
          actionLabel="Go to Strategies"
          onAction={() => router.push("/strategies/hosted")}
        />
      ) : (
        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
          {deployments.map((dep, i) => (
            <CardWithResult
              key={dep.id}
              deployment={dep}
              paperDeployments={paperDeployments}
              onPromote={handlePromote}
              promotingId={promotingId}
              index={i}
            />
          ))}
        </SimpleGrid>
      )}
    </Box>
  );
}
