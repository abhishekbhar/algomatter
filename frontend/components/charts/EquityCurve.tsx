"use client";
import { memo, useRef, useEffect } from "react";
import { createChart, AreaSeries, IChartApi, AreaData, Time } from "lightweight-charts";
import { useColorModeValue } from "@chakra-ui/react";

interface EquityCurveProps { data: Array<{ time: string | number; value: number }>; height?: number; }

export const EquityCurve = memo(function EquityCurve({ data, height = 300 }: EquityCurveProps) {
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
    const series = chart.addSeries(AreaSeries, {
      lineColor: "#3182ce", topColor: "rgba(49, 130, 206, 0.4)",
      bottomColor: "rgba(49, 130, 206, 0.0)", lineWidth: 2,
    });
    const sorted = [...data].sort((a, b) => {
      if (typeof a.time === "number" && typeof b.time === "number") return a.time - b.time;
      return String(a.time).localeCompare(String(b.time));
    });
    series.setData(sorted as AreaData<Time>[]);
    chart.timeScale().fitContent();
    const handleResize = () => { if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth }); };
    window.addEventListener("resize", handleResize);
    return () => { window.removeEventListener("resize", handleResize); chart.remove(); };
  }, [data, height, bgColor, textColor]);

  return <div ref={containerRef} />;
});
