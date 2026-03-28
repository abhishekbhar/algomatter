"use client";
import {
  Modal, ModalOverlay, ModalContent, ModalHeader, ModalBody, ModalFooter, ModalCloseButton,
  Button, FormControl, FormLabel, Input, Select, HStack, useToast,
} from "@chakra-ui/react";
import { useState } from "react";
import { apiClient } from "@/lib/api/client";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  deploymentId: string;
  onOrderPlaced?: () => void;
}

export function ManualOrderModal({ isOpen, onClose, deploymentId, onOrderPlaced }: Props) {
  const [action, setAction] = useState("buy");
  const [quantity, setQuantity] = useState("");
  const [orderType, setOrderType] = useState("market");
  const [price, setPrice] = useState("");
  const [loading, setLoading] = useState(false);
  const toast = useToast();

  const handleSubmit = async () => {
    setLoading(true);
    try {
      await apiClient(`/api/v1/deployments/${deploymentId}/manual-order`, {
        method: "POST",
        body: {
          action,
          quantity: parseFloat(quantity),
          order_type: orderType,
          price: price ? parseFloat(price) : null,
        },
      });
      toast({ title: "Order placed", status: "success", duration: 2000 });
      onOrderPlaced?.();
      onClose();
    } catch {
      toast({ title: "Failed to place order", status: "error", duration: 3000 });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Place Manual Order</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <FormControl mb={3}>
            <FormLabel>Action</FormLabel>
            <Select value={action} onChange={(e) => setAction(e.target.value)}>
              <option value="buy">Buy</option>
              <option value="sell">Sell</option>
            </Select>
          </FormControl>
          <FormControl mb={3}>
            <FormLabel>Quantity</FormLabel>
            <Input type="number" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
          </FormControl>
          <FormControl mb={3}>
            <FormLabel>Order Type</FormLabel>
            <Select value={orderType} onChange={(e) => setOrderType(e.target.value)}>
              <option value="market">Market</option>
              <option value="limit">Limit</option>
            </Select>
          </FormControl>
          {orderType === "limit" && (
            <FormControl mb={3}>
              <FormLabel>Price</FormLabel>
              <Input type="number" value={price} onChange={(e) => setPrice(e.target.value)} />
            </FormControl>
          )}
        </ModalBody>
        <ModalFooter>
          <HStack>
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button colorScheme="blue" onClick={handleSubmit} isLoading={loading} isDisabled={!quantity}>
              Place Order
            </Button>
          </HStack>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
