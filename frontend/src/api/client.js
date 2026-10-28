const BASE_URL = (
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `HTTP ${status}`);
    this.status = status;
  }
}

function getAccessToken() {
  for (const storageName of ["sessionStorage", "localStorage"]) {
    try {
      const token = globalThis[storageName]?.getItem("access_token")?.trim();
      if (token) return token;
    } catch {
      // Trình duyệt có thể chặn storage; vẫn cho phép gọi API công khai.
    }
  }
  return null;
}

export async function request(path, { method = "GET", body } = {}) {
  const token = getAccessToken();
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const res = await fetch(`${BASE_URL}${normalizedPath}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token && { Authorization: `Bearer ${token}` }),
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let detail = "";
    try {
      const data = await res.json();
      detail = typeof data.detail === "string" ? data.detail : "";
    } catch {
      // response không phải JSON, bỏ qua
    }
    throw new ApiError(res.status, detail);
  }
  return res.status === 204 ? null : res.json();
}
