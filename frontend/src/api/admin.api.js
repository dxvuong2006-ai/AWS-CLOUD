import { request } from "./client";

export const listAdminUsers = (search = "") =>
  request(`/admin/users${search ? `?search=${encodeURIComponent(search)}` : ""}`);
export const createAdminUser = (payload) =>
  request("/admin/users", { method: "POST", body: payload });
export const updateAdminUser = (userId, payload) =>
  request(`/admin/users/${userId}`, { method: "PATCH", body: payload });
export const setAdminUserEnabled = (userId, enabled) =>
  request(`/admin/users/${userId}/status`, { method: "PATCH", body: { enabled } });
export const listMonitoringJobs = () => request("/admin/monitoring/jobs");
