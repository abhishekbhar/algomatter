"use client";
import {
  Box, Table, Thead, Tbody, Tr, Th, Td, Badge, Text,
  useColorModeValue,
} from "@chakra-ui/react";
import { useLivePositions } from "@/lib/hooks/useApi";
import { OriginBadge } from "@/components/brokers/OriginBadge";

interface Props {
  brokerId: string;
}

export function BrokerPositionsTable({ brokerId }: Props) {
  const { data: positions, isLoading } = useLivePositions(brokerId);
  const borderColor = useColorModeValue("gray.200", "gray.700");

  if (isLoading) return <Box py={4}><Text color="gray.500">Loading...</Text></Box>;
  if (!positions || positions.length === 0) {
    return <Box py={8} textAlign="center"><Text color="gray.500">No open positions on this account.</Text></Box>;
  }

  return (
    <Box overflowX="auto">
      <Table size="sm" variant="simple">
        <Thead>
          <Tr>
            <Th>Symbol</Th>
            <Th>Side</Th>
            <Th isNumeric>Qty</Th>
            <Th isNumeric>Entry Price</Th>
            <Th>Source</Th>
            <Th>Strategy</Th>
          </Tr>
        </Thead>
        <Tbody>
          {positions.map((pos) => (
            <Tr key={`${pos.symbol}-${pos.action}`} borderBottomWidth={1} borderColor={borderColor}>
              <Td fontWeight="semibold">{pos.symbol}</Td>
              <Td>
                <Badge colorScheme={pos.action === "BUY" ? "green" : "red"}>
                  {pos.action === "BUY" ? "LONG" : "SHORT"}
                </Badge>
              </Td>
              <Td isNumeric>{pos.quantity}</Td>
              <Td isNumeric>₹{pos.entry_price.toLocaleString()}</Td>
              <Td><OriginBadge origin={pos.origin} /></Td>
              <Td color="gray.500" fontSize="sm">{pos.strategy_name ?? "—"}</Td>
            </Tr>
          ))}
        </Tbody>
      </Table>
    </Box>
  );
}
