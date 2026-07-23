import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { adminLogin, employeeLogin, fetchMe, logout as logoutApi, MeResponse, refreshTokens } from "../api/authApi";
import { setAccessToken, setOnSessionExpired } from "../api/client";
import { clearStoredRefreshToken, getStoredRefreshToken, setStoredRefreshToken } from "./tokenStorage";

interface AuthState {
  status: "loading" | "signedOut" | "signedIn";
  me: MeResponse | null;
  refreshToken: string | null;
}

interface AuthContextValue extends AuthState {
  signInEmployee: (companyCode: string, employeeCode: string, pin: string) => Promise<void>;
  signInAdmin: (companyCode: string, username: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading", me: null, refreshToken: null });

  const establishSession = useCallback(async (accessToken: string, refreshToken: string) => {
    setAccessToken(accessToken);
    await setStoredRefreshToken(refreshToken);
    const me = await fetchMe(accessToken);
    setState({ status: "signedIn", me, refreshToken });
  }, []);

  const signOut = useCallback(async () => {
    if (state.refreshToken) {
      await logoutApi(state.refreshToken);
    }
    setAccessToken(null);
    await clearStoredRefreshToken();
    setState({ status: "signedOut", me: null, refreshToken: null });
  }, [state.refreshToken]);

  const signInEmployee = useCallback(
    async (companyCode: string, employeeCode: string, pin: string) => {
      const pair = await employeeLogin(companyCode, employeeCode, pin);
      await establishSession(pair.access_token, pair.refresh_token);
    },
    [establishSession]
  );

  const signInAdmin = useCallback(
    async (companyCode: string, username: string, password: string) => {
      const pair = await adminLogin(companyCode, username, password);
      await establishSession(pair.access_token, pair.refresh_token);
    },
    [establishSession]
  );

  // Cold-start: try to resume a session from the stored refresh token.
  useEffect(() => {
    (async () => {
      const stored = await getStoredRefreshToken();
      if (!stored) {
        setState({ status: "signedOut", me: null, refreshToken: null });
        return;
      }
      try {
        const pair = await refreshTokens(stored);
        await establishSession(pair.access_token, pair.refresh_token);
      } catch {
        await clearStoredRefreshToken();
        setState({ status: "signedOut", me: null, refreshToken: null });
      }
    })();
  }, [establishSession]);

  // Wire the API client's "refresh failed" callback to a hard sign-out so an
  // expired/revoked session always drops the user back at the login screen.
  useEffect(() => {
    setOnSessionExpired(() => {
      setAccessToken(null);
      clearStoredRefreshToken();
      setState({ status: "signedOut", me: null, refreshToken: null });
    });
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, signInEmployee, signInAdmin, signOut }),
    [state, signInEmployee, signInAdmin, signOut]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
