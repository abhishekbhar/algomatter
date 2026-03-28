"use client";
import { Box, Text, VStack, HStack, IconButton, Button, Badge } from "@chakra-ui/react";
import { MdClose } from "react-icons/md";
import { apiClient } from "@/lib/api/client";

interface PendingOrder {
  id: string;
  action: string;
  quantity: number;
  order_type?: string;
  price?: number;
}

interface Props {
  deploymentId: string;
  orders: PendingOrder[];
  onOrderCancelled?: () => void;
  onPlaceOrder?: () => void;
}

export function PendingOrdersList({ deploymentId, orders, onOrderCancelled, onPlaceOrder }: Props) {
  const handleCancel = async (orderId: string) => {
    await apiClient(`/api/v1/deployments/${deploymentId}/cancel-order`, {
      method: "POST",
      body: { order_id: orderId },
    });
    onOrderCancelled?.();
  };

  return (
    <Box p={4} borderWidth="1px" borderRadius="md">
      <HStack justify="space-between" mb={2}>
        <Text fontWeight="bold">Pending Orders</Text>
        <Button size="xs" colorScheme="blue" onClick={onPlaceOrder}>Place Order</Button>
      </HStack>
      {orders.length === 0 ? (
        <Text color="gray.500" fontSize="sm">No pending orders</Text>
      ) : (
        <VStack align="stretch" spacing={1}>
          {orders.map((order) => (
            <HStack key={order.id} justify="space-between" fontSize="xs">
              <HStack>
                <Badge colorScheme={order.action === "buy" ? "green" : "red"} size="sm">
                  {order.action.toUpperCase()}
                </Badge>
                <Text>{order.quantity} @ {order.price ?? "MKT"}</Text>
              </HStack>
              <IconButton
                aria-label="Cancel order"
                icon={<MdClose />}
                size="xs"
                variant="ghost"
                colorScheme="red"
                onClick={() => handleCancel(order.id)}
              />
            </HStack>
          ))}
        </VStack>
      )}
    </Box>
  );
}
