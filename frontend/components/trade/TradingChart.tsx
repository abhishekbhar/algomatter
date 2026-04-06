"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { Box, Flex, Text, Button, Spinner, HStack } from "@chakra-ui/react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  type IChartApi,
  type ISeriesApi,
  ColorType,
} from "lightweight-charts";
import {
  fetchBinanceKlines,
  useBinanceKlineStream,
  type KlineData,
} from "@/lib/hooks/useBinanceWebSocket";

const INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d"] as const;
type Interval = (typeof INTERVALS)[number];

interface TradingChartProps {
  symbol: string;
  price?: number;
  change24h?: number;
}

function klineToCandle(k: KlineData) {
  return {
    time: (k.time / 1000) as import("lightweight-charts").UTCTimestamp,
    open: k.open,
    high: k.high,
    low: k.low,
    close: k.close,
  };
}

function klineToVolume(k: KlineData) {
  return {
    time: (k.time / 1000) as import("lightweight-charts").UTCTimestamp,
    value: k.volume,
    color: k.close >= k.open ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)",
  };
}

export function TradingChart({ symbol, price, change24h }: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  const [interval, setInterval] = useState<Interval>("15m");
  const [loading, setLoading] = useState(true);

  // Create chart once on mount
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0f1118" },
        textColor: "#888",
      },
      grid: {
        vertLines: { color: "#1c1f2e" },
        horzLines: { color: "#1c1f2e" },
      },
      crosshair: {
        vertLine: { color: "#555", width: 1, style: 3 },
        horzLine: { color: "#555", width: 1, style: 3 },
      },
      timeScale: {
        borderColor: "#1c1f2e",
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: "#1c1f2e",
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });

    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    // ResizeObserver for responsive sizing
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        chart.applyOptions({ width, height });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
    };
  }, []);

  // Load historical data when symbol or interval changes
  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const klines = await fetchBinanceKlines(symbol, interval, 500);
        if (cancelled) return;

        const candles = klines.map(klineToCandle);
        const volumes = klines.map(klineToVolume);

        candleSeriesRef.current?.setData(candles);
        volumeSeriesRef.current?.setData(volumes);
        chartRef.current?.timeScale().fitContent();
      } catch (err) {
        console.error("Failed to fetch klines:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [symbol, interval]);

  // Real-time kline stream
  const handleKline = useCallback((kline: KlineData) => {
    const candle = klineToCandle(kline);
    const vol = klineToVolume(kline);
    candleSeriesRef.current?.update(candle);
    volumeSeriesRef.current?.update(vol);
  }, []);

  useBinanceKlineStream(symbol, interval, handleKline);

  const priceColor =
    change24h !== undefined && change24h >= 0 ? "#22c55e" : "#ef4444";

  return (
    <Box
      bg="#0f1118"
      borderRadius="md"
      overflow="hidden"
      h="100%"
      flex="1"
      minW={0}
      display="flex"
      flexDirection="column"
    >
      {/* Toolbar */}
      <Flex
        px={3}
        py={2}
        align="center"
        gap={3}
        borderBottom="1px solid #1c1f2e"
        flexShrink={0}
      >
        <Text color="white" fontWeight="bold" fontSize="sm">
          {symbol}
        </Text>

        {price !== undefined && (
          <Text color={priceColor} fontWeight="semibold" fontSize="sm">
            {price.toLocaleString(undefined, {
              minimumFractionDigits: 2,
              maximumFractionDigits: 8,
            })}
          </Text>
        )}

        {change24h !== undefined && (
          <Text color={priceColor} fontSize="xs">
            {change24h >= 0 ? "+" : ""}
            {change24h.toFixed(2)}%
          </Text>
        )}

        <HStack spacing={1} ml="auto">
          {INTERVALS.map((iv) => (
            <Button
              key={iv}
              size="xs"
              variant={iv === interval ? "solid" : "ghost"}
              colorScheme={iv === interval ? "blue" : "gray"}
              color={iv === interval ? "white" : "#888"}
              onClick={() => setInterval(iv)}
              fontWeight="medium"
              minW="36px"
            >
              {iv}
            </Button>
          ))}
        </HStack>
      </Flex>

      {/* Chart container */}
      <Box ref={containerRef} flex="1" position="relative">
        {loading && (
          <Flex
            position="absolute"
            inset="0"
            align="center"
            justify="center"
            zIndex={10}
            bg="rgba(15,17,24,0.7)"
          >
            <Spinner color="blue.400" size="lg" />
          </Flex>
        )}
      </Box>
    </Box>
  );
}
