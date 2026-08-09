import { apiClient } from "./client";
import { Role } from "./authApi";

// Both best-effort: a failed push-token call must never block sign-in or
// sign-out. See registerForPushNotificationsAsync's own doc comment for the
// same rule on the client-side half of this.
export async function registerPushToken(role: Role, token: string): Promise<void> {
  try {
    await apiClient.post(`/api/v1/${role}/push-token`, { token });
  } catch {
    // This device just won't get pushes until the next successful sign-in.
  }
}

export async function unregisterPushToken(role: Role, token: string): Promise<void> {
  try {
    await apiClient.delete(`/api/v1/${role}/push-token`, { data: { token } });
  } catch {
    // Not worth retrying - the refresh token this session relied on is
    // typically already revoked by the time this runs during sign-out.
  }
}
