"use client";
import { ChakraProvider, defaultSystem } from "@chakra-ui/react";
import { AuthProvider } from "@/lib/hooks/useAuth";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ChakraProvider value={defaultSystem}>
      <AuthProvider>{children}</AuthProvider>
    </ChakraProvider>
  );
}
