import * as Notifications from "expo-notifications";
import Constants from "expo-constants";
import { Platform } from "react-native";

// Controls how a push is presented while the app is in the foreground (Expo
// SDK 57's NotificationBehavior shape - shouldShowBanner/shouldShowList
// replaced the older shouldShowAlert field). Set once at module load, same
// as Expo's own docs example.
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

/**
 * Requests notification permission (if not already granted or denied) and
 * returns this device's Expo push token, or null if permission was denied,
 * this is a simulator/web build with no push capability, or the EAS project
 * isn't configured (see mobile/app.json's extra.eas.projectId).
 *
 * Never throws - a push token is a nice-to-have, not something that should
 * block sign-in if it fails. Callers should treat a null return as "this
 * device just won't get pushes," not as an error to surface to the user.
 */
export async function registerForPushNotificationsAsync(): Promise<string | null> {
  try {
    // Android 8+ requires at least one notification channel to exist before
    // permission is requested / notifications can be shown.
    if (Platform.OS === "android") {
      await Notifications.setNotificationChannelAsync("default", {
        name: "default",
        importance: Notifications.AndroidImportance.DEFAULT,
      });
    }

    const { status: existingStatus } = await Notifications.getPermissionsAsync();
    let finalStatus = existingStatus;
    if (existingStatus !== "granted") {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }
    if (finalStatus !== "granted") return null;

    const projectId = Constants.expoConfig?.extra?.eas?.projectId;
    if (!projectId) return null;

    const { data } = await Notifications.getExpoPushTokenAsync({ projectId });
    return data;
  } catch {
    return null;
  }
}
