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

export interface PayStubSummary {
  period_start: string;
  period_end: string;
  hours: number;
  regular_hours: number;
  overtime_hours: number;
  pay: number;
}

export async function getPayStubs(): Promise<PayStubSummary[]> {
  const res = await apiClient.get<{ stubs: PayStubSummary[] }>("/api/v1/employee/pay-stubs");
  return res.data.stubs;
}

export interface PayStubEntry {
  clock_in: string | null;
  clock_out: string | null;
  hours: number | null;
  running_hours: number | null;
  running_due: number | null;
  is_manual: boolean;
}

export interface PayStubDetail {
  period_start: string;
  period_end: string;
  hourly_rate: number;
  total_hours: number;
  regular_hours: number;
  overtime_hours: number;
  total_due: number;
  entries: PayStubEntry[];
}

export async function getPayStubDetail(periodStart: string): Promise<PayStubDetail> {
  const res = await apiClient.get<PayStubDetail>(`/api/v1/employee/pay-stubs/${periodStart}`);
  return res.data;
}

export interface PtoRequest {
  id: number;
  start_date: string;
  end_date: string;
  hours: number;
  reason: string | null;
  status: string;
  requested_at: string | null;
}

export async function getPtoRequests(): Promise<PtoRequest[]> {
  const res = await apiClient.get<{ requests: PtoRequest[] }>("/api/v1/employee/pto");
  return res.data.requests;
}

export async function createPtoRequest(input: {
  start_date: string;
  end_date: string;
  hours: number;
  reason?: string;
}): Promise<PtoRequest> {
  const res = await apiClient.post<{ request: PtoRequest }>("/api/v1/employee/pto", input);
  return res.data.request;
}

export interface Shift {
  id: number;
  shift_start: string;
  shift_end: string;
  notes: string | null;
  offered_for_swap: boolean;
}

export async function getSchedule(): Promise<Shift[]> {
  const res = await apiClient.get<{ shifts: Shift[] }>("/api/v1/employee/schedule");
  return res.data.shifts;
}

export interface TimeHistoryEntry {
  clock_in: string;
  clock_out: string | null;
  hours: number | null;
}

export interface WeeklyHistory {
  period_start: string;
  period_end: string;
  hours: number;
  pay: number;
}

export async function getTimeHistory(): Promise<{ history: TimeHistoryEntry[]; weekly_history: WeeklyHistory[] }> {
  const res = await apiClient.get("/api/v1/employee/time-history");
  return res.data;
}

export interface Profile {
  id: number;
  name: string;
  employee_code: string;
  worker_type: string;
  hourly_rate: number;
  email: string | null;
  phone: string | null;
  job_title: string | null;
  department: string | null;
  pto_balance_hours: number | null;
}

export async function getProfile(): Promise<Profile> {
  const res = await apiClient.get<{ employee: Profile }>("/api/v1/employee/profile");
  return res.data.employee;
}

export interface Announcement {
  id: number;
  title: string;
  body: string;
  created_at: string;
}

export async function getAnnouncements(): Promise<Announcement[]> {
  const res = await apiClient.get<{ announcements: Announcement[] }>("/api/v1/employee/announcements");
  return res.data.announcements;
}

export interface AppNotification {
  id: number;
  kind: string;
  title: string;
  body: string | null;
  link: string | null;
  read: boolean;
  created_at: string;
}

export async function getNotifications(): Promise<AppNotification[]> {
  const res = await apiClient.get<{ notifications: AppNotification[] }>("/api/v1/employee/notifications");
  return res.data.notifications;
}

export async function markNotificationsRead(): Promise<void> {
  await apiClient.post("/api/v1/employee/notifications/read", {});
}
