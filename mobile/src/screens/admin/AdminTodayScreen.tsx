import React from "react";
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { useQuery } from "@tanstack/react-query";

import { AttendanceException, ClockedInEmployee, getTodayStatus } from "../../api/admin";
import { ErrorState } from "../../components/ErrorState";

function timeOnly(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

export default function AdminTodayScreen() {
  const query = useQuery({ queryKey: ["admin-today"], queryFn: getTodayStatus });

  if (query.isLoading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#a8641f" />
      </View>
    );
  }

  if (query.isError) {
    return <ErrorState message="Couldn't load today's status." onRetry={() => query.refetch()} />;
  }

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={{ padding: 16 }}
      refreshControl={<RefreshControl refreshing={query.isFetching} onRefresh={() => query.refetch()} />}
    >
      <Text style={styles.header}>Today</Text>

      <Text style={styles.subheader}>Clocked in now ({query.data?.clocked_in_now.length ?? 0})</Text>
      {(query.data?.clocked_in_now ?? []).length === 0 ? (
        <Text style={styles.empty}>No one is clocked in right now.</Text>
      ) : (
        query.data!.clocked_in_now.map((row: ClockedInEmployee) => (
          <View key={row.employee_id} style={styles.row}>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{row.name}</Text>
              <Text style={styles.rowSubtitle}>{row.employee_code}</Text>
            </View>
            <Text style={styles.rowMeta}>Since {timeOnly(row.clock_in)}</Text>
          </View>
        ))
      )}

      <Text style={[styles.subheader, { marginTop: 24 }]}>
        Today's exceptions ({query.data?.exceptions.length ?? 0})
      </Text>
      {(query.data?.exceptions ?? []).length === 0 ? (
        <Text style={styles.empty}>No attendance issues today.</Text>
      ) : (
        query.data!.exceptions.map((row: AttendanceException, i: number) => (
          <View key={`${row.employee_code}-${i}`} style={styles.row}>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{row.name}</Text>
              <Text style={styles.rowSubtitle}>{row.employee_code}</Text>
            </View>
            <Text style={styles.flagText}>{row.flags}</Text>
          </View>
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#fff" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  header: { fontSize: 22, fontWeight: "700", marginBottom: 12, color: "#1c1a17" },
  subheader: { fontSize: 16, fontWeight: "700", marginBottom: 4, color: "#1c1a17" },
  row: { flexDirection: "row", alignItems: "center", paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: "#e3dbcb" },
  rowTitle: { fontWeight: "600", color: "#1c1a17" },
  rowSubtitle: { color: "#6f6656", marginTop: 2 },
  rowMeta: { color: "#6f6656", fontSize: 13 },
  flagText: { color: "#a3271d", fontWeight: "700", fontSize: 13 },
  empty: { color: "#6f6656", marginBottom: 8 },
});
