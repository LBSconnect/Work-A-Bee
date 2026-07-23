import React, { useState } from "react";
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createPtoRequest, getPtoRequests, PtoRequest } from "../../api/employee";
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

export default function PtoScreen() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["pto"], queryFn: getPtoRequests });

  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [hours, setHours] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => createPtoRequest({ start_date: startDate, end_date: endDate, hours: Number(hours), reason }),
    onSuccess: () => {
      setStartDate("");
      setEndDate("");
      setHours("");
      setReason("");
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["pto"] });
    },
    onError: (err) => setError(apiErrorMessage(err, "Couldn't submit that request.")),
  });

  return (
    <FlatList
      style={styles.screen}
      data={query.data ?? []}
      keyExtractor={(r) => String(r.id)}
      renderItem={({ item }: { item: PtoRequest }) => (
        <View style={styles.row}>
          <View style={{ flex: 1 }}>
            <Text style={styles.rowTitle}>
              {item.start_date} → {item.end_date}
            </Text>
            <Text style={styles.rowSubtitle}>
              {item.hours}h{item.reason ? ` · ${item.reason}` : ""}
            </Text>
          </View>
          <StatusPill status={item.status} />
        </View>
      )}
      ListHeaderComponent={
        <View>
          <Text style={styles.header}>Request Time Off</Text>
          <TextInput style={styles.input} placeholder="Start date (YYYY-MM-DD)" value={startDate} onChangeText={setStartDate} />
          <TextInput style={styles.input} placeholder="End date (YYYY-MM-DD)" value={endDate} onChangeText={setEndDate} />
          <TextInput style={styles.input} placeholder="Hours" keyboardType="numeric" value={hours} onChangeText={setHours} />
          <TextInput style={styles.input} placeholder="Reason (optional)" value={reason} onChangeText={setReason} />
          {error ? <Text style={styles.error}>{error}</Text> : null}
          <Pressable style={styles.submitButton} onPress={() => mutation.mutate()} disabled={mutation.isPending}>
            {mutation.isPending ? <ActivityIndicator color="#fff" /> : <Text style={styles.submitButtonText}>Submit Request</Text>}
          </Pressable>
          <Text style={styles.subheader}>My Requests</Text>
        </View>
      }
      ListEmptyComponent={query.isLoading ? null : <Text style={styles.empty}>No time off requests yet.</Text>}
      contentContainerStyle={{ padding: 16 }}
    />
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#fff" },
  header: { fontSize: 22, fontWeight: "700", marginBottom: 12, color: "#1c1a17" },
  subheader: { fontSize: 16, fontWeight: "700", marginTop: 24, marginBottom: 4, color: "#1c1a17" },
  input: { borderWidth: 1, borderColor: "#e3dbcb", borderRadius: 10, paddingHorizontal: 14, paddingVertical: 10, marginBottom: 10 },
  error: { color: "#a3271d", marginBottom: 10 },
  submitButton: { backgroundColor: "#a8641f", borderRadius: 10, paddingVertical: 12, alignItems: "center" },
  submitButtonText: { color: "#fff", fontWeight: "700" },
  row: { flexDirection: "row", alignItems: "center", paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: "#e3dbcb" },
  rowTitle: { fontWeight: "600", color: "#1c1a17" },
  rowSubtitle: { color: "#6f6656", marginTop: 2 },
  pill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 100 },
  pillText: { fontSize: 12, fontWeight: "700", textTransform: "capitalize" },
  pillPending: { backgroundColor: "#f5e8cf" },
  pillApproved: { backgroundColor: "#dfeee3" },
  pillDenied: { backgroundColor: "#f6e1de" },
  empty: { color: "#6f6656", textAlign: "center", marginTop: 20 },
});
