"use client";
import { Box, VStack, IconButton, Flex, Text, useColorModeValue } from "@chakra-ui/react";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  MdDashboard,
  MdShowChart,
  MdWebhook,
  MdAccountBalance,
  MdPlayArrow,
  MdHistory,
  MdAnalytics,
  MdSettings,
  MdCode,
  MdTrendingUp,
  MdChevronLeft,
  MdChevronRight,
  MdQueryStats,
} from "react-icons/md";
import { NavItem } from "./NavItem";

const NAV_ITEMS = [
  { icon: MdDashboard, label: "Dashboard", href: "/" },
  { icon: MdShowChart, label: "Webhook Strategies", href: "/strategies" },
  { icon: MdCode, label: "Hosted Strategies", href: "/strategies/hosted" },
  { icon: MdTrendingUp, label: "Live Trading", href: "/live-trading" },
  { icon: MdWebhook, label: "Webhooks", href: "/webhooks" },
  { icon: MdAccountBalance, label: "Brokers", href: "/brokers" },
  { icon: MdPlayArrow, label: "Paper Trading", href: "/paper-trading" },
  { icon: MdQueryStats, label: "Backtest Deployments", href: "/backtest-deployments" },
  { icon: MdHistory, label: "Backtesting", href: "/backtesting" },
  { icon: MdAnalytics, label: "Analytics", href: "/analytics" },
  { icon: MdSettings, label: "Settings", href: "/settings" },
];

export function Sidebar() {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const pathname = usePathname();
  const bg = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");
  return (
    <Box
      as="nav"
      w={isCollapsed ? "60px" : "220px"}
      minH="100vh"
      bg={bg}
      borderRight="1px"
      borderColor={borderColor}
      transition="width 0.2s"
      py={4}
    >
      <Flex
        justify={isCollapsed ? "center" : "space-between"}
        align="center"
        px={3}
        mb={6}
      >
        {!isCollapsed && (
          <Text fontSize="lg" fontWeight="bold">
            AlgoMatter
          </Text>
        )}
        <IconButton
          aria-label="Toggle sidebar"
          icon={isCollapsed ? <MdChevronRight /> : <MdChevronLeft />}
          size="sm"
          variant="ghost"
          onClick={() => setIsCollapsed(!isCollapsed)}
        />
      </Flex>
      <VStack spacing={1} align="stretch" px={2}>
        {NAV_ITEMS.map((item) => (
          <NavItem
            key={item.href}
            icon={item.icon}
            label={item.label}
            href={item.href}
            isActive={
              pathname === item.href ||
              (item.href !== "/" && pathname.startsWith(item.href) &&
                !NAV_ITEMS.some((other) => other.href !== item.href && other.href.startsWith(item.href) && pathname.startsWith(other.href)))
            }
            isCollapsed={isCollapsed}
          />
        ))}
      </VStack>
    </Box>
  );
}
