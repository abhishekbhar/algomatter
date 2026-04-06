"use client";
import { Box, Table, Thead, Tbody, Tr, Th, Td, Badge, Text } from "@chakra-ui/react";
import { useBrokerOrders } from "@/lib/hooks/useApi";
import { formatDate } from "@/lib/utils/formatters";

interface Props {
  brokerId: string;
}

export function BrokerOrdersTable({ brokerId }: Props) {
  const { data: orders, isLoading } = useBrokerOrders(brokerId);

  if (isLoading) return <Box py={4}><Text color="gray.500">Loading...</Text></Box>;
  if (!orders || orders.length === 0) {
    return <Box py={8} textAlign="center"><Text color="gray.500">No open orders</Text></Box>;
  }

  return (
    <Box overflowX="auto">
      <Table size="sm" variant="simple">
        <Thead>
          <Tr>
            <Th>Time</Th>
            <Th>Symbol</Th>
            <Th>Action</Th>
            <Th isNumeric>Qty</Th>
            <Th>Type</Th>
            <Th isNumeric>Price</Th>
            <Th>Strategy</Th>
          </Tr>
        </Thead>
        <Tbody>
          {orders.map((order) => (
            <Tr key={order.order_id}>
              <Td fontSize="xs" color="gray.500">{order.created_at ? formatDate(order.created_at) : "—"}</Td>
              <Td fontWeight="semibold">{order.symbol}</Td>
              <Td>
                <Badge colorScheme={order.action === "BUY" ? "green" : "red"}>{order.action}</Badge>
              </Td>
              <Td isNumeric>{order.quantity}</Td>
              <Td>{order.order_type}</Td>
              <Td isNumeric>{order.price != null ? `$${order.price.toLocaleString()}` : "MKT"}</Td>
              <Td color="gray.500" fontSize="sm">{order.deployment_name}</Td>
            </Tr>
          ))}
        </Tbody>
      </Table>
    </Box>
  );
}
