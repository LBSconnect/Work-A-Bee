import { apiClient } from "./client";

export interface ClockedInEmployee {
  employee_id: number;
  name: string;
  employee_code: string;
  clock_in: string;
}

export interface AttendanceException {
  employee_code: string;
  name: string;
  date: string;
  scheduled_start: string | null;
  scheduled_end: string | null;
  actual_in: string | null;
  actual_out: string | null;
  flags: string;
}

export interface TodayStatus {
  date: string;
  clocked_in_now: ClockedInEmployee[];
  exceptions: AttendanceException[];
}

export async function getTodayStatus(): Promise<TodayStatus> {
  const res = await apiClient.get<TodayStatus>("/api/v1/admin/today");
  return res.data;
}

export interface AdminPtoRequest {
  id: number;
  employee_id: number;
  employee_name: string;
  employee_code: string;
  start_date: string;
  end_date: string;
  hours: number;
  reason: string | null;
  status: string;
  requested_at: string | null;
}

export async function getAdminPtoRequests(): Promise<AdminPtoRequest[]> {
  const res = await apiClient.get<{ requests: AdminPtoRequest[] }>("/api/v1/admin/pto");
  return res.data.requests;
}

export async function approvePto(id: number): Promise<{ request: AdminPtoRequest; warning?: string }> {
  const res = await apiClient.post<{ request: AdminPtoRequest; warning?: string }>(`/api/v1/admin/pto/${id}/approve`, {});
  return res.data;
}

export async function denyPto(id: number): Promise<AdminPtoRequest> {
  const res = await apiClient.post<{ request: AdminPtoRequest }>(`/api/v1/admin/pto/${id}/deny`, {});
  return res.data.request;
}

export interface AdminCorrection {
  id: number;
  employee_id: number;
  name: string;
  employee_code: string;
  issue_type: "missing_clock_in" | "missing_clock_out";
  issue_date: string;
  requested_clock_in: string | null;
  requested_clock_out: string | null;
  reason: string | null;
  status: string;
  manager_comment: string | null;
}

export async function getAdminCorrections(): Promise<AdminCorrection[]> {
  const res = await apiClient.get<{ requests: AdminCorrection[] }>("/api/v1/admin/corrections");
  return res.data.requests;
}

export async function approveCorrection(id: number): Promise<AdminCorrection> {
  const res = await apiClient.post<{ request: AdminCorrection }>(`/api/v1/admin/corrections/${id}/approve`, {});
  return res.data.request;
}

export async function denyCorrection(id: number, comment: string): Promise<AdminCorrection> {
  const res = await apiClient.post<{ request: AdminCorrection }>(`/api/v1/admin/corrections/${id}/deny`, { comment });
  return res.data.request;
}
