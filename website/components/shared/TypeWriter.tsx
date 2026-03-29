"use client";

import { useEffect, useState, useRef } from "react";
import { useInView } from "framer-motion";

interface TypeWriterProps {
  code: string;
  speed?: number;
  className?: string;
}

export function TypeWriter({ code, speed = 30, className = "" }: TypeWriterProps) {
  const ref = useRef<HTMLPreElement>(null);
  const isInView = useInView(ref, { once: true });
  const [displayed, setDisplayed] = useState("");

  useEffect(() => {
    if (!isInView) return;
    let i = 0;
    const timer = setInterval(() => {
      if (i < code.length) {
        setDisplayed(code.slice(0, i + 1));
        i++;
      } else {
        clearInterval(timer);
      }
    }, speed);
    return () => clearInterval(timer);
  }, [isInView, code, speed]);

  return (
    <pre
      ref={ref}
      className={`font-mono text-sm leading-relaxed ${className}`}
    >
      <code>{displayed}<span className="animate-pulse">|</span></code>
    </pre>
  );
}
