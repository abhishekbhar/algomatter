"use client";
import { Box, Flex, Button, ButtonGroup, Skeleton } from "@chakra-ui/react";
import { useState } from "react";

export type Timeframe = "1W" | "1M" | "3M" | "ALL";

interface ChartContainerProps {
  children: (timeframe: Timeframe) => React.ReactNode;
  isLoading?: boolean;
  height?: number;
  showTimeframes?: boolean;
}

export function ChartContainer({ children, isLoading, height = 300, showTimeframes = true }: ChartContainerProps) {
  const [timeframe, setTimeframe] = useState<Timeframe>("1M");
  if (isLoading) return <Skeleton height={`${height}px`} borderRadius="lg" />;
  return (
    <Box>
      {showTimeframes && (
        <Flex justify="flex-end" mb={2}>
          <ButtonGroup size="xs" variant="outline">
            {(["1W", "1M", "3M", "ALL"] as Timeframe[]).map((tf) => (
              <Button key={tf} onClick={() => setTimeframe(tf)}
                variant={timeframe === tf ? "solid" : "outline"}
                colorScheme={timeframe === tf ? "blue" : "gray"}>{tf}</Button>
            ))}
          </ButtonGroup>
        </Flex>
      )}
      <Box h={`${height}px`}>{children(timeframe)}</Box>
    </Box>
  );
}
