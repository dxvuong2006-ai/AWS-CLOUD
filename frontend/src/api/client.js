import { readSession, clearSession } from "./session";
import { currentCognitoAccessToken } from "./cognito";
import { LOCAL_AUTH } from "../config/auth";

const configuredBaseUrl = (
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8000"
).replace(/\/+$/, "");
// The local FastAPI instructions bind Uvicorn to IPv4 (127.0.0.1). On some
// Windows setups, fetch resolves "localhost" to ::1 first and fails instead
// of retrying the IPv4 listener, so normalize only that loopback hostname.
const BASE_URL = configuredBaseUrl.replace(
  /^(https?:\/\/)localhost(?=[:/]|$)/i,
  "$1127.0.0.1",
);

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
      ? LOCAL_AUTH
        ? storedSession?.token
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
      `Không nhận được phản hồi từ ${BASE_URL}. Lỗi này có thể do kết nối, CORS hoặc URL API. ${error.message}`,
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
