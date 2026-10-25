const BASE_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `HTTP ${status}`);
    this.status = status;
  }
}

export async function request(path, { method = "GET", body, demoUser } = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(demoUser && { "X-Demo-User": demoUser }),
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