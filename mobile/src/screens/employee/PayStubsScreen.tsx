import React from "react";
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { useQuery } from "@tanstack/react-query";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { getPayStubs, PayStubSummary } from "../../api/employee";
import type { MoreStackParamList } from "../../navigation/MoreStack";

export default function PayStubsScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<MoreStackParamList>>();
  const query = useQuery({ queryKey: ["pay-stubs"], queryFn: getPayStubs });

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
      keyExtractor={(s) => s.period_start}
      renderItem={({ item }: { item: PayStubSummary }) => (
        <Pressable
          style={styles.row}
          onPress={() => navigation.navigate("PayStubDetail", { periodStart: item.period_start })}
        >
          <View style={{ flex: 1 }}>
            <Text style={styles.rowTitle}>
              {item.period_start} → {item.period_end}
            </Text>
            <Text style={styles.rowSubtitle}>{item.hours.toFixed(2)} hrs</Text>
          </View>
          <Text style={styles.rowAmount}>${item.pay.toFixed(2)}</Text>
        </Pressable>
      )}
      ListHeaderComponent={<Text style={styles.header}>Pay Stubs</Text>}
      contentContainerStyle={{ padding: 16 }}
    />
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#fff" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  header: { fontSize: 22, fontWeight: "700", marginBottom: 12, color: "#1c1a17" },
  row: { flexDirection: "row", alignItems: "center", paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: "#e3dbcb" },
  rowTitle: { fontWeight: "600", color: "#1c1a17" },
  rowSubtitle: { color: "#6f6656", marginTop: 2 },
  rowAmount: { fontWeight: "700", fontSize: 16, color: "#1c1a17" },
});
