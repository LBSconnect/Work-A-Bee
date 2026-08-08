import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useAuth } from "../../auth/AuthContext";

export default function AdminMoreScreen() {
  const { me, signOut } = useAuth();

  return (
    <View style={styles.screen}>
      <Text style={styles.title}>{me?.username}</Text>
      <Text style={styles.subtitle}>{me?.org.name}</Text>
      <Pressable style={styles.signOutButton} onPress={() => signOut()}>
        <Text style={styles.signOutButtonText}>Sign Out</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24, backgroundColor: "#fff", gap: 8 },
  title: { fontSize: 22, fontWeight: "700", color: "#1c1a17" },
  subtitle: { color: "#6f6656" },
  signOutButton: { marginTop: 24, paddingVertical: 12, paddingHorizontal: 20, backgroundColor: "#a8641f", borderRadius: 10 },
  signOutButtonText: { color: "#fff", fontWeight: "700" },
});
