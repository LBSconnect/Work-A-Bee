import React from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";
import { useQuery } from "@tanstack/react-query";

import { getProfile } from "../../api/employee";
import { ErrorState } from "../../components/ErrorState";

function Field({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <View style={styles.field}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <Text style={styles.fieldValue}>{value}</Text>
    </View>
  );
}

export default function ProfileScreen() {
  const query = useQuery({ queryKey: ["profile"], queryFn: getProfile });

  if (query.isLoading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#a8641f" />
      </View>
    );
  }

  // See PayStubDetailScreen's comment on why isError/!data is a separate
  // branch from isLoading, not folded into it.
  if (query.isError || !query.data) {
    return <ErrorState message="Couldn't load your profile." onRetry={() => query.refetch()} />;
  }

  const p = query.data;

  return (
    <ScrollView style={styles.screen} contentContainerStyle={{ padding: 16 }}>
      <Text style={styles.header}>{p.name}</Text>
      <Field label="Employee ID" value={p.employee_code} />
      <Field label="Job Title" value={p.job_title} />
      <Field label="Department" value={p.department} />
      <Field label="Worker Type" value={p.worker_type} />
      <Field label="Hourly Rate" value={`$${p.hourly_rate.toFixed(2)}`} />
      <Field label="Email" value={p.email} />
      <Field label="Phone" value={p.phone} />
      <Field label="PTO Balance" value={p.pto_balance_hours != null ? `${p.pto_balance_hours.toFixed(1)} hrs` : null} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#fff" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  header: { fontSize: 24, fontWeight: "700", marginBottom: 20, color: "#1c1a17" },
  field: { paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: "#e3dbcb" },
  fieldLabel: { fontSize: 12, textTransform: "uppercase", letterSpacing: 0.5, color: "#6f6656" },
  fieldValue: { fontSize: 16, color: "#1c1a17", marginTop: 2 },
});
