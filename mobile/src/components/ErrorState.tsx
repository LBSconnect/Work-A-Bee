import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

// Shared "couldn't load, try again" state - the pattern ClockScreen already
// established for itself. Every other data-fetching screen either fell
// through to its empty-state copy on a failed request (misleading - "no
// announcements" and "no fetch error" look identical to a user) or, worse,
// spun its loading indicator forever with no way out. This makes a real
// fetch failure visibly distinct and gives the user a way to recover
// without backgrounding/killing the app.
export function ErrorState({
  message = "Something went wrong.",
  onRetry,
}: {
  message?: string;
  onRetry: () => void;
}) {
  return (
    <View style={styles.center}>
      <Text style={styles.error}>{message}</Text>
      <Pressable style={styles.retryButton} onPress={onRetry}>
        <Text style={styles.retryButtonText}>Try again</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center", gap: 12, padding: 24 },
  error: { color: "#a3271d", textAlign: "center" },
  retryButton: { backgroundColor: "#a8641f", paddingHorizontal: 20, paddingVertical: 10, borderRadius: 10 },
  retryButtonText: { color: "#fff", fontWeight: "700" },
});
