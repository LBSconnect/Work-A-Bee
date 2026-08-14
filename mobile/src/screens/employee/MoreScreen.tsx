import React from "react";
import { Alert, Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useMutation } from "@tanstack/react-query";

import { useAuth } from "../../auth/AuthContext";
import type { MoreStackParamList } from "../../navigation/MoreStack";
import { PRIVACY_POLICY_URL } from "../../legal";
import { requestAccountDeletion } from "../../api/employee";
import { apiErrorMessage } from "../../api/client";

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

  // Apple Guideline 5.1.1(v): this app's accounts are provisioned by an
  // employer admin, not self-service signup, so "delete my account" here is
  // a request routed to that admin (see api/employee/account_deletion.py)
  // rather than an immediate self-service deletion - payroll/timekeeping
  // records typically carry their own retention requirements the employer
  // has to weigh before removing someone.
  const deletionMutation = useMutation({
    mutationFn: requestAccountDeletion,
    onSuccess: ({ already_requested }) => {
      Alert.alert(
        "Request sent",
        already_requested
          ? "You already have a pending deletion request. Your admin has been notified and will follow up with you."
          : "Your admin has been notified and will follow up with you."
      );
    },
    onError: (err) => Alert.alert("Couldn't send request", apiErrorMessage(err, "Please try again.")),
  });

  const confirmDeletion = () => {
    Alert.alert(
      "Delete My Account",
      "This sends a request to your employer's admin to delete your Work-A-Beez account and data. They'll follow up with you directly.",
      [
        { text: "Cancel", style: "cancel" },
        { text: "Request Deletion", style: "destructive", onPress: () => deletionMutation.mutate() },
      ]
    );
  };

  return (
    <View style={styles.screen}>
      {MENU_ITEMS.map((item) => (
        <Pressable key={item.screen} style={styles.row} onPress={() => navigation.navigate(item.screen as never)}>
          <Text style={styles.rowText}>{item.label}</Text>
          <Text style={styles.chevron}>›</Text>
        </Pressable>
      ))}
      <Pressable style={styles.row} onPress={() => Linking.openURL(PRIVACY_POLICY_URL)}>
        <Text style={styles.rowText}>Privacy Policy</Text>
        <Text style={styles.chevron}>›</Text>
      </Pressable>
      <Pressable style={styles.row} onPress={confirmDeletion} disabled={deletionMutation.isPending}>
        <Text style={[styles.rowText, styles.dangerText]}>Delete My Account</Text>
        <Text style={styles.chevron}>›</Text>
      </Pressable>
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
  dangerText: { color: "#a3271d" },
  chevron: { fontSize: 20, color: "#6f6656" },
  signOutButton: { marginTop: 32, paddingVertical: 14, alignItems: "center", backgroundColor: "#a3271d", borderRadius: 10 },
  signOutButtonText: { color: "#fff", fontWeight: "700" },
});
