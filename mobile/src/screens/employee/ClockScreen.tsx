import React from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "../../auth/AuthContext";
import { getClockStatus, toggleClock } from "../../api/employee";

export default function ClockScreen() {
  const { me, signOut } = useAuth();
  const queryClient = useQueryClient();

  const statusQuery = useQuery({
    queryKey: ["clock-status"],
    queryFn: getClockStatus,
  });

  const toggleMutation = useMutation({
    mutationFn: toggleClock,
    onSuccess: (data) => {
      queryClient.setQueryData(["clock-status"], data);
    },
  });

  if (statusQuery.isLoading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#a8641f" />
      </View>
    );
  }

  if (statusQuery.isError || !statusQuery.data) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>Couldn't load your clock status.</Text>
        <Pressable style={styles.retryButton} onPress={() => statusQuery.refetch()}>
          <Text style={styles.retryButtonText}>Try again</Text>
        </Pressable>
      </View>
    );
  }

  const status = statusQuery.data;

  return (
    <View style={styles.screen}>
      <Text style={styles.greeting}>Hi, {me?.name ?? me?.username}</Text>

      <View style={[styles.statusPill, status.clocked_in ? styles.statusPillIn : styles.statusPillOut]}>
        <Text style={styles.statusPillText}>{status.clocked_in ? "Clocked In" : "Clocked Out"}</Text>
      </View>

      <Pressable
        style={[styles.clockButton, status.clocked_in ? styles.clockButtonOut : styles.clockButtonIn]}
        onPress={() => toggleMutation.mutate()}
        disabled={toggleMutation.isPending}
      >
        {toggleMutation.isPending ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.clockButtonText}>{status.clocked_in ? "Clock Out" : "Clock In"}</Text>
        )}
      </Pressable>

      <View style={styles.summary}>
        <Text style={styles.summaryLabel}>This pay period</Text>
        <Text style={styles.summaryValue}>{status.current_period_hours.toFixed(2)} hrs</Text>
        <Text style={styles.summaryValue}>${status.current_period_pay.toFixed(2)}</Text>
      </View>

      <Pressable style={styles.signOutButton} onPress={() => signOut()}>
        <Text style={styles.signOutButtonText}>Sign Out</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, alignItems: "center", padding: 24, backgroundColor: "#fff", gap: 16 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", gap: 12 },
  greeting: { fontSize: 22, fontWeight: "700", marginTop: 24, color: "#1c1a17" },
  statusPill: { paddingHorizontal: 18, paddingVertical: 8, borderRadius: 100 },
  statusPillIn: { backgroundColor: "#dfeee3" },
  statusPillOut: { backgroundColor: "#e7eaee" },
  statusPillText: { fontWeight: "700", color: "#1c1a17" },
  clockButton: { width: "100%", paddingVertical: 22, borderRadius: 16, alignItems: "center", marginTop: 12 },
  clockButtonIn: { backgroundColor: "#2c6b4c" },
  clockButtonOut: { backgroundColor: "#a3271d" },
  clockButtonText: { color: "#fff", fontSize: 20, fontWeight: "700" },
  summary: { alignItems: "center", marginTop: 24, gap: 4 },
  summaryLabel: { color: "#6f6656", fontSize: 13, textTransform: "uppercase", letterSpacing: 0.5 },
  summaryValue: { fontSize: 18, fontWeight: "600", color: "#1c1a17" },
  error: { color: "#a3271d" },
  retryButton: { backgroundColor: "#a8641f", paddingHorizontal: 20, paddingVertical: 10, borderRadius: 10 },
  retryButtonText: { color: "#fff", fontWeight: "700" },
  signOutButton: { marginTop: "auto", paddingVertical: 12 },
  signOutButtonText: { color: "#6f6656", fontWeight: "600" },
});
