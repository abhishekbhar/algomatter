"use client";
import { useRef, useEffect } from "react";
import { createChart, HistogramSeries, IChartApi, HistogramData, Time } from "lightweight-charts";
import { useColorModeValue } from "@chakra-ui/react";

interface DrawdownChartProps { data: Array<{ time: string; value: number }>; height?: number; }

export function DrawdownChart({ data, height = 300 }: DrawdownChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const bgColor = useColorModeValue("#ffffff", "#1a202c");
  const textColor = useColorModeValue("#2d3748", "#e2e8f0");

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth, height,
      layout: { background: { color: bgColor }, textColor },
      grid: { vertLines: { visible: false }, horzLines: { color: "#e2e8f020" } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    });
    chartRef.current = chart;
    const series = chart.addSeries(HistogramSeries, {
      color: "#e53e3e",
    });
    const sorted = [...data].sort((a, b) => a.time.localeCompare(b.time));
    series.setData(sorted as HistogramData<Time>[]);
    chart.timeScale().fitContent();
    const handleResize = () => { if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth }); };
    window.addEventListener("resize", handleResize);
    return () => { window.removeEventListener("resize", handleResize); chart.remove(); };
  }, [data, height, bgColor, textColor]);

  return <div ref={containerRef} />;
}
