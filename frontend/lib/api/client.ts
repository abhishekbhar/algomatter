import { API_BASE_URL } from "@/lib/utils/constants";

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("refresh_token");
}

export function setRefreshToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem("refresh_token", token);
  else localStorage.removeItem("refresh_token");
}

export function clearTokens() {
  accessToken = null;
  if (typeof window !== "undefined") localStorage.removeItem("refresh_token");
}

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(`API error ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

async function refreshAccessToken(): Promise<boolean> {
  const rt = getRefreshToken();
  if (!rt) return false;
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: rt }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    setAccessToken(data.access_token);
    setRefreshToken(data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  rawResponse?: boolean;
}

export async function apiClient<T = unknown>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = "GET", body, headers = {}, rawResponse } = options;
  const reqHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...headers,
  };
  if (accessToken) reqHeaders["Authorization"] = `Bearer ${accessToken}`;

  const fetchOpts: RequestInit = { method, headers: reqHeaders };
  if (body) fetchOpts.body = JSON.stringify(body);

  let res = await fetch(`${API_BASE_URL}${path}`, fetchOpts);

  if (res.status === 401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      reqHeaders["Authorization"] = `Bearer ${accessToken}`;
      res = await fetch(`${API_BASE_URL}${path}`, {
        method,
        headers: reqHeaders,
        body: fetchOpts.body,
      });
    } else {
      clearTokens();
      if (typeof window !== "undefined") {
        window.location.href = "/app/login";
      }
      throw new ApiError(401, "Session expired");
    }
  }

  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(res.status, detail);
  }

  if (rawResponse) return res as unknown as T;
  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}
