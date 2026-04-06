"use client";
import { Box, Text, HStack, VStack, useColorModeValue } from "@chakra-ui/react";
import { useRouter } from "next/navigation";
import { DeploymentBadge } from "@/components/shared/DeploymentBadge";
import type { Deployment, PositionInfo } from "@/lib/api/types";

interface Props {
  deployment: Deployment;
  position?: PositionInfo;
}

export function LiveDeploymentCard({ deployment, position }: Props) {
  const router = useRouter();
  const bg = useColorModeValue("white", "gray.700");
  const borderColor = useColorModeValue("gray.200", "gray.600");
  const pnl = position?.total_realized_pnl ?? 0;

  return (
    <Box
      p={4}
      bg={bg}
      borderWidth="1px"
      borderColor={borderColor}
      borderRadius="md"
      cursor="pointer"
      _hover={{ shadow: "md" }}
      onClick={() => router.push(`/live-deployments/${deployment.id}`)}
    >
      <VStack align="stretch" spacing={2}>
        <Text fontWeight="bold" fontSize="sm" noOfLines={1}>
          {deployment.strategy_name}
        </Text>
        <Text fontSize="xs" color="gray.500">{deployment.symbol}</Text>
        <HStack>
          <DeploymentBadge mode={deployment.mode} status={deployment.status} />
        </HStack>
        <Text
          fontSize="sm"
          fontWeight="semibold"
          color={pnl >= 0 ? "green.500" : "red.500"}
        >
          P&L: {pnl >= 0 ? "+" : ""}₹{pnl.toFixed(2)}
        </Text>
        <Text fontSize="xs" color="gray.500">
          {position?.open_orders_count ?? 0} open orders
        </Text>
      </VStack>
    </Box>
  );
}
