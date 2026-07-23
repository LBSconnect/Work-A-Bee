import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

import { API_BASE_URL } from "./config";
import { refreshTokens } from "./authApi";
import { getStoredRefreshToken, setStoredRefreshToken, clearStoredRefreshToken } from "../auth/tokenStorage";

// Authenticated client for everything except the auth endpoints themselves
// (see authApi.ts). Holds the current access token in memory only - never on
// disk - and transparently refreshes once on a 401 before giving up.
let accessToken: string | null = null;
let onSessionExpired: (() => void) | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function setOnSessionExpired(handler: () => void) {
  onSessionExpired = handler;
}

export const apiClient = axios.create({ baseURL: API_BASE_URL });

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

let refreshInFlight: Promise<string | null> | null = null;

async function tryRefresh(): Promise<string | null> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const storedRefresh = await getStoredRefreshToken();
      if (!storedRefresh) return null;
      try {
        const pair = await refreshTokens(storedRefresh);
        await setStoredRefreshToken(pair.refresh_token);
        setAccessToken(pair.access_token);
        return pair.access_token;
      } catch {
        await clearStoredRefreshToken();
        return null;
      }
    })();
  }
  try {
    return await refreshInFlight;
  } finally {
    refreshInFlight = null;
  }
}

apiClient.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;
    if (error.response?.status === 401 && original && !original._retried) {
      original._retried = true;
      const newAccessToken = await tryRefresh();
      if (newAccessToken) {
        original.headers.Authorization = `Bearer ${newAccessToken}`;
        return apiClient(original);
      }
      onSessionExpired?.();
    }
    return Promise.reject(error);
  }
);

export function apiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err) && err.response?.data && (err.response.data as any).error?.message) {
    return (err.response.data as any).error.message as string;
  }
  return fallback;
}
