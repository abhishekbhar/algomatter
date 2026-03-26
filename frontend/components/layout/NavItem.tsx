"use client";
import { Flex, Text, Icon, useColorModeValue } from "@chakra-ui/react";
import Link from "next/link";
import { IconType } from "react-icons";

interface NavItemProps {
  icon: IconType;
  label: string;
  href: string;
  isActive: boolean;
  isCollapsed: boolean;
}

export function NavItem({ icon, label, href, isActive, isCollapsed }: NavItemProps) {
  const activeBg = useColorModeValue("blue.50", "blue.900");
  const activeColor = useColorModeValue("blue.600", "blue.200");
  const hoverBg = useColorModeValue("gray.100", "gray.700");
  return (
    <Link href={href} style={{ textDecoration: "none" }}>
      <Flex
        align="center"
        px={3}
        py={2}
        borderRadius="md"
        bg={isActive ? activeBg : "transparent"}
        color={isActive ? activeColor : "inherit"}
        _hover={{ bg: isActive ? activeBg : hoverBg }}
        gap={3}
      >
        <Icon as={icon} boxSize={5} />
        {!isCollapsed && (
          <Text fontSize="sm" fontWeight={isActive ? "semibold" : "normal"}>
            {label}
          </Text>
        )}
      </Flex>
    </Link>
  );
}
