import { readSession, clearSession } from "./session";
import { currentCognitoAccessToken } from "./cognito";

const BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_URL ||
  "http://localhost:8000"
).replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(status, detail, code = "") {
    super(detail || `HTTP ${status}`);
    this.status = status;
    this.code = code;
  }
}

export async function request(
  path,
  { method = "GET", body, auth = true, timeoutMs = 0, keepalive = false } = {},
) {
  const storedSession = auth ? readSession() : null;
  let token = null;
  try {
    token = auth
      ? storedSession?.token.startsWith("mock:")
        ? storedSession.token
        : await currentCognitoAccessToken()
      : null;
  } catch (error) {
    clearSession();
    window.dispatchEvent(new Event("learncloud:unauthorized"));
    throw error;
  }
  if (auth && !token) {
    clearSession();
    window.dispatchEvent(new Event("learncloud:unauthorized"));
    throw new ApiError(401, "Authentication required.");
  }
  if (token?.startsWith("mock:")) {
    throw new ApiError(401, "Tài khoản mô phỏng không thể gọi API thật.");
  }

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const controller = timeoutMs > 0 ? new AbortController() : null;
  const timer = controller
    ? setTimeout(() => controller.abort(), timeoutMs)
    : null;
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
  } catch (error) {
    throw new ApiError(
      0,
      `Không kết nối được backend tại ${BASE_URL}. ${error.message}`,
      "BACKEND_CONNECTION_ERROR",
    );
  } finally {
    if (timer) clearTimeout(timer);
  }

  if (!res.ok) {
    let detail = "";
    let code = "";
    try {
      const data = await res.json();
      if (typeof data.detail === "string") {
        detail = data.detail;
      } else if (data.detail && typeof data.detail === "object") {
        detail =
          typeof data.detail.message === "string" ? data.detail.message : "";
        code = typeof data.detail.code === "string" ? data.detail.code : "";
      }
      if (!code && typeof data.code === "string") code = data.code;
    } catch {
      // Non-JSON responses retain their HTTP status.
    }
    if (res.status === 401 && token && readSession()?.token === token) {
      clearSession();
      window.dispatchEvent(new Event("learncloud:unauthorized"));
    }
    throw new ApiError(res.status, detail, code);
  }
  return res.status === 204 ? null : res.json();
}
