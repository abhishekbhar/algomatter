"use client";

import { motion, useInView } from "framer-motion";
import { useRef } from "react";

export function EquityCurve({ className = "" }: { className?: string }) {
  const ref = useRef<SVGSVGElement>(null);
  const isInView = useInView(ref, { once: true });

  const curvePath =
    "M0,120 Q50,110 100,100 T200,80 T300,60 T400,45 T500,30 T600,15";
  const areaPath = `${curvePath} L600,160 L0,160 Z`;

  return (
    <svg
      ref={ref}
      viewBox="0 0 600 160"
      className={className}
      preserveAspectRatio="none"
    >
      <defs>
        <linearGradient id="curveGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#6366f1" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
        </linearGradient>
      </defs>
      <motion.path
        d={areaPath}
        fill="url(#curveGrad)"
        initial={{ opacity: 0 }}
        animate={isInView ? { opacity: 1 } : {}}
        transition={{ duration: 1, delay: 0.5 }}
      />
      <motion.path
        d={curvePath}
        fill="none"
        stroke="#6366f1"
        strokeWidth="2"
        initial={{ pathLength: 0 }}
        animate={isInView ? { pathLength: 1 } : {}}
        transition={{ duration: 2, ease: "easeInOut" }}
      />
    </svg>
  );
}
