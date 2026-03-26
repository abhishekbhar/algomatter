"use client";
import {
  Flex,
  IconButton,
  useColorMode,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  Avatar,
  Text,
} from "@chakra-ui/react";
import { MdLightMode, MdDarkMode } from "react-icons/md";
import { useAuth } from "@/lib/hooks/useAuth";

export function TopBar() {
  const { colorMode, toggleColorMode } = useColorMode();
  const { user, logout } = useAuth();
  return (
    <Flex
      as="header"
      h="56px"
      px={6}
      align="center"
      justify="flex-end"
      gap={4}
      borderBottom="1px"
      borderColor="gray.200"
    >
      <IconButton
        aria-label="Toggle theme"
        icon={colorMode === "light" ? <MdDarkMode /> : <MdLightMode />}
        variant="ghost"
        onClick={toggleColorMode}
      />
      <Menu>
        <MenuButton>
          <Avatar size="sm" name={user?.email} />
        </MenuButton>
        <MenuList>
          <MenuItem isDisabled>
            <Text fontSize="sm" color="gray.500">
              {user?.email}
            </Text>
          </MenuItem>
          <MenuItem onClick={logout}>Logout</MenuItem>
        </MenuList>
      </Menu>
    </Flex>
  );
}
