"use client";
import { Flex, Box, Spinner, Center } from "@chakra-ui/react";
import { useAuth } from "@/lib/hooks/useAuth";
import { useFeatureFlags } from "@/lib/contexts/FeatureFlagsContext";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoading: authLoading } = useAuth();
  const { isLoading: flagsLoading } = useFeatureFlags();
  const router = useRouter();

  useEffect(() => {
    if (!authLoading && !user) router.push("/login");
  }, [authLoading, user, router]);

  if (authLoading || flagsLoading)
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
