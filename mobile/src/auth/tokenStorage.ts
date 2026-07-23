import * as SecureStore from "expo-secure-store";

// Refresh token is the only long-lived credential worth persisting to disk -
// it lives in the Android Keystore-backed SecureStore. The short-lived (15
// minute) access token is deliberately kept in memory only (see AuthContext)
// so it never touches disk at all.
const REFRESH_TOKEN_KEY = "workabeez_refresh_token";

export async function getStoredRefreshToken(): Promise<string | null> {
  return SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
}

export async function setStoredRefreshToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, token);
}

export async function clearStoredRefreshToken(): Promise<void> {
  await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
}
