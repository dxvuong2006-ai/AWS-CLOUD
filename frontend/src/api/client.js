import { readSession, clearSession } from "./session";

const BASE_URL = (
  import.meta.env.VITE_API_URL || "http://localhost:8000"
).replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `HTTP ${status}`);
    this.status = status;
  }
}

export async function request(path, { method = "GET", body, auth = true, timeoutMs = 0, keepalive = false } = {}) {
  const token = auth ? readSession()?.token : null;
  if (token?.startsWith("mock:")) throw new ApiError(401, "Tài khoản mô phỏng không thể gọi API thật.");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const controller = timeoutMs > 0 ? new AbortController() : null;
  const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;
  let res;
  try {
    res = await fetch(`${BASE_URL}${normalizedPath}`, {
      method,
      ...(controller ? { signal: controller.signal } : {}),
      keepalive: keepalive && JSON.stringify(body ?? "").length < 60000,
      headers: {
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } finally {
    if (timer) clearTimeout(timer);
  }
  if (!res.ok) {
    let detail = "";
    try {
      const data = await res.json();
      detail = typeof data.detail === "string" ? data.detail : "";
    } catch {
      // Non-JSON errors retain their HTTP status.
    }
    if (res.status === 401 && token && readSession()?.token === token) {
      clearSession();
      window.dispatchEvent(new Event("learncloud:unauthorized"));
    }
    throw new ApiError(res.status, detail);
  }
  return res.status === 204 ? null : res.json();
}
