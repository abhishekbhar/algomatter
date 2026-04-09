"use client";
import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { apiClient, setAccessToken, setRefreshToken, getRefreshToken, clearTokens } from "@/lib/api/client";

interface User {
  id: string;
  email: string;
  is_active: boolean;
  plan: string;
  created_at: string;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchMe = useCallback(async () => {
    try {
      const me = await apiClient<User>("/api/v1/auth/me");
      setUser(me);
    } catch {
      clearTokens();
      setUser(null);
    }
  }, []);

  useEffect(() => {
    const rt = getRefreshToken();
    if (!rt) { setIsLoading(false); return; }
    apiClient<{ access_token: string; refresh_token: string }>("/api/v1/auth/refresh", {
      method: "POST", body: { refresh_token: rt },
    })
      .then((data) => {
        setAccessToken(data.access_token);
        setRefreshToken(data.refresh_token);
        return fetchMe();
      })
      .catch(() => { clearTokens(); })
      .finally(() => setIsLoading(false));
  }, [fetchMe]);

  const login = useCallback(async (email: string, password: string) => {
    const data = await apiClient<{ access_token: string; refresh_token: string }>(
      "/api/v1/auth/login", { method: "POST", body: { email, password } }
    );
    setAccessToken(data.access_token);
    setRefreshToken(data.refresh_token);
    await fetchMe();
  }, [fetchMe]);

  const signup = useCallback(async (email: string, password: string) => {
    const data = await apiClient<{ access_token: string; refresh_token: string }>(
      "/api/v1/auth/signup", { method: "POST", body: { email, password } }
    );
    setAccessToken(data.access_token);
    setRefreshToken(data.refresh_token);
    await fetchMe();
  }, [fetchMe]);

  const logout = useCallback(async () => {
    const rt = getRefreshToken();
    if (rt) {
      // Best-effort: invalidate token on server; ignore network errors
      try {
        await apiClient("/api/v1/auth/logout", { method: "POST", body: { refresh_token: rt } });
      } catch {
        // ignore — token will expire naturally
      }
    }
    clearTokens();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
