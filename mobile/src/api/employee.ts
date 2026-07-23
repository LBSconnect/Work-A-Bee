import { apiClient } from "./client";

export interface ClockStatus {
  clocked_in: boolean;
  clock_in_at: string | null;
  current_period_hours: number;
  current_period_pay: number;
  period_start: string;
  period_end: string;
  action?: "clocked_in" | "clocked_out";
  at?: string;
}

export async function getClockStatus(): Promise<ClockStatus> {
  const res = await apiClient.get<ClockStatus>("/api/v1/employee/clock/status");
  return res.data;
}

export async function toggleClock(): Promise<ClockStatus> {
  const res = await apiClient.post<ClockStatus>("/api/v1/employee/clock", {});
  return res.data;
}
