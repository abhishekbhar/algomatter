"use client";
import { useEffect, useRef } from "react";
import { Box, useColorMode } from "@chakra-ui/react";

interface TradingChartProps {
  symbol: string;
  price?: number;
  change24h?: number;
}

export function TradingChart({ symbol }: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { colorMode } = useColorMode();

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    container.innerHTML = "";

    const widgetDiv = document.createElement("div");
    widgetDiv.className = "tradingview-widget-container__widget";
    widgetDiv.style.height = "100%";
    widgetDiv.style.width = "100%";
    container.appendChild(widgetDiv);

    const script = document.createElement("script");
    script.src =
      "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.type = "text/javascript";
    script.async = true;
    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol: `BINANCE:${symbol}`,
      interval: "15",
      timezone: "Etc/UTC",
      theme: colorMode === "dark" ? "dark" : "light",
      style: "1",
      locale: "en",
      allow_symbol_change: true,
      support_host: "https://www.tradingview.com",
      hide_top_toolbar: false,
      hide_legend: false,
      hide_side_toolbar: false,
      save_image: true,
      calendar: false,
      withdateranges: true,
    });
    container.appendChild(script);

    return () => {
      container.innerHTML = "";
    };
  }, [symbol, colorMode]);

  return (
    <Box
      ref={containerRef}
      className="tradingview-widget-container"
      overflow="hidden"
      h="100%"
      flex="1"
      minW={0}
    />
  );
}
