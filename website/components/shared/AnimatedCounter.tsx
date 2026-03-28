"use client";

import { useEffect, useRef, useState } from "react";
import { useInView } from "framer-motion";

interface AnimatedCounterProps {
  target: number;
  prefix?: string;
  suffix?: string;
  duration?: number;
}

function getDecimalPlaces(n: number): number {
  const s = n.toString();
  const dot = s.indexOf(".");
  return dot === -1 ? 0 : s.length - dot - 1;
}

export function AnimatedCounter({
  target,
  prefix = "",
  suffix = "",
  duration = 2,
}: AnimatedCounterProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const isInView = useInView(ref, { once: true });
  const [count, setCount] = useState(0);
  const decimals = getDecimalPlaces(target);

  useEffect(() => {
    if (!isInView) return;
    let start = 0;
    const step = target / (duration * 60);
    const timer = setInterval(() => {
      start += step;
      if (start >= target) {
        setCount(target);
        clearInterval(timer);
      } else {
        setCount(
          decimals > 0
            ? parseFloat(start.toFixed(decimals))
            : Math.floor(start)
        );
      }
    }, 1000 / 60);
    return () => clearInterval(timer);
  }, [isInView, target, duration, decimals]);

  const display = decimals > 0
    ? count.toFixed(decimals)
    : count.toLocaleString();

  return (
    <span ref={ref} className="tabular-nums">
      {prefix}
      {display}
      {suffix}
    </span>
  );
}
