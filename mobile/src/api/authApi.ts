import axios from "axios";

import { API_BASE_URL } from "./config";

// A plain, un-intercepted axios instance for the auth endpoints themselves -
// login/refresh/logout must never trigger the authenticated client's
// "on 401, try to refresh" interceptor (see client.ts), or a bad login
// attempt could recurse into a refresh attempt.
const authHttp = axios.create({ baseURL: API_BASE_URL });

export type Role = "employee" | "admin";

export interface TokenPair {
  access_token: string;
  refresh_token: string;
}

export interface MeResponse {
  role: Role;
  id: number;
  name?: string;
  employee_code?: string;
  username?: string;
  org: { id: number; name: string; timezone: string };
  plan: string;
  promo_active: boolean;
  features: Record<string, boolean>;
}

function apiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err) && err.response?.data?.error?.message) {
    return err.response.data.error.message as string;
  }
  return fallback;
}

export async function employeeLogin(
  companyCode: string,
  employeeCode: string,
  pin: string
): Promise<TokenPair> {
  try {
    const res = await authHttp.post<TokenPair>("/api/v1/auth/employee/login", {
      company_code: companyCode,
      employee_code: employeeCode,
      pin,
      device_label: "React Native app",
    });
    return res.data;
  } catch (err) {
    throw new Error(apiErrorMessage(err, "Unable to sign in. Please try again."));
  }
}

export async function adminLogin(
  companyCode: string,
  username: string,
  password: string
): Promise<TokenPair> {
  try {
    const res = await authHttp.post<TokenPair>("/api/v1/auth/admin/login", {
      company_code: companyCode,
      username,
      password,
      device_label: "React Native app",
    });
    return res.data;
  } catch (err) {
    throw new Error(apiErrorMessage(err, "Unable to sign in. Please try again."));
  }
}

export async function refreshTokens(refreshToken: string): Promise<TokenPair> {
  const res = await authHttp.post<TokenPair>("/api/v1/auth/refresh", {
    refresh_token: refreshToken,
  });
  return res.data;
}

export async function logout(refreshToken: string): Promise<void> {
  try {
    await authHttp.post("/api/v1/auth/logout", { refresh_token: refreshToken });
  } catch {
    // Best-effort: if this fails, the refresh token still expires on its own,
    // and the access token expires within 15 minutes regardless.
  }
}

export async function fetchMe(accessToken: string): Promise<MeResponse> {
  const res = await authHttp.get<MeResponse>("/api/v1/auth/me", {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  return res.data;
}
