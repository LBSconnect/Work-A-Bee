import React from "react";
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from "react-native";
import { useQuery } from "@tanstack/react-query";

import { getTimeHistory, TimeHistoryEntry } from "../../api/employee";

export default function TimeHistoryScreen() {
  const query = useQuery({ queryKey: ["time-history"], queryFn: getTimeHistory });

  if (query.isLoading || !query.data) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#a8641f" />
      </View>
    );
  }

  return (
    <FlatList
      style={styles.screen}
      data={query.data.history}
      keyExtractor={(_, i) => String(i)}
      renderItem={({ item }: { item: TimeHistoryEntry }) => (
        <View style={styles.row}>
          <Text style={styles.rowTitle}>{new Date(item.clock_in).toLocaleString()}</Text>
          <Text style={styles.rowSubtitle}>
            {item.clock_out ? `Out ${new Date(item.clock_out).toLocaleTimeString()}` : "Still clocked in"}
            {item.hours != null ? ` · ${item.hours.toFixed(2)} hrs` : ""}
          </Text>
        </View>
      )}
      ListHeaderComponent={<Text style={styles.header}>Recent Time Entries</Text>}
      ListEmptyComponent={<Text style={styles.empty}>No time entries yet.</Text>}
      contentContainerStyle={{ padding: 16 }}
    />
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#fff" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  header: { fontSize: 22, fontWeight: "700", marginBottom: 12, color: "#1c1a17" },
  row: { paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: "#e3dbcb" },
  rowTitle: { fontWeight: "600", color: "#1c1a17" },
  rowSubtitle: { color: "#6f6656", marginTop: 2 },
  empty: { color: "#6f6656", textAlign: "center", marginTop: 20 },
});
