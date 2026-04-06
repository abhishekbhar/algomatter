"use client";
import { useState, useCallback } from "react";
import { Box, Flex } from "@chakra-ui/react";
import { Watchlist } from "@/components/trade/Watchlist";
import { TradingChart } from "@/components/trade/TradingChart";
import { OrderForm } from "@/components/trade/OrderForm";
import { TradeHistory } from "@/components/trade/TradeHistory";
import { type TickerData } from "@/lib/hooks/useBinanceWebSocket";

export default function TradePage() {
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [tickerMap, setTickerMap] = useState<Record<string, TickerData>>({});

  const currentTicker = tickerMap[symbol];

  const handleSymbolSelect = useCallback((s: string) => {
    setSymbol(s);
  }, []);

  // Called by Watchlist whenever any ticker updates
  const handleTickerUpdate = useCallback((data: TickerData) => {
    setTickerMap((prev) => ({ ...prev, [data.symbol]: data }));
  }, []);

  return (
    <Box h="calc(100vh - 64px)" display="flex" flexDirection="column">
      {/* Main 3-column layout */}
      <Flex flex="1" minH={0}>
        {/* Left: Watchlist */}
        <Watchlist
          activeSymbol={symbol}
          onSymbolSelect={handleSymbolSelect}
          onTickerUpdate={handleTickerUpdate}
        />

        {/* Center: Chart */}
        <TradingChart
          symbol={symbol}
          price={currentTicker?.price}
          change24h={currentTicker?.change24h}
        />

        {/* Right: Order Form */}
        <OrderForm
          symbol={symbol}
          currentPrice={currentTicker?.price ?? null}
        />
      </Flex>

      {/* Bottom: Trade History */}
      <TradeHistory />
    </Box>
  );
}
