const BASE_URL = (
  import.meta.env.VITE_API_URL || "http://localhost:8000"
).replace(/\/+$/, "");

export async function request(path, { method = "GET", body, demoUser } = {}) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const res = await fetch(`${BASE_URL}${normalizedPath}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(demoUser && { "X-Demo-User": demoUser }),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}