"use client";
import { useState } from "react";
import {
  Box, Button, Flex, FormControl, FormLabel, Input, Select,
  Slider, SliderTrack, SliderFilledTrack, SliderThumb,
  Text, useColorModeValue, useToast,
} from "@chakra-ui/react";
import { apiClient } from "@/lib/api/client";
import { useBrokers, useBrokerBalance, useBrokerQuote } from "@/lib/hooks/useApi";
import { getBrokerCaps } from "@/components/trade/BrokerCapabilities";

interface Props {
  symbol: string;
  currentPrice: number | null;
  onOrderPlaced?: () => void;
}

export function OrderForm({ symbol, currentPrice, onOrderPlaced }: Props) {
  const toast = useToast();
  const { data: brokerConnections } = useBrokers();
  const [selectedBrokerId, setSelectedBrokerId] = useState<string>("");
  const [productType, setProductType] = useState<"SPOT" | "FUTURES">("SPOT");
  const [action, setAction] = useState<"BUY" | "SELL">("BUY");
  const [orderType, setOrderType] = useState("MARKET");
  const [price, setPrice] = useState("");
  const [priceSliderPct, setPriceSliderPct] = useState(50);
  const [quantityPct, setQuantityPct] = useState(0);
  const [quantity, setQuantity] = useState("");
  const [takeProfit, setTakeProfit] = useState("");
  const [stopLoss, setStopLoss] = useState("");
  const [triggerPrice, setTriggerPrice] = useState("");
  const [leverage, setLeverage] = useState(1);
  const [positionModel, setPositionModel] = useState("cross");
  const [tradeMode, setTradeMode] = useState<"open" | "close">("open");
  const [loading, setLoading] = useState(false);

  const { data: balance } = useBrokerBalance(selectedBrokerId || null, productType);
  const { data: brokerQuote } = useBrokerQuote(selectedBrokerId || null, symbol);
  const selectedBroker = brokerConnections?.find((b) => String(b.id) === selectedBrokerId);
  const caps = selectedBroker ? getBrokerCaps(selectedBroker.broker_type) : null;

  // Use broker's own price when available, fall back to Binance ticker price
  const effectiveCurrentPrice = brokerQuote?.last_price ?? currentPrice;

  const bg = useColorModeValue("white", "gray.800");
  const inputBg = useColorModeValue("gray.50", "gray.700");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  const handlePriceSliderChange = (val: number) => {
    setPriceSliderPct(val);
    if (effectiveCurrentPrice) {
      const min = effectiveCurrentPrice * 0.95;
      const max = effectiveCurrentPrice * 1.05;
      setPrice((min + (max - min) * (val / 100)).toFixed(2));
    }
  };

  const handleQuantityPctChange = (val: number) => {
    setQuantityPct(val);
    if (balance && effectiveCurrentPrice) {
      const ep = price ? parseFloat(price) : effectiveCurrentPrice;
      if (ep > 0) {
        const maxQty = balance.available / ep;
        setQuantity((maxQty * (val / 100)).toFixed(6));
      }
    }
  };

  const handleSubmit = async () => {
    if (!selectedBrokerId || !quantity) return;
    setLoading(true);
    try {
      const body: Record<string, unknown> = {
        broker_connection_id: selectedBrokerId,
        symbol,
        exchange: selectedBroker?.broker_type === "exchange1" ? "EXCHANGE1" : "BINANCE",
        product_type: productType,
        action,
        quantity: parseFloat(quantity),
        order_type: orderType.toLowerCase(),
        price: price ? parseFloat(price) : null,
        trigger_price: triggerPrice ? parseFloat(triggerPrice) : null,
        take_profit: takeProfit ? parseFloat(takeProfit) : null,
        stop_loss: stopLoss ? parseFloat(stopLoss) : null,
      };
      if (productType === "FUTURES") {
        body.leverage = leverage;
        body.position_model = positionModel;
        if (tradeMode === "open") {
          // Open: BUY=long (no side), SELL=short (needs position_side)
          if (action === "SELL" && caps?.shortFutures) {
            body.position_side = "short";
          }
        } else {
          // Close: BUY closes short, SELL closes long (default side)
          if (action === "BUY" && caps?.shortFutures) {
            body.position_side = "short";
          }
        }
      }
      await apiClient("/api/v1/trades/manual", { method: "POST", body });
      toast({ title: "Order placed", status: "success", duration: 2000 });
      onOrderPlaced?.();
      setQuantity(""); setQuantityPct(0); setPrice(""); setPriceSliderPct(50);
    } catch {
      toast({ title: "Failed to place order", status: "error", duration: 3000 });
    } finally {
      setLoading(false);
    }
  };

  const isFuturesDisabled = caps && !caps.futures;
  const isShortDisabled = productType === "FUTURES" && caps && !caps.shortFutures;
  const showTriggerPrice = orderType === "SL" || orderType === "SL-M";
  const isLimitLike = orderType === "LIMIT" || orderType === "SL";

  const buyLabel = productType !== "FUTURES" ? "Buy"
    : tradeMode === "open" ? "Long"
    : "Close Short";
  const sellLabel = productType !== "FUTURES" ? "Sell"
    : tradeMode === "open" ? "Short"
    : "Close Long";
  const actionLabel = action === "BUY" ? buyLabel : sellLabel;
  const submitLabel = productType === "FUTURES"
    ? `${actionLabel} ${symbol}${tradeMode === "open" && leverage > 1 ? ` ${leverage}x` : ""}`
    : `${actionLabel} ${symbol}`;
  const balancePrefix = caps?.currencySymbol || "";

  return (
    <Box w="280px" bg={bg} borderLeft="1px" borderColor={borderColor} overflowY="auto" flexShrink={0} p={3}>
      <Flex bg={inputBg} borderRadius="md" p="2px" mb={3}>
        <Button flex={1} size="sm" variant={productType === "SPOT" ? "solid" : "ghost"} colorScheme={productType === "SPOT" ? "green" : "gray"} onClick={() => setProductType("SPOT")}>Spot</Button>
        <Button flex={1} size="sm" variant={productType === "FUTURES" ? "solid" : "ghost"} colorScheme={productType === "FUTURES" ? "yellow" : "gray"} onClick={() => setProductType("FUTURES")} isDisabled={!!isFuturesDisabled}>Futures</Button>
      </Flex>

      <FormControl mb={3}>
        <FormLabel fontSize="xs" color="gray.500" textTransform="uppercase">Broker</FormLabel>
        <Select size="sm" bg={inputBg} value={selectedBrokerId} onChange={(e) => setSelectedBrokerId(e.target.value)} placeholder="Select broker...">
          {(brokerConnections ?? []).map((b) => (<option key={String(b.id)} value={String(b.id)}>{b.label} — {b.broker_type}{b.is_active ? "" : " (Inactive)"}</option>))}
        </Select>
      </FormControl>

      {/* Show broker price when available */}
      {brokerQuote && (
        <Flex justify="space-between" mb={3} px={1} fontSize="xs">
          <Text color="gray.500">Broker Price</Text>
          <Text fontWeight="semibold">{balancePrefix}{brokerQuote.last_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {caps?.currency ?? "USDT"}</Text>
        </Flex>
      )}

      {productType === "FUTURES" && (
        <Flex bg={inputBg} borderRadius="md" p="2px" mb={2}>
          <Button flex={1} size="xs" variant={tradeMode === "open" ? "solid" : "ghost"} colorScheme={tradeMode === "open" ? "blue" : "gray"} onClick={() => setTradeMode("open")}>Open</Button>
          <Button flex={1} size="xs" variant={tradeMode === "close" ? "solid" : "ghost"} colorScheme={tradeMode === "close" ? "orange" : "gray"} onClick={() => setTradeMode("close")}>Close</Button>
        </Flex>
      )}

      <Flex gap={2} mb={3}>
        <Button flex={1} size="sm" colorScheme={action === "BUY" ? "green" : "gray"} variant={action === "BUY" ? "solid" : "outline"} onClick={() => setAction("BUY")}>{buyLabel}</Button>
        <Button flex={1} size="sm" colorScheme={action === "SELL" ? "red" : "gray"} variant={action === "SELL" ? "solid" : "outline"} onClick={() => setAction("SELL")} isDisabled={productType === "FUTURES" && tradeMode === "open" ? !!isShortDisabled : false}>{sellLabel}</Button>
      </Flex>

      {productType === "FUTURES" && (
        <Flex gap={2} mb={3}>
          <FormControl flex={1}>
            <FormLabel fontSize="xs" color="gray.500">MARGIN</FormLabel>
            <Flex gap={1}>
              <Button size="xs" variant={positionModel === "isolated" ? "solid" : "ghost"} colorScheme="yellow" onClick={() => setPositionModel("isolated")}>Isolated</Button>
              <Button size="xs" variant={positionModel === "cross" ? "solid" : "ghost"} colorScheme="yellow" onClick={() => setPositionModel("cross")}>Cross</Button>
            </Flex>
          </FormControl>
          <FormControl flex={1}>
            <FormLabel fontSize="xs" color="gray.500">LEVERAGE</FormLabel>
            <Select size="sm" bg={inputBg} value={leverage} onChange={(e) => setLeverage(Number(e.target.value))}>
              {[1, 2, 3, 5, 10, 20, 50, 75, 100, 125].map((l) => (<option key={l} value={l}>{l}x</option>))}
            </Select>
          </FormControl>
        </Flex>
      )}

      <FormControl mb={3}>
        <FormLabel fontSize="xs" color="gray.500" textTransform="uppercase">Order Type</FormLabel>
        <Flex gap={1} flexWrap="wrap">
          {["MARKET", "LIMIT", "SL-M", "SL"].map((ot) => {
            const disabled = caps && !caps.orderTypes.includes(ot);
            return (<Button key={ot} size="xs" variant={orderType === ot ? "solid" : "ghost"} colorScheme={orderType === ot ? "blue" : "gray"} onClick={() => setOrderType(ot)} isDisabled={!!disabled}>{ot === "SL-M" ? "Stop" : ot === "SL" ? "Stop Limit" : ot.charAt(0) + ot.slice(1).toLowerCase()}</Button>);
          })}
        </Flex>
      </FormControl>

      {isLimitLike && (
        <FormControl mb={3}>
          <FormLabel fontSize="xs" color="gray.500">PRICE</FormLabel>
          <Input size="sm" type="number" bg={inputBg} value={price} onChange={(e) => setPrice(e.target.value)} placeholder={effectiveCurrentPrice?.toFixed(2) ?? ""} />
          <Slider mt={1} min={0} max={100} value={priceSliderPct} onChange={handlePriceSliderChange} size="sm"><SliderTrack><SliderFilledTrack /></SliderTrack><SliderThumb /></Slider>
          <Flex justify="space-between" fontSize="2xs" color="gray.500"><Text>-5%</Text><Text>+5%</Text></Flex>
        </FormControl>
      )}

      {showTriggerPrice && (
        <FormControl mb={3}>
          <FormLabel fontSize="xs" color="gray.500">TRIGGER PRICE</FormLabel>
          <Input size="sm" type="number" bg={inputBg} value={triggerPrice} onChange={(e) => setTriggerPrice(e.target.value)} />
        </FormControl>
      )}

      <FormControl mb={3}>
        <FormLabel fontSize="xs" color="gray.500">QUANTITY</FormLabel>
        <Input size="sm" type="number" bg={inputBg} value={quantity} onChange={(e) => { setQuantity(e.target.value); setQuantityPct(0); }} />
        <Slider mt={1} min={0} max={100} step={1} value={quantityPct} onChange={handleQuantityPctChange} size="sm"><SliderTrack><SliderFilledTrack /></SliderTrack><SliderThumb /></Slider>
        <Flex justify="space-between" fontSize="2xs" color="gray.500"><Text>0%</Text><Text>25%</Text><Text>50%</Text><Text>75%</Text><Text>100%</Text></Flex>
      </FormControl>

      <Flex gap={2} mb={3}>
        <FormControl flex={1}><FormLabel fontSize="xs" color="gray.500">TAKE PROFIT</FormLabel><Input size="sm" type="number" bg={inputBg} placeholder="Optional" value={takeProfit} onChange={(e) => setTakeProfit(e.target.value)} /></FormControl>
        <FormControl flex={1}><FormLabel fontSize="xs" color="gray.500">STOP LOSS</FormLabel><Input size="sm" type="number" bg={inputBg} placeholder="Optional" value={stopLoss} onChange={(e) => setStopLoss(e.target.value)} /></FormControl>
      </Flex>

      {productType === "FUTURES" && effectiveCurrentPrice && quantity ? (
        <Box borderTop="1px" borderColor={borderColor} py={2} mb={2} fontSize="xs">
          <Flex justify="space-between"><Text color="gray.500">Required Margin</Text><Text color="yellow.400">{balancePrefix}{((parseFloat(quantity) * (caps?.futuresContractSize ?? 1) * (parseFloat(price) || effectiveCurrentPrice)) / leverage).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {caps?.currency ?? "USDT"}</Text></Flex>
        </Box>
      ) : null}

      {effectiveCurrentPrice && quantity ? (
        <Flex justify="space-between" borderTop="1px" borderColor={borderColor} py={2} mb={3} fontSize="xs">
          <Text color="gray.500">Total</Text><Text fontWeight="semibold">{balancePrefix}{(parseFloat(quantity) * (productType === "FUTURES" ? (caps?.futuresContractSize ?? 1) : 1) * (parseFloat(price) || effectiveCurrentPrice)).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {caps?.currency ?? "USDT"}</Text>
        </Flex>
      ) : null}

      <Button w="100%" colorScheme={action === "BUY" ? "green" : "red"} onClick={handleSubmit} isLoading={loading} isDisabled={!selectedBrokerId || !quantity}>{submitLabel}</Button>
      {balance && (<Text textAlign="center" mt={2} fontSize="xs" color="gray.500">Available: {balancePrefix}{balance.available.toLocaleString()} {caps?.currency ?? "USDT"}</Text>)}
    </Box>
  );
}
