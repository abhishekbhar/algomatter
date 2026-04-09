"use client";
import { Badge } from "@chakra-ui/react";

interface OriginBadgeProps {
  origin: "webhook" | "deployment" | "exchange_direct";
}

const ORIGIN_CONFIG = {
  webhook: { colorScheme: "blue", label: "Webhook" },
  deployment: { colorScheme: "purple", label: "Deployment" },
  exchange_direct: { colorScheme: "orange", label: "Exchange Direct" },
} as const;

export function OriginBadge({ origin }: OriginBadgeProps) {
  const { colorScheme, label } = ORIGIN_CONFIG[origin];
  return (
    <Badge colorScheme={colorScheme} variant="subtle" fontSize="xs">
      {label}
    </Badge>
  );
}
