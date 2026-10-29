const BASE_URL = (
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(status, detail, code) {
    super(detail || `HTTP ${status}`);
    this.status = status;
    this.code = code;
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

export async function request(path, { method = "GET", body, cache } = {}) {
  const token = getAccessToken();
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const res = await fetch(`${BASE_URL}${normalizedPath}`, {
    method,
    cache,
    headers: {
      "Content-Type": "application/json",
      ...(token && { Authorization: `Bearer ${token}` }),
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let detail = "";
    let code;
    try {
      const data = await res.json();
      detail = typeof data.detail === "string" ? data.detail : "";
      code = data.code;
    } catch {
      // response không phải JSON, bỏ qua
    }
    throw new ApiError(res.status, detail, code);
  }
  return res.status === 204 ? null : res.json();
}
