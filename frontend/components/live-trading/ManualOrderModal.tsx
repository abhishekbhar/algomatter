"use client";
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  Button,
  FormControl,
  FormLabel,
  Input,
  Select,
  Slider,
  SliderTrack,
  SliderFilledTrack,
  SliderThumb,
  HStack,
  Flex,
  Text,
  useToast,
} from "@chakra-ui/react";
import { useState } from "react";
import { apiClient } from "@/lib/api/client";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  deploymentId: string;
  onOrderPlaced?: () => void;
  currentPrice?: number | null;
  availableBalance?: number | null;
}

export function ManualOrderModal({
  isOpen,
  onClose,
  deploymentId,
  onOrderPlaced,
  currentPrice,
  availableBalance,
}: Props) {
  const [action, setAction] = useState("buy");
  const [quantity, setQuantity] = useState("");
  const [quantityPct, setQuantityPct] = useState(0);
  const [orderType, setOrderType] = useState("market");
  const [price, setPrice] = useState("");
  const [priceSliderPct, setPriceSliderPct] = useState(50);
  const [triggerPrice, setTriggerPrice] = useState("");
  const [takeProfit, setTakeProfit] = useState("");
  const [stopLoss, setStopLoss] = useState("");
  const [loading, setLoading] = useState(false);
  const toast = useToast();

  const isLimitLike = orderType === "limit" || orderType === "stop_limit";
  const showTriggerPrice = orderType === "stop" || orderType === "stop_limit";

  // Price from slider (±5% of current price)
  const handlePriceSliderChange = (val: number) => {
    setPriceSliderPct(val);
    if (currentPrice) {
      const min = currentPrice * 0.95;
      const max = currentPrice * 1.05;
      setPrice((min + (max - min) * (val / 100)).toFixed(2));
    }
  };

  // Quantity from % of balance
  const handleQuantityPctChange = (val: number) => {
    setQuantityPct(val);
    if (availableBalance && currentPrice) {
      const effectivePrice = price ? parseFloat(price) : currentPrice;
      if (effectivePrice > 0) {
        const maxQty = availableBalance / effectivePrice;
        setQuantity((maxQty * (val / 100)).toFixed(6));
      }
    }
  };

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const body: Record<string, unknown> = {
        action,
        quantity: parseFloat(quantity),
        order_type: orderType,
        price: price ? parseFloat(price) : null,
        trigger_price: triggerPrice ? parseFloat(triggerPrice) : null,
        take_profit: takeProfit ? parseFloat(takeProfit) : null,
        stop_loss: stopLoss ? parseFloat(stopLoss) : null,
      };
      await apiClient(`/api/v1/deployments/${deploymentId}/manual-order`, {
        method: "POST",
        body,
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
            <FormLabel>Order Type</FormLabel>
            <Select
              value={orderType}
              onChange={(e) => setOrderType(e.target.value)}
            >
              <option value="market">Market</option>
              <option value="limit">Limit</option>
              <option value="stop">Stop</option>
              <option value="stop_limit">Stop Limit</option>
            </Select>
          </FormControl>

          {isLimitLike && (
            <FormControl mb={3}>
              <FormLabel>Price</FormLabel>
              <Input
                type="number"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder={currentPrice?.toFixed(2)}
              />
              {currentPrice && (
                <>
                  <Slider
                    mt={1}
                    min={0}
                    max={100}
                    value={priceSliderPct}
                    onChange={handlePriceSliderChange}
                    size="sm"
                  >
                    <SliderTrack>
                      <SliderFilledTrack />
                    </SliderTrack>
                    <SliderThumb />
                  </Slider>
                  <Flex justify="space-between" fontSize="xs" color="gray.500">
                    <Text>-5%</Text>
                    <Text>+5%</Text>
                  </Flex>
                </>
              )}
            </FormControl>
          )}

          {showTriggerPrice && (
            <FormControl mb={3}>
              <FormLabel>Trigger Price</FormLabel>
              <Input
                type="number"
                value={triggerPrice}
                onChange={(e) => setTriggerPrice(e.target.value)}
              />
            </FormControl>
          )}

          <FormControl mb={3}>
            <FormLabel>Quantity</FormLabel>
            <Input
              type="number"
              value={quantity}
              onChange={(e) => {
                setQuantity(e.target.value);
                setQuantityPct(0);
              }}
            />
            {availableBalance && currentPrice && (
              <>
                <Slider
                  mt={1}
                  min={0}
                  max={100}
                  step={1}
                  value={quantityPct}
                  onChange={handleQuantityPctChange}
                  size="sm"
                >
                  <SliderTrack>
                    <SliderFilledTrack />
                  </SliderTrack>
                  <SliderThumb />
                </Slider>
                <Flex justify="space-between" fontSize="xs" color="gray.500">
                  <Text>0%</Text>
                  <Text>50%</Text>
                  <Text>100%</Text>
                </Flex>
              </>
            )}
          </FormControl>

          <HStack mb={3}>
            <FormControl>
              <FormLabel>Take Profit</FormLabel>
              <Input
                type="number"
                placeholder="Optional"
                value={takeProfit}
                onChange={(e) => setTakeProfit(e.target.value)}
              />
            </FormControl>
            <FormControl>
              <FormLabel>Stop Loss</FormLabel>
              <Input
                type="number"
                placeholder="Optional"
                value={stopLoss}
                onChange={(e) => setStopLoss(e.target.value)}
              />
            </FormControl>
          </HStack>
        </ModalBody>
        <ModalFooter>
          <HStack>
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button
              colorScheme="blue"
              onClick={handleSubmit}
              isLoading={loading}
              isDisabled={!quantity}
            >
              Place Order
            </Button>
          </HStack>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
