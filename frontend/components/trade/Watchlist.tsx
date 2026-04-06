"use client";
import { useRef, useState, useCallback, useReducer, useMemo } from "react";
import { Box, Flex, Text, Input, VStack, useColorModeValue } from "@chakra-ui/react";
import {
  useBinanceTickerStream,
  type TickerData,
} from "@/lib/hooks/useBinanceWebSocket";

const DEFAULT_SYMBOLS = [
  "BTCUSDT",
  "ETHUSDT",
  "SOLUSDT",
  "XRPUSDT",
  "BNBUSDT",
  "ADAUSDT",
  "DOGEUSDT",
];

interface WatchlistProps {
  activeSymbol: string;
  onSymbolSelect: (symbol: string) => void;
  onTickerUpdate?: (data: TickerData) => void;
}

export function Watchlist({
  activeSymbol,
  onSymbolSelect,
  onTickerUpdate,
}: WatchlistProps) {
  const [search, setSearch] = useState("");
  const [, forceUpdate] = useReducer((x: number) => x + 1, 0);
  const tickerMapRef = useRef<Map<string, TickerData>>(new Map());
  const onTickerUpdateRef = useRef(onTickerUpdate);
  onTickerUpdateRef.current = onTickerUpdate;

  const bg = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");
  const inputBg = useColorModeValue("gray.50", "gray.700");
  const activeBg = useColorModeValue("blue.50", "rgba(59,130,246,0.1)");
  const hoverBg = useColorModeValue("gray.50", "rgba(255,255,255,0.05)");
  const symbolColor = useColorModeValue("gray.800", "white");
  const subColor = useColorModeValue("gray.500", "gray.500");
  const priceColor = useColorModeValue("gray.700", "gray.300");

  const handleTicker = useCallback((data: TickerData) => {
    tickerMapRef.current.set(data.symbol, data);
    onTickerUpdateRef.current?.(data);
    forceUpdate();
  }, []);

  const { connected } = useBinanceTickerStream(DEFAULT_SYMBOLS, handleTicker);

  const filteredSymbols = useMemo(() => {
    if (!search.trim()) return DEFAULT_SYMBOLS;
    const q = search.toUpperCase();
    return DEFAULT_SYMBOLS.filter((s) => s.includes(q));
  }, [search]);

  return (
    <Box
      w="180px"
      bg={bg}
      borderRight="1px"
      borderColor={borderColor}
      h="100%"
      display="flex"
      flexDirection="column"
      flexShrink={0}
    >
      {/* Search */}
      <Box p={2} borderBottom="1px" borderColor={borderColor}>
        <Input
          placeholder="Search..."
          size="xs"
          bg={inputBg}
          border="none"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </Box>

      {/* Disconnected warning */}
      {!connected && (
        <Box px={2} py={1} bg="red.100" _dark={{ bg: "red.900" }}>
          <Text fontSize="2xs" color="red.500" _dark={{ color: "red.300" }} textAlign="center">
            Disconnected
          </Text>
        </Box>
      )}

      {/* Symbol list */}
      <VStack spacing={0} align="stretch" overflowY="auto" flex="1">
        {filteredSymbols.map((sym) => {
          const ticker = tickerMapRef.current.get(sym);
          const isActive = sym === activeSymbol;
          const changeColor =
            ticker && ticker.change24h >= 0 ? "green.400" : "red.400";

          return (
            <Flex
              key={sym}
              px={2}
              py={2}
              cursor="pointer"
              bg={isActive ? activeBg : "transparent"}
              borderLeft={isActive ? "3px solid" : "3px solid transparent"}
              borderLeftColor={isActive ? "blue.500" : "transparent"}
              _hover={{ bg: hoverBg }}
              onClick={() => onSymbolSelect(sym)}
              direction="column"
              gap={0}
            >
              <Flex justify="space-between" align="center">
                <Text color={symbolColor} fontSize="xs" fontWeight="semibold">
                  {sym.replace("USDT", "")}
                </Text>
                <Text color={changeColor} fontSize="2xs" fontWeight="medium">
                  {ticker
                    ? `${ticker.change24h >= 0 ? "+" : ""}${ticker.change24h.toFixed(2)}%`
                    : "—"}
                </Text>
              </Flex>
              <Flex justify="space-between" align="center">
                <Text color={subColor} fontSize="2xs">
                  {sym}
                </Text>
                <Text color={priceColor} fontSize="2xs">
                  {ticker
                    ? ticker.price.toLocaleString(undefined, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 8,
                      })
                    : "—"}
                </Text>
              </Flex>
            </Flex>
          );
        })}
      </VStack>
    </Box>
  );
}
