import React from "react";
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from "react-native";
import { useQuery } from "@tanstack/react-query";

import { Announcement, getAnnouncements } from "../../api/employee";

export default function AnnouncementsScreen() {
  const query = useQuery({ queryKey: ["announcements"], queryFn: getAnnouncements });

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
      keyExtractor={(a) => String(a.id)}
      renderItem={({ item }: { item: Announcement }) => (
        <View style={styles.row}>
          <Text style={styles.rowTitle}>{item.title}</Text>
          <Text style={styles.rowBody}>{item.body}</Text>
          <Text style={styles.rowDate}>{new Date(item.created_at).toLocaleDateString()}</Text>
        </View>
      )}
      ListHeaderComponent={<Text style={styles.header}>Announcements</Text>}
      ListEmptyComponent={<Text style={styles.empty}>No announcements yet.</Text>}
      contentContainerStyle={{ padding: 16 }}
    />
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#fff" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  header: { fontSize: 22, fontWeight: "700", marginBottom: 12, color: "#1c1a17" },
  row: { paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: "#e3dbcb" },
  rowTitle: { fontWeight: "700", fontSize: 16, color: "#1c1a17" },
  rowBody: { color: "#1c1a17", marginTop: 4 },
  rowDate: { color: "#6f6656", marginTop: 6, fontSize: 12 },
  empty: { color: "#6f6656", textAlign: "center", marginTop: 20 },
});
