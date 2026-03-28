"use client";
import { Badge, Flex } from "@chakra-ui/react";

interface DeploymentBadgeProps {
  mode: string;
  status: string;
}

const MODE_COLORS: Record<string, string> = {
  backtest: "blue",
  paper: "yellow",
  live: "green",
};

const STATUS_COLORS: Record<string, string> = {
  running: "green",
  paused: "orange",
  stopped: "red",
  completed: "blue",
  failed: "red",
  pending: "gray",
};

export function DeploymentBadge({ mode, status }: DeploymentBadgeProps) {
  return (
    <Flex gap={1}>
      <Badge colorScheme={MODE_COLORS[mode] || "gray"} variant="subtle" fontSize="xs">
        {mode}
      </Badge>
      <Badge colorScheme={STATUS_COLORS[status] || "gray"} variant="solid" fontSize="xs">
        {status}
      </Badge>
    </Flex>
  );
}
