import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { adminLogin, employeeLogin, fetchMe, logout as logoutApi, MeResponse, refreshTokens } from "../api/authApi";
import { setAccessToken, setOnSessionExpired } from "../api/client";
import { registerPushToken, unregisterPushToken } from "../api/pushApi";
import { registerForPushNotificationsAsync } from "../notifications/registerPushToken";
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
  // This device's current Expo push token, once known - not state, since
  // nothing ever needs to re-render off it. Only used to unregister on
  // sign-out; a failed lookup just leaves it null and sign-out skips that.
  const pushTokenRef = useRef<string | null>(null);

  const establishSession = useCallback(async (accessToken: string, refreshToken: string) => {
    setAccessToken(accessToken);
    await setStoredRefreshToken(refreshToken);
    const me = await fetchMe(accessToken);
    setState({ status: "signedIn", me, refreshToken });

    // Fire-and-forget: registering this device for push must never delay or
    // block sign-in landing on the home screen (see the doc comments on
    // registerForPushNotificationsAsync/registerPushToken for why each step
    // here already swallows its own failures).
    registerForPushNotificationsAsync().then((token) => {
      if (token) {
        pushTokenRef.current = token;
        registerPushToken(me.role, token);
      }
    });
  }, []);

  const signOut = useCallback(async () => {
    // Unregister the push token FIRST, while the access token can still be
    // silently refreshed if expired. logoutApi() revokes the refresh token
    // server-side - if that ran first and the access token had already
    // expired, this authenticated DELETE call's 401 would try to refresh
    // using the now-revoked refresh token, fail, and silently no-op
    // (unregisterPushToken swallows its own errors). That left the device's
    // push_tokens row behind, so a signed-out user kept receiving pushes
    // addressed to their account until someone else logged into the same
    // device and reassigned the token.
    if (pushTokenRef.current && state.me) {
      await unregisterPushToken(state.me.role, pushTokenRef.current);
      pushTokenRef.current = null;
    }
    if (state.refreshToken) {
      await logoutApi(state.refreshToken);
    }
    setAccessToken(null);
    await clearStoredRefreshToken();
    setState({ status: "signedOut", me: null, refreshToken: null });
  }, [state.refreshToken, state.me]);

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
