import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { useAuth } from "../../auth/AuthContext";
import type { MoreStackParamList } from "../../navigation/MoreStack";

const MENU_ITEMS: { label: string; screen: keyof MoreStackParamList }[] = [
  { label: "Pay Stubs", screen: "PayStubs" },
  { label: "Time History", screen: "TimeHistory" },
  { label: "Profile", screen: "Profile" },
  { label: "Announcements", screen: "Announcements" },
  { label: "Notifications", screen: "Notifications" },
];

export default function MoreScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<MoreStackParamList>>();
  const { signOut } = useAuth();

  return (
    <View style={styles.screen}>
      {MENU_ITEMS.map((item) => (
        <Pressable key={item.screen} style={styles.row} onPress={() => navigation.navigate(item.screen as never)}>
          <Text style={styles.rowText}>{item.label}</Text>
          <Text style={styles.chevron}>›</Text>
        </Pressable>
      ))}
      <Pressable style={styles.signOutButton} onPress={() => signOut()}>
        <Text style={styles.signOutButtonText}>Sign Out</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#fff", padding: 16 },
  row: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingVertical: 16, borderBottomWidth: 1, borderBottomColor: "#e3dbcb" },
  rowText: { fontSize: 16, color: "#1c1a17" },
  chevron: { fontSize: 20, color: "#6f6656" },
  signOutButton: { marginTop: 32, paddingVertical: 14, alignItems: "center", backgroundColor: "#a3271d", borderRadius: 10 },
  signOutButtonText: { color: "#fff", fontWeight: "700" },
});
