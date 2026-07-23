import React, { useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { useAuth } from "../auth/AuthContext";

type LoginRole = "employee" | "admin";

export default function LoginScreen() {
  const { signInEmployee, signInAdmin } = useAuth();
  const [role, setRole] = useState<LoginRole>("employee");
  const [companyCode, setCompanyCode] = useState("");
  const [identifier, setIdentifier] = useState(""); // employee code, or admin username
  const [secret, setSecret] = useState(""); // PIN, or admin password
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit() {
    setError(null);
    setSubmitting(true);
    try {
      if (role === "employee") {
        await signInEmployee(companyCode.trim(), identifier.trim(), secret.trim());
      } else {
        await signInAdmin(companyCode.trim(), identifier.trim(), secret);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.screen}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <Text style={styles.title}>Work-A-Beez</Text>

      <View style={styles.roleSwitch}>
        <Pressable
          style={[styles.roleButton, role === "employee" && styles.roleButtonActive]}
          onPress={() => setRole("employee")}
        >
          <Text style={[styles.roleButtonText, role === "employee" && styles.roleButtonTextActive]}>
            Employee
          </Text>
        </Pressable>
        <Pressable
          style={[styles.roleButton, role === "admin" && styles.roleButtonActive]}
          onPress={() => setRole("admin")}
        >
          <Text style={[styles.roleButtonText, role === "admin" && styles.roleButtonTextActive]}>
            Admin
          </Text>
        </Pressable>
      </View>

      <TextInput
        style={styles.input}
        placeholder="Company code"
        autoCapitalize="none"
        autoCorrect={false}
        value={companyCode}
        onChangeText={setCompanyCode}
      />
      <TextInput
        style={styles.input}
        placeholder={role === "employee" ? "Employee ID" : "Username"}
        autoCapitalize="none"
        autoCorrect={false}
        value={identifier}
        onChangeText={setIdentifier}
      />
      <TextInput
        style={styles.input}
        placeholder={role === "employee" ? "PIN" : "Password"}
        secureTextEntry
        keyboardType={role === "employee" ? "number-pad" : "default"}
        value={secret}
        onChangeText={setSecret}
      />

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <Pressable style={styles.submitButton} onPress={handleSubmit} disabled={submitting}>
        {submitting ? <ActivityIndicator color="#fff" /> : <Text style={styles.submitButtonText}>Sign In</Text>}
      </Pressable>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, justifyContent: "center", padding: 24, backgroundColor: "#fff" },
  title: { fontSize: 28, fontWeight: "700", textAlign: "center", marginBottom: 32, color: "#1c1a17" },
  roleSwitch: { flexDirection: "row", marginBottom: 20, borderRadius: 10, overflow: "hidden", borderWidth: 1, borderColor: "#e3dbcb" },
  roleButton: { flex: 1, paddingVertical: 10, alignItems: "center", backgroundColor: "#faf7f1" },
  roleButtonActive: { backgroundColor: "#a8641f" },
  roleButtonText: { fontWeight: "600", color: "#6f6656" },
  roleButtonTextActive: { color: "#fff" },
  input: {
    borderWidth: 1,
    borderColor: "#e3dbcb",
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    marginBottom: 12,
    fontSize: 16,
  },
  error: { color: "#a3271d", marginBottom: 12, textAlign: "center" },
  submitButton: {
    backgroundColor: "#a8641f",
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 8,
  },
  submitButtonText: { color: "#fff", fontWeight: "700", fontSize: 16 },
});
