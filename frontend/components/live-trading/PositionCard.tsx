"use client";
import { Box, Text, VStack, HStack, Button, useColorModeValue } from "@chakra-ui/react";
import type { PositionInfo } from "@/lib/api/types";

interface Props {
  position: PositionInfo | undefined;
  onClosePosition?: () => void;
}

export function PositionCard({ position, onClosePosition }: Props) {
  const bg = useColorModeValue("white", "gray.700");
  const pos = position?.position;

  return (
    <Box p={4} bg={bg} borderWidth="1px" borderRadius="md">
      <Text fontWeight="bold" mb={2}>Position</Text>
      {!pos ? (
        <Text color="gray.500" fontSize="sm">No open position</Text>
      ) : (
        <VStack align="stretch" spacing={1}>
          <HStack justify="space-between">
            <Text fontSize="sm">Quantity</Text>
            <Text fontSize="sm" fontWeight="semibold">{pos.quantity}</Text>
          </HStack>
          <HStack justify="space-between">
            <Text fontSize="sm">Avg Entry</Text>
            <Text fontSize="sm">₹{pos.avg_entry_price.toFixed(2)}</Text>
          </HStack>
          <HStack justify="space-between">
            <Text fontSize="sm">Unrealized P&L</Text>
            <Text fontSize="sm" color={pos.unrealized_pnl >= 0 ? "green.500" : "red.500"}>
              {pos.unrealized_pnl >= 0 ? "+" : ""}₹{pos.unrealized_pnl.toFixed(2)}
            </Text>
          </HStack>
          {onClosePosition && (
            <Button size="xs" colorScheme="orange" mt={2} onClick={onClosePosition}>
              Close Position
            </Button>
          )}
        </VStack>
      )}
      {position && (
        <Text fontSize="xs" color="gray.500" mt={2}>
          Realized P&L: ₹{position.total_realized_pnl.toFixed(2)}
        </Text>
      )}
    </Box>
  );
}
