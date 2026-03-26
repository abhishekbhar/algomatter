"use client";
import { Badge } from "@chakra-ui/react";

const VARIANT_MAP = { success: "green", error: "red", warning: "yellow", info: "blue", neutral: "gray" } as const;

interface StatusBadgeProps { variant: keyof typeof VARIANT_MAP; text: string; }

export function StatusBadge({ variant, text }: StatusBadgeProps) {
  return <Badge colorScheme={VARIANT_MAP[variant]}>{text}</Badge>;
}
