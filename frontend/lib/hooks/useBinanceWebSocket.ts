import { useEffect, useRef, useState, useCallback } from "react";

export interface TickerData {
  symbol: string;
  price: number;
  change24h: number;
  volume: number;
}

export interface KlineData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  isClosed: boolean;
}

type TickerCallback = (ticker: TickerData) => void;
type KlineCallback = (kline: KlineData) => void;

const BINANCE_WS_URL = "wss://stream.binance.com:9443/stream";
const MAX_RECONNECT_DELAY = 30000;

export function useBinanceTickerStream(
  symbols: string[],
  onTicker: TickerCallback,
): { connected: boolean } {
  const [connected, setConnected] = useState(false);
  const callbackRef = useRef<TickerCallback>(onTicker);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    callbackRef.current = onTicker;
  }, [onTicker]);

  useEffect(() => {
    if (symbols.length === 0) return;

    const lowerSymbols = symbols.map((s) => s.toLowerCase());

    function connect() {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }

      const ws = new WebSocket(BINANCE_WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        reconnectAttemptRef.current = 0;
        const params = lowerSymbols.map((s) => `${s}@miniTicker`);
        ws.send(JSON.stringify({ method: "SUBSCRIBE", params, id: 1 }));
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.data && msg.data.e === "24hrMiniTicker") {
            const d = msg.data;
            callbackRef.current({
              symbol: d.s as string,
              price: parseFloat(d.c),
              change24h: parseFloat(d.P || "0"),
              volume: parseFloat(d.v),
            });
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        setConnected(false);
        scheduleReconnect();
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    function scheduleReconnect() {
      const delay = Math.min(
        1000 * Math.pow(2, reconnectAttemptRef.current),
        MAX_RECONNECT_DELAY,
      );
      reconnectAttemptRef.current += 1;
      reconnectTimerRef.current = setTimeout(connect, delay);
    }

    connect();

    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
      setConnected(false);
    };
  }, [symbols.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  return { connected };
}

export function useBinanceKlineStream(
  symbol: string | null,
  interval: string,
  onKline: KlineCallback,
): { connected: boolean } {
  const [connected, setConnected] = useState(false);
  const callbackRef = useRef<KlineCallback>(onKline);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    callbackRef.current = onKline;
  }, [onKline]);

  useEffect(() => {
    if (!symbol) return;

    const lowerSymbol = symbol.toLowerCase();

    function connect() {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }

      const ws = new WebSocket(BINANCE_WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        reconnectAttemptRef.current = 0;
        ws.send(
          JSON.stringify({
            method: "SUBSCRIBE",
            params: [`${lowerSymbol}@kline_${interval}`],
            id: 1,
          }),
        );
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.data && msg.data.e === "kline") {
            const k = msg.data.k;
            callbackRef.current({
              time: k.t as number,
              open: parseFloat(k.o),
              high: parseFloat(k.h),
              low: parseFloat(k.l),
              close: parseFloat(k.c),
              volume: parseFloat(k.v),
              isClosed: k.x as boolean,
            });
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        setConnected(false);
        scheduleReconnect();
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    function scheduleReconnect() {
      const delay = Math.min(
        1000 * Math.pow(2, reconnectAttemptRef.current),
        MAX_RECONNECT_DELAY,
      );
      reconnectAttemptRef.current += 1;
      reconnectTimerRef.current = setTimeout(connect, delay);
    }

    connect();

    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
      setConnected(false);
    };
  }, [symbol, interval]);

  return { connected };
}

export async function fetchBinanceKlines(
  symbol: string,
  interval: string,
  limit = 500,
): Promise<KlineData[]> {
  const url = `https://api.binance.com/api/v3/klines?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&limit=${limit}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Binance API error: ${res.status}`);
  const data: unknown[][] = await res.json();
  return data.map((k) => ({
    time: k[0] as number,
    open: parseFloat(k[1] as string),
    high: parseFloat(k[2] as string),
    low: parseFloat(k[3] as string),
    close: parseFloat(k[4] as string),
    volume: parseFloat(k[5] as string),
    isClosed: true,
  }));
}
