import React from "react";
import { ActivityIndicator, Alert, FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { AdminPtoRequest, approvePto, denyPto, getAdminPtoRequests } from "../../api/admin";
import { apiErrorMessage } from "../../api/client";

function StatusPill({ status }: { status: string }) {
  const style =
    status === "approved" ? styles.pillApproved : status === "denied" ? styles.pillDenied : styles.pillPending;
  return (
    <View style={[styles.pill, style]}>
      <Text style={styles.pillText}>{status}</Text>
    </View>
  );
}

export default function AdminPtoScreen() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["admin-pto"], queryFn: getAdminPtoRequests });

  const approveMutation = useMutation({
    mutationFn: approvePto,
    onSuccess: (data) => {
      if (data.warning) Alert.alert("Approved", data.warning);
      queryClient.invalidateQueries({ queryKey: ["admin-pto"] });
    },
    onError: (err) => Alert.alert("Couldn't approve", apiErrorMessage(err, "Please try again.")),
  });

  const denyMutation = useMutation({
    mutationFn: denyPto,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-pto"] }),
    onError: (err) => Alert.alert("Couldn't deny", apiErrorMessage(err, "Please try again.")),
  });

  return (
    <FlatList
      style={styles.screen}
      data={query.data ?? []}
      keyExtractor={(r) => String(r.id)}
      refreshing={query.isFetching}
      onRefresh={() => query.refetch()}
      ListHeaderComponent={<Text style={styles.header}>Time Off Requests</Text>}
      ListEmptyComponent={query.isLoading ? null : <Text style={styles.empty}>No time off requests.</Text>}
      contentContainerStyle={{ padding: 16 }}
      renderItem={({ item }: { item: AdminPtoRequest }) => (
        <View style={styles.row}>
          <View style={styles.rowTop}>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{item.employee_name}</Text>
              <Text style={styles.rowSubtitle}>
                {item.start_date} → {item.end_date} · {item.hours}h
              </Text>
              {item.reason ? <Text style={styles.rowSubtitle}>{item.reason}</Text> : null}
            </View>
            <StatusPill status={item.status} />
          </View>
          {item.status === "pending" && (
            <View style={styles.actions}>
              <Pressable
                style={[styles.actionButton, styles.approveButton]}
                onPress={() => approveMutation.mutate(item.id)}
                disabled={approveMutation.isPending || denyMutation.isPending}
              >
                {approveMutation.isPending && approveMutation.variables === item.id ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.actionButtonText}>Approve</Text>
                )}
              </Pressable>
              <Pressable
                style={[styles.actionButton, styles.denyButton]}
                onPress={() => denyMutation.mutate(item.id)}
                disabled={approveMutation.isPending || denyMutation.isPending}
              >
                {denyMutation.isPending && denyMutation.variables === item.id ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.actionButtonText}>Deny</Text>
                )}
              </Pressable>
            </View>
          )}
        </View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#fff" },
  header: { fontSize: 22, fontWeight: "700", marginBottom: 12, color: "#1c1a17" },
  row: { paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: "#e3dbcb" },
  rowTop: { flexDirection: "row", alignItems: "flex-start" },
  rowTitle: { fontWeight: "600", color: "#1c1a17" },
  rowSubtitle: { color: "#6f6656", marginTop: 2 },
  pill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 100 },
  pillText: { fontSize: 12, fontWeight: "700", textTransform: "capitalize" },
  pillPending: { backgroundColor: "#f5e8cf" },
  pillApproved: { backgroundColor: "#dfeee3" },
  pillDenied: { backgroundColor: "#f6e1de" },
  actions: { flexDirection: "row", gap: 10, marginTop: 10 },
  actionButton: { flex: 1, paddingVertical: 10, borderRadius: 10, alignItems: "center" },
  approveButton: { backgroundColor: "#2c6b4c" },
  denyButton: { backgroundColor: "#a3271d" },
  actionButtonText: { color: "#fff", fontWeight: "700" },
  empty: { color: "#6f6656", textAlign: "center", marginTop: 20 },
});
