import React, { useEffect } from "react";
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from "react-native";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useIsFocused } from "@react-navigation/native";

import { AppNotification, getNotifications, markNotificationsRead } from "../../api/employee";

export default function NotificationsScreen() {
  const isFocused = useIsFocused();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["notifications"], queryFn: getNotifications });

  const markReadMutation = useMutation({
    mutationFn: markNotificationsRead,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });

  // Viewing the list is what marks items read, same as the web app - but as
  // an explicit action on focus, not a side effect baked into the GET.
  useEffect(() => {
    if (isFocused && query.data?.some((n) => !n.read)) {
      markReadMutation.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isFocused, query.data]);

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
      keyExtractor={(n) => String(n.id)}
      renderItem={({ item }: { item: AppNotification }) => (
        <View style={[styles.row, !item.read && styles.rowUnread]}>
          <Text style={styles.rowTitle}>{item.title}</Text>
          {item.body ? <Text style={styles.rowBody}>{item.body}</Text> : null}
          <Text style={styles.rowDate}>{new Date(item.created_at).toLocaleString()}</Text>
        </View>
      )}
      ListHeaderComponent={<Text style={styles.header}>Notifications</Text>}
      ListEmptyComponent={<Text style={styles.empty}>You're all caught up.</Text>}
      contentContainerStyle={{ padding: 16 }}
    />
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#fff" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  header: { fontSize: 22, fontWeight: "700", marginBottom: 12, color: "#1c1a17" },
  row: { paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: "#e3dbcb" },
  rowUnread: { backgroundColor: "#faf7f1" },
  rowTitle: { fontWeight: "700", color: "#1c1a17" },
  rowBody: { color: "#1c1a17", marginTop: 2 },
  rowDate: { color: "#6f6656", marginTop: 4, fontSize: 12 },
  empty: { color: "#6f6656", textAlign: "center", marginTop: 20 },
});
