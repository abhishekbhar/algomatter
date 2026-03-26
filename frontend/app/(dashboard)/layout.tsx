"use client";
import { Flex, Box, Spinner, Center } from "@chakra-ui/react";
import { useAuth } from "@/lib/hooks/useAuth";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) router.push("/login");
  }, [isLoading, user, router]);

  if (isLoading)
    return (
      <Center h="100vh">
        <Spinner size="xl" />
      </Center>
    );
  if (!user) return null;

  return (
    <Flex minH="100vh">
      <Sidebar />
      <Box flex={1}>
        <TopBar />
        <Box p={6}>{children}</Box>
      </Box>
    </Flex>
  );
}
