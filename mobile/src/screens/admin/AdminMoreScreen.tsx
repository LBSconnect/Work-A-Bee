import React from "react";
import { Alert, Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { useMutation } from "@tanstack/react-query";

import { useAuth } from "../../auth/AuthContext";
import { PRIVACY_POLICY_URL } from "../../legal";
import { requestAccountDeletion } from "../../api/admin";
import { apiErrorMessage } from "../../api/client";

export default function AdminMoreScreen() {
  const { me, signOut } = useAuth();

  // Apple Guideline 5.1.1(v): unlike employee accounts (provisioned by an
  // employer admin), admin accounts are created self-service via the web
  // signup wizard, so this role needs its own in-app deletion path - there's
  // no in-app "admin's admin" to route it to, so it goes to Work-A-Beez's
  // platform support contact instead (see api/admin/account_deletion.py).
  const deletionMutation = useMutation({
    mutationFn: requestAccountDeletion,
    onSuccess: ({ already_requested }) => {
      Alert.alert(
        "Request sent",
        already_requested
          ? "You already have a pending deletion request. Our support team will follow up with you."
          : "Our support team will follow up with you to complete the deletion."
      );
    },
    onError: (err) => Alert.alert("Couldn't send request", apiErrorMessage(err, "Please try again.")),
  });

  const confirmDeletion = () => {
    Alert.alert(
      "Delete My Account",
      "This sends a request to Work-A-Beez support to delete your account and organization's data. They'll follow up with you directly.",
      [
        { text: "Cancel", style: "cancel" },
        { text: "Request Deletion", style: "destructive", onPress: () => deletionMutation.mutate() },
      ]
    );
  };

  return (
    <View style={styles.screen}>
      <Text style={styles.title}>{me?.username}</Text>
      <Text style={styles.subtitle}>{me?.org.name}</Text>
      <Pressable onPress={() => Linking.openURL(PRIVACY_POLICY_URL)}>
        <Text style={styles.link}>Privacy Policy</Text>
      </Pressable>
      <Pressable onPress={confirmDeletion} disabled={deletionMutation.isPending}>
        <Text style={styles.dangerLink}>Delete My Account</Text>
      </Pressable>
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
  link: { marginTop: 16, color: "#a8641f", textDecorationLine: "underline" },
  dangerLink: { marginTop: 8, color: "#a3271d", textDecorationLine: "underline" },
  signOutButton: { marginTop: 24, paddingVertical: 12, paddingHorizontal: 20, backgroundColor: "#a8641f", borderRadius: 10 },
  signOutButtonText: { color: "#fff", fontWeight: "700" },
});
