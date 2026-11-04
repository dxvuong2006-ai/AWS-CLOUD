import { request } from "./client";

// Authentication always uses the real backend, including when lesson data is mocked.
export function loginUser(email, password) {
  return request("/auth/login", {
    method: "POST", auth: false, body: { email: email.trim(), password },
  });
}

export function fetchCurrentUser() {
  return request("/auth/me");
}
