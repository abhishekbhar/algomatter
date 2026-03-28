"use client";
import { Box, Text, Flex, Button, useColorModeValue, useToast } from "@chakra-ui/react";
import { DeploymentBadge } from "@/components/shared/DeploymentBadge";
import { apiClient } from "@/lib/api/client";
import type { Deployment } from "@/lib/api/types";

interface DeploymentCardProps {
  deployment: Deployment;
  onUpdate?: () => void;
  onPromote?: (deployment: Deployment) => void;
}

export function DeploymentCard({ deployment: d, onUpdate, onPromote }: DeploymentCardProps) {
  const toast = useToast();
  const bg = useColorModeValue("white", "gray.800");

  const handleAction = async (action: string) => {
    try {
      await apiClient(`/api/v1/deployments/${d.id}/${action}`, { method: "POST" });
      toast({ title: `Deployment ${action}ed`, status: "success", duration: 2000 });
      onUpdate?.();
    } catch {
      toast({ title: `Failed to ${action}`, status: "error", duration: 3000 });
    }
  };

  const canPause = d.status === "running";
  const canResume = d.status === "paused";
  const canStop = ["running", "paused", "pending"].includes(d.status);
  const canPromote = (d.mode === "backtest" && d.status === "completed") ||
                     (d.mode === "paper" && ["running", "paused"].includes(d.status));

  return (
    <Box bg={bg} p={4} borderRadius="lg" border="1px" borderColor="gray.200" shadow="sm">
      <Flex justify="space-between" align="center" mb={2}>
        <DeploymentBadge mode={d.mode} status={d.status} />
        <Text fontSize="xs" color="gray.500">
          {new Date(d.created_at).toLocaleDateString()}
        </Text>
      </Flex>
      <Text fontWeight="medium" mb={1}>{d.symbol}</Text>
      <Text fontSize="sm" color="gray.500" mb={3}>
        {d.interval} &middot; {d.exchange} &middot; {d.product_type}
      </Text>
      <Flex gap={2} flexWrap="wrap">
        {canPause && (
          <Button size="xs" variant="outline" colorScheme="orange" onClick={() => handleAction("pause")}>
            Pause
          </Button>
        )}
        {canResume && (
          <Button size="xs" variant="outline" colorScheme="green" onClick={() => handleAction("resume")}>
            Resume
          </Button>
        )}
        {canStop && (
          <Button size="xs" variant="outline" colorScheme="red" onClick={() => handleAction("stop")}>
            Stop
          </Button>
        )}
        {canPromote && (
          <Button size="xs" colorScheme="blue" onClick={() => onPromote?.(d)}>
            Promote
          </Button>
        )}
      </Flex>
    </Box>
  );
}
