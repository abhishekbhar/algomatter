"use client";
import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  ReactNode,
} from "react";
import { API_BASE_URL } from "@/lib/utils/constants";

export interface FeatureFlags {
  paperTrading: boolean;
  backtesting: boolean;
}

interface FeatureFlagsContextValue extends FeatureFlags {
  isLoading: boolean;
}

const DEFAULT_FLAGS: FeatureFlags = {
  paperTrading: true,
  backtesting: true,
};

const FeatureFlagsContext = createContext<FeatureFlagsContextValue>({
  ...DEFAULT_FLAGS,
  isLoading: true,
});

export function FeatureFlagsProvider({ children }: { children: ReactNode }) {
  const [flags, setFlags] = useState<FeatureFlags>(DEFAULT_FLAGS);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/config`);
        if (!res.ok) throw new Error(`status ${res.status}`);
        const data = await res.json();
        if (cancelled) return;
        const ff = data?.featureFlags ?? {};
        setFlags({
          paperTrading:
            typeof ff.paperTrading === "boolean" ? ff.paperTrading : true,
          backtesting:
            typeof ff.backtesting === "boolean" ? ff.backtesting : true,
        });
      } catch (err) {
        // Fail-open: keep defaults (both true) so UI matches historical behavior.
        // eslint-disable-next-line no-console
        console.warn("FeatureFlagsProvider: fetch failed, defaulting open", err);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <FeatureFlagsContext.Provider value={{ ...flags, isLoading }}>
      {children}
    </FeatureFlagsContext.Provider>
  );
}

export function useFeatureFlags(): FeatureFlagsContextValue {
  return useContext(FeatureFlagsContext);
}
