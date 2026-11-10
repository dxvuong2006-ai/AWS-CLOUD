import { request, ApiError } from "./client";
import { accountMock } from "../mocks/account.mock";
import { signInWithCognito } from "./cognito";

export const AUTH_MOCK = import.meta.env.VITE_USE_AUTH_MOCK === "true";
function call(action, path, body, method = "POST", auth = false) {
  if (AUTH_MOCK) {
    if (import.meta.env.VITE_USE_MOCK !== "true")
      return Promise.reject(new ApiError(400, "Auth mock yêu cầu VITE_USE_MOCK=true."));
    return accountMock(action, body);
  }
  return request(path, { method, body, auth });
}
export const loginUser = (email, password) => {
  const normalizedEmail = email.trim().toLowerCase();
  if (AUTH_MOCK) return call("login", "", { email: normalizedEmail, password });
  return signInWithCognito(normalizedEmail, password);
};
export const fetchCurrentUser = () => call("me", "/auth/me", undefined, "GET", true);
// Explicit payload prevents role escalation even if a form gains unexpected fields.
export const registerStudent = ({ name, email, password }) =>
  call("register", "/auth/register", { name: name.trim(), email: email.trim(), password });
const normalizeVerificationCode = (code) => String(code ?? "").replace(/\D/g, "");
export const verifyEmail = (email, code) => {
  const normalizedCode = normalizeVerificationCode(code);
  if (!/^\d{6}$/.test(normalizedCode))
    return Promise.reject(new ApiError(422, "Mã xác thực phải gồm đúng 6 chữ số."));
  return call("verify", "/auth/verify-email", {
    email: email.trim().toLowerCase(),
    code: normalizedCode,
  });
};
export const resendVerification = (email) => call("resend", "/auth/resend-verification", {
  email: email.trim().toLowerCase(),
});
export const forgotPassword = (email) => call("forgot", "/auth/forgot-password", {
  email: email.trim().toLowerCase(),
});
export const resetPassword = (email, code, password) => {
  const normalizedCode = normalizeVerificationCode(code);
  if (!/^\d{6}$/.test(normalizedCode))
    return Promise.reject(new ApiError(422, "Mã xác thực phải gồm đúng 6 chữ số."));
  return call("reset", "/auth/reset-password", {
    email: email.trim().toLowerCase(),
    code: normalizedCode,
    password,
  });
};
export const updateProfile = (name) => call("profile", "/auth/me", { name: name.trim() }, "PATCH", true);
export const changePassword = (current_password, new_password) =>
  call("password", "/auth/change-password", { current_password, new_password }, "POST", true);
