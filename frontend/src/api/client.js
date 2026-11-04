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

export async function request(path, { method = "GET", body, auth = true } = {}) {
  const token = auth ? readSession()?.token : null;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const res = await fetch(`${BASE_URL}${normalizedPath}`, {
    method,
    headers: {
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!res.ok) {
    let detail = "";
    try {
      const data = await res.json();
      detail = typeof data.detail === "string" ? data.detail : "";
    } catch {
      // Non-JSON errors retain their HTTP status.
    }
    // A delayed response from an old session must not log out a new session.
    if (res.status === 401 && token && readSession()?.token === token) {
      clearSession();
      window.dispatchEvent(new Event("learncloud:unauthorized"));
    }
    throw new ApiError(res.status, detail);
  }
  return res.status === 204 ? null : res.json();
}
