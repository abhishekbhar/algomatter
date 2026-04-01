"use client";
import { useRef, useEffect } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesMarkersPluginApi,
  type CandlestickData,
  type HistogramData,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import { useColorModeValue } from "@chakra-ui/react";
import type { OhlcvCandle, TradeMarker } from "@/lib/api/types";

interface CandlestickChartProps {
  data: OhlcvCandle[];
  trades?: TradeMarker[];
  height?: number;
}

function toUnix(iso: string): UTCTimestamp {
  return Math.floor(new Date(iso).getTime() / 1000) as UTCTimestamp;
}

export function CandlestickChart({ data, trades = [], height = 400 }: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const bgColor = useColorModeValue("#ffffff", "#1a202c");
  const textColor = useColorModeValue("#2d3748", "#e2e8f0");

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: { background: { color: bgColor }, textColor },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: "#e2e8f020" },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    });
    chartRef.current = chart;

    // Candlestick series
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#38a169",
      downColor: "#e53e3e",
      borderDownColor: "#e53e3e",
      borderUpColor: "#38a169",
      wickDownColor: "#e53e3e",
      wickUpColor: "#38a169",
    });

    const sorted = [...data].sort((a, b) => a.timestamp.localeCompare(b.timestamp));

    const candleData: CandlestickData<Time>[] = sorted.map((c) => ({
      time: toUnix(c.timestamp),
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));
    candleSeries.setData(candleData);

    // Volume series on separate scale
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    const volumeData: HistogramData<Time>[] = sorted.map((c) => ({
      time: toUnix(c.timestamp),
      value: c.volume,
      color: c.close >= c.open ? "rgba(56, 161, 105, 0.3)" : "rgba(229, 62, 62, 0.3)",
    }));
    volumeSeries.setData(volumeData);

    // Trade markers
    if (trades.length > 0) {
      const markerData: SeriesMarker<Time>[] = trades
        .sort((a, b) => a.time.localeCompare(b.time))
        .map((t) => ({
          time: toUnix(t.time) as Time,
          position: t.action === "BUY" ? "belowBar" as const : "aboveBar" as const,
          shape: t.action === "BUY" ? "arrowUp" as const : "arrowDown" as const,
          color: t.action === "BUY" ? "#38a169" : "#e53e3e",
          text: t.action,
          size: 1,
        }));
      markersRef.current = createSeriesMarkers(candleSeries, markerData);
    }

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      if (markersRef.current) {
        markersRef.current.detach();
        markersRef.current = null;
      }
      chart.remove();
    };
  }, [data, trades, height, bgColor, textColor]);

  return <div ref={containerRef} />;
}
