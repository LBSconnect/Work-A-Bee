import React from "react";
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from "react-native";
import { useQuery } from "@tanstack/react-query";
import { useRoute, RouteProp } from "@react-navigation/native";

import { getPayStubDetail, PayStubEntry } from "../../api/employee";
import type { MoreStackParamList } from "../../navigation/MoreStack";

export default function PayStubDetailScreen() {
  const route = useRoute<RouteProp<MoreStackParamList, "PayStubDetail">>();
  const { periodStart } = route.params;

  const query = useQuery({
    queryKey: ["pay-stub-detail", periodStart],
    queryFn: () => getPayStubDetail(periodStart),
  });

  if (query.isLoading || !query.data) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#a8641f" />
      </View>
    );
  }

  const stub = query.data;

  return (
    <FlatList
      style={styles.screen}
      data={stub.entries}
      keyExtractor={(_, i) => String(i)}
      renderItem={({ item }: { item: PayStubEntry }) => (
        <View style={styles.row}>
          <Text style={styles.rowTitle}>
            {item.clock_in ? new Date(item.clock_in).toLocaleString() : "—"}
            {item.clock_out ? ` – ${new Date(item.clock_out).toLocaleTimeString()}` : " (open)"}
          </Text>
          <Text style={styles.rowSubtitle}>{item.hours != null ? `${item.hours.toFixed(2)} hrs` : ""}</Text>
        </View>
      )}
      ListHeaderComponent={
        <View>
          <Text style={styles.header}>
            {stub.period_start} → {stub.period_end}
          </Text>
          <View style={styles.summary}>
            <Text style={styles.summaryLine}>Regular: {stub.regular_hours.toFixed(2)} hrs</Text>
            <Text style={styles.summaryLine}>Overtime: {stub.overtime_hours.toFixed(2)} hrs</Text>
            <Text style={styles.summaryTotal}>Total due: ${stub.total_due.toFixed(2)}</Text>
          </View>
        </View>
      }
      ListEmptyComponent={<Text style={styles.empty}>No time entries in this period.</Text>}
      contentContainerStyle={{ padding: 16 }}
    />
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#fff" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  header: { fontSize: 20, fontWeight: "700", marginBottom: 12, color: "#1c1a17" },
  summary: { backgroundColor: "#faf7f1", borderRadius: 10, padding: 14, marginBottom: 16, gap: 4 },
  summaryLine: { color: "#6f6656" },
  summaryTotal: { fontWeight: "700", fontSize: 16, color: "#1c1a17", marginTop: 4 },
  row: { paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: "#e3dbcb" },
  rowTitle: { color: "#1c1a17" },
  rowSubtitle: { color: "#6f6656", marginTop: 2 },
  empty: { color: "#6f6656", textAlign: "center", marginTop: 20 },
});
