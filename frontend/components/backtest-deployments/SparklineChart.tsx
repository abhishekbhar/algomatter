"use client";

interface Point {
  timestamp: string;
  equity: number;
}

interface SparklineChartProps {
  data: Point[] | null | undefined;
  width?: number;
  height?: number;
}

export function SparklineChart({
  data,
  width = 200,
  height = 40,
}: SparklineChartProps) {
  const points = data && data.length > 1 ? data : null;

  if (!points) {
    const mid = height / 2;
    return (
      <svg width={width} height={height} aria-hidden="true">
        <line x1={0} y1={mid} x2={width} y2={mid} stroke="#4A5568" strokeWidth={1.5} />
      </svg>
    );
  }

  const equities = points.map((p) => p.equity);
  const min = Math.min(...equities);
  const max = Math.max(...equities);
  const range = max - min || 1;
  const pad = 2;

  const toX = (_: Point, i: number) =>
    pad + (i / (points.length - 1)) * (width - pad * 2);
  const toY = (p: Point) =>
    pad + ((max - p.equity) / range) * (height - pad * 2);

  const pathD = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${toX(p, i).toFixed(1)},${toY(p).toFixed(1)}`)
    .join(" ");

  const areaD =
    pathD +
    ` L${(pad + (width - pad * 2)).toFixed(1)},${height} L${pad},${height} Z`;

  const isPositive = equities[equities.length - 1] >= equities[0];
  const lineColor = isPositive ? "#48BB78" : "#FC8181";
  const fillColor = isPositive ? "rgba(72,187,120,0.15)" : "rgba(252,129,129,0.15)";

  return (
    <svg width={width} height={height} aria-hidden="true">
      <path d={areaD} fill={fillColor} stroke="none" />
      <path d={pathD} fill="none" stroke={lineColor} strokeWidth={1.5} strokeLinejoin="round" />
    </svg>
  );
}
