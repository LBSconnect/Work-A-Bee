import React from "react";
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from "react-native";
import { useQuery } from "@tanstack/react-query";

import { getSchedule, Shift } from "../../api/employee";

function formatRange(startIso: string, endIso: string) {
  const start = new Date(startIso);
  const end = new Date(endIso);
  const day = start.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  const startTime = start.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  const endTime = end.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  return `${day} · ${startTime}–${endTime}`;
}

function ShiftRow({ shift }: { shift: Shift }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowTitle}>{formatRange(shift.shift_start, shift.shift_end)}</Text>
      {shift.notes ? <Text style={styles.rowSubtitle}>{shift.notes}</Text> : null}
      {shift.offered_for_swap ? <Text style={styles.badge}>Offered for swap</Text> : null}
    </View>
  );
}

export default function ScheduleScreen() {
  const query = useQuery({ queryKey: ["schedule"], queryFn: getSchedule });

  if (query.isLoading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#a8641f" />
      </View>
    );
  }

  return (
    <FlatList
      style={styles.screen}
      data={query.data ?? []}
      keyExtractor={(s) => String(s.id)}
      renderItem={({ item }) => <ShiftRow shift={item} />}
      ListHeaderComponent={<Text style={styles.header}>Upcoming Shifts</Text>}
      ListEmptyComponent={<Text style={styles.empty}>No upcoming shifts scheduled.</Text>}
      contentContainerStyle={{ padding: 16 }}
    />
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#fff" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  header: { fontSize: 22, fontWeight: "700", marginBottom: 12, color: "#1c1a17" },
  row: { paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: "#e3dbcb" },
  rowTitle: { fontSize: 16, fontWeight: "600", color: "#1c1a17" },
  rowSubtitle: { color: "#6f6656", marginTop: 2 },
  badge: { marginTop: 6, alignSelf: "flex-start", backgroundColor: "#f1e2cc", color: "#a8641f", fontSize: 12, fontWeight: "700", paddingHorizontal: 8, paddingVertical: 2, borderRadius: 100 },
  empty: { color: "#6f6656", textAlign: "center", marginTop: 40 },
});
