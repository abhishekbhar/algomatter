"use client";
import {
  Box, Text, HStack, VStack, Badge, Button, Skeleton, useColorModeValue, Flex,
} from "@chakra-ui/react";
import { useRouter } from "next/navigation";
import { SparklineChart } from "./SparklineChart";
import type { Deployment, DeploymentResult } from "@/lib/api/types";

interface Props {
  deployment: Deployment;
  result: DeploymentResult | null | undefined;
  isPromoted: boolean;
  onPromote: (id: string) => void;
  isPromoting?: boolean;
}

const STATUS_COLORS: Record<string, string> = {
  running: "yellow",
  paused: "yellow",
  pending: "gray",
  completed: "green",
  failed: "red",
  stopped: "red",
};

function MetricTile({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <Box textAlign="center">
      <Text fontSize="9px" color="gray.500" textTransform="uppercase" letterSpacing="wide">
        {label}
      </Text>
      <Text fontSize="sm" fontWeight="bold" color={color ?? "inherit"}>
        {value}
      </Text>
    </Box>
  );
}

export function BacktestDeploymentCard({
  deployment,
  result,
  isPromoted,
  onPromote,
  isPromoting = false,
}: Props) {
  const router = useRouter();
  const bg = useColorModeValue("white", "gray.700");
  const borderColor = useColorModeValue("gray.200", "gray.600");
  const isCompleted = deployment.status === "completed";
  const isFailed = deployment.status === "failed" || deployment.status === "stopped";
  const metrics = result?.metrics;

  const returnColor =
    metrics == null
      ? "gray.500"
      : metrics.total_return >= 0
      ? "green.400"
      : "red.400";

  return (
    <Box
      p={4}
      bg={bg}
      borderWidth="1px"
      borderColor={borderColor}
      borderRadius="md"
      cursor="pointer"
      _hover={{ shadow: "md" }}
      onClick={() => router.push(`/backtest-deployments/${deployment.id}`)}
    >
      <VStack align="stretch" spacing={3}>
        {/* Header */}
        <Flex justify="space-between" align="flex-start">
          <Box>
            <Text fontWeight="bold" fontSize="sm" noOfLines={1}>
              {deployment.strategy_name}
            </Text>
            <Text fontSize="xs" color="gray.500">
              {deployment.symbol} · {deployment.exchange} · {deployment.interval}
            </Text>
          </Box>
          <Badge colorScheme={STATUS_COLORS[deployment.status] ?? "gray"} variant="solid" fontSize="xs">
            {deployment.status}
          </Badge>
        </Flex>

        {/* Sparkline */}
        {isCompleted && (
          <Box>
            {result === undefined ? (
              <Skeleton height="40px" borderRadius="sm" />
            ) : (
              <SparklineChart data={result !== null ? result.equity_curve : null} width={220} height={40} />
            )}
          </Box>
        )}

        {/* Metrics */}
        {isFailed ? (
          <Text fontSize="xs" color="red.400">
            View Logs →
          </Text>
        ) : (
          <HStack justify="space-between">
            <MetricTile
              label="Return"
              value={metrics != null ? `${metrics.total_return >= 0 ? "+" : ""}${metrics.total_return.toFixed(1)}%` : "—"}
              color={returnColor}
            />
            <MetricTile
              label="Win Rate"
              value={metrics != null ? `${metrics.win_rate.toFixed(0)}%` : "—"}
            />
            <MetricTile
              label="Max DD"
              value={metrics != null ? `${metrics.max_drawdown.toFixed(1)}%` : "—"}
              color={metrics != null ? "red.400" : undefined}
            />
            <MetricTile
              label="Trades"
              value={metrics != null ? String(metrics.total_trades) : "—"}
            />
          </HStack>
        )}

        {/* Promote / Promoted */}
        {isCompleted && (
          <Box onClick={(e) => e.stopPropagation()}>
            {isPromoted ? (
              <Text fontSize="xs" color="blue.400">
                ✓ Promoted to Paper
              </Text>
            ) : (
              <Button
                size="xs"
                colorScheme="blue"
                variant="outline"
                isLoading={isPromoting}
                onClick={() => onPromote(deployment.id)}
                width="full"
              >
                Promote to Paper →
              </Button>
            )}
          </Box>
        )}
      </VStack>
    </Box>
  );
}
