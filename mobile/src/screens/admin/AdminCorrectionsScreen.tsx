import React, { useState } from "react";
import { ActivityIndicator, Alert, FlatList, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { AdminCorrection, approveCorrection, denyCorrection, getAdminCorrections } from "../../api/admin";
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

export default function AdminCorrectionsScreen() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["admin-corrections"], queryFn: getAdminCorrections });
  const [denyingId, setDenyingId] = useState<number | null>(null);
  const [comment, setComment] = useState("");

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["admin-corrections"] });

  const approveMutation = useMutation({
    mutationFn: approveCorrection,
    onSuccess: invalidate,
    onError: (err) => Alert.alert("Couldn't approve", apiErrorMessage(err, "Please try again.")),
  });

  const denyMutation = useMutation({
    mutationFn: ({ id, comment }: { id: number; comment: string }) => denyCorrection(id, comment),
    onSuccess: () => {
      setDenyingId(null);
      setComment("");
      invalidate();
    },
    onError: (err) => Alert.alert("Couldn't deny", apiErrorMessage(err, "Please try again.")),
  });

  return (
    <FlatList
      style={styles.screen}
      data={query.data ?? []}
      keyExtractor={(r) => String(r.id)}
      refreshing={query.isFetching}
      onRefresh={() => query.refetch()}
      ListHeaderComponent={<Text style={styles.header}>Punch Corrections</Text>}
      ListEmptyComponent={query.isLoading ? null : <Text style={styles.empty}>No correction requests.</Text>}
      contentContainerStyle={{ padding: 16 }}
      renderItem={({ item }: { item: AdminCorrection }) => (
        <View style={styles.row}>
          <View style={styles.rowTop}>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{item.name}</Text>
              <Text style={styles.rowSubtitle}>
                {item.issue_type === "missing_clock_out" ? "Missing clock-out" : "Missing clock-in"} · {item.issue_date}
              </Text>
              {item.reason ? <Text style={styles.rowSubtitle}>{item.reason}</Text> : null}
              {item.manager_comment ? <Text style={styles.rowSubtitle}>Comment: {item.manager_comment}</Text> : null}
            </View>
            <StatusPill status={item.status} />
          </View>

          {item.status === "pending" && (
            <>
              <View style={styles.actions}>
                <Pressable
                  style={[styles.actionButton, styles.approveButton]}
                  onPress={() => approveMutation.mutate(item.id)}
                  disabled={approveMutation.isPending}
                >
                  {approveMutation.isPending && approveMutation.variables === item.id ? (
                    <ActivityIndicator color="#fff" />
                  ) : (
                    <Text style={styles.actionButtonText}>Approve</Text>
                  )}
                </Pressable>
                <Pressable
                  style={[styles.actionButton, styles.denyButton]}
                  onPress={() => {
                    setComment("");
                    setDenyingId(denyingId === item.id ? null : item.id);
                  }}
                >
                  <Text style={styles.actionButtonText}>Deny</Text>
                </Pressable>
              </View>

              {denyingId === item.id && (
                <View style={styles.denyForm}>
                  <TextInput
                    style={styles.input}
                    placeholder="Reason for denying (required)"
                    value={comment}
                    onChangeText={setComment}
                    multiline
                  />
                  <Pressable
                    style={[styles.actionButton, styles.denyButton, !comment.trim() && styles.actionButtonDisabled]}
                    onPress={() => denyMutation.mutate({ id: item.id, comment: comment.trim() })}
                    disabled={!comment.trim() || denyMutation.isPending}
                  >
                    {denyMutation.isPending ? (
                      <ActivityIndicator color="#fff" />
                    ) : (
                      <Text style={styles.actionButtonText}>Confirm Deny</Text>
                    )}
                  </Pressable>
                </View>
              )}
            </>
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
  actionButtonDisabled: { opacity: 0.5 },
  approveButton: { backgroundColor: "#2c6b4c" },
  denyButton: { backgroundColor: "#a3271d" },
  actionButtonText: { color: "#fff", fontWeight: "700" },
  denyForm: { marginTop: 10, gap: 8 },
  input: {
    borderWidth: 1,
    borderColor: "#e3dbcb",
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    minHeight: 44,
  },
  empty: { color: "#6f6656", textAlign: "center", marginTop: 20 },
});
