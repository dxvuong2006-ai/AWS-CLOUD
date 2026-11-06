import { request, ApiError } from "./client";
import { accountMock } from "../mocks/account.mock";

export const AUTH_MOCK = import.meta.env.VITE_USE_AUTH_MOCK === "true";
function call(action, path, body, method = "POST", auth = false) {
  if (AUTH_MOCK) {
    if (import.meta.env.VITE_USE_MOCK !== "true")
      return Promise.reject(new ApiError(400, "Auth mock yêu cầu VITE_USE_MOCK=true."));
    return accountMock(action, body);
  }
  return request(path, { method, body, auth });
}
export const loginUser = (email, password) =>
  call("login", "/auth/login", { email: email.trim(), password });
export const fetchCurrentUser = () => call("me", "/auth/me", undefined, "GET", true);
// Explicit payload prevents role escalation even if a form gains unexpected fields.
export const registerStudent = ({ name, email, password }) =>
  call("register", "/auth/register", { name: name.trim(), email: email.trim(), password });
export const verifyEmail = (email, code) => call("verify", "/auth/verify-email", { email, code });
export const resendVerification = (email) => call("resend", "/auth/resend-verification", { email });
export const forgotPassword = (email) => call("forgot", "/auth/forgot-password", { email });
export const resetPassword = (email, code, password) =>
  call("reset", "/auth/reset-password", { email, code, password });
export const updateProfile = (name) => call("profile", "/auth/me", { name: name.trim() }, "PATCH", true);
export const changePassword = (current_password, new_password) =>
  call("password", "/auth/change-password", { current_password, new_password }, "POST", true);
