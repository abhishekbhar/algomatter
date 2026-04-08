"use client";
import { ChakraProvider, extendTheme } from "@chakra-ui/react";
import { AuthProvider } from "@/lib/hooks/useAuth";
import { FeatureFlagsProvider } from "@/lib/contexts/FeatureFlagsContext";

const theme = extendTheme({
  config: { initialColorMode: "light", useSystemColorMode: false },
  fonts: { heading: "var(--font-inter)", body: "var(--font-inter)" },
});

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ChakraProvider theme={theme}>
      <FeatureFlagsProvider>
        <AuthProvider>{children}</AuthProvider>
      </FeatureFlagsProvider>
    </ChakraProvider>
  );
}
