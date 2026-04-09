"use client";
import { useState } from "react";
import {
  Box, Table, Thead, Tbody, Tr, Th, Td, Badge, Text, HStack, Button, Flex, Tooltip,
} from "@chakra-ui/react";
import { useActivity } from "@/lib/hooks/useApi";
import { formatDate } from "@/lib/utils/formatters";

interface Props {
  brokerId: string;
}

const PAGE_SIZE = 50;

export function BrokerTradesTable({ brokerId }: Props) {
  const [offset, setOffset] = useState(0);
  const { data, isLoading } = useActivity(brokerId, offset, PAGE_SIZE);

  if (isLoading) return <Box py={4}><Text color="gray.500">Loading...</Text></Box>;
  if (!data || data.items.length === 0) {
    return <Box py={8} textAlign="center"><Text color="gray.500">No activity recorded</Text></Box>;
  }

  const { items, total } = data;
  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;

  return (
    <Box>
      <Box overflowX="auto">
        <Table size="sm" variant="simple">
          <Thead>
            <Tr>
              <Th>Time</Th>
              <Th>Symbol</Th>
              <Th>Action</Th>
              <Th isNumeric>Qty</Th>
              <Th isNumeric>Fill Price</Th>
              <Th>Source</Th>
              <Th>Strategy</Th>
              <Th>Status</Th>
            </Tr>
          </Thead>
          <Tbody>
            {items.map((item) => (
              <Tr key={item.id}>
                <Td fontSize="xs" color="gray.500">{formatDate(item.created_at)}</Td>
                <Td fontWeight="semibold">{item.symbol}</Td>
                <Td>
                  <Badge colorScheme={item.action === "BUY" ? "green" : "red"}>{item.action}</Badge>
                </Td>
                <Td isNumeric>{item.quantity}</Td>
                <Td isNumeric>
                  {item.fill_price != null ? (
                    `₹${item.fill_price.toLocaleString()}`
                  ) : (
                    <Tooltip label="Exchange1 does not return fill prices for futures orders.">
                      <Text as="span" color="gray.400">—</Text>
                    </Tooltip>
                  )}
                </Td>
                <Td>
                  <Badge
                    colorScheme={item.source === "webhook" ? "blue" : "purple"}
                    variant="subtle"
                    fontSize="xs"
                  >
                    {item.source === "webhook" ? "Webhook" : "Deployment"}
                  </Badge>
                </Td>
                <Td color="gray.500" fontSize="sm">{item.strategy_name ?? "—"}</Td>
                <Td><Badge variant="subtle">{item.status}</Badge></Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </Box>

      {total > PAGE_SIZE && (
        <Flex justify="space-between" align="center" mt={3} px={1}>
          <Text fontSize="sm" color="gray.500">
            {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
          </Text>
          <HStack>
            <Button size="xs" onClick={() => setOffset(offset - PAGE_SIZE)} isDisabled={!canPrev}>
              Prev
            </Button>
            <Button size="xs" onClick={() => setOffset(offset + PAGE_SIZE)} isDisabled={!canNext}>
              Next
            </Button>
          </HStack>
        </Flex>
      )}

      <Text fontSize="xs" color="gray.500" mt={3} px={1}>
        Exchange-direct trades (placed directly on Exchange1) are not visible here.
      </Text>
    </Box>
  );
}
