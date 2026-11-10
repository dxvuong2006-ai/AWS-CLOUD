import { request, ApiError } from "./client";
import { signInWithCognito, signOutFromCognito } from "./cognito";
import { LOCAL_AUTH } from "../config/auth";
import { readSession } from "./session";

export const AUTH_MOCK = LOCAL_AUTH;
function call(path, body, method = "POST", auth = false) {
  const endpoint = LOCAL_AUTH && path !== "/auth/me"
    ? path.replace("/auth/", "/auth/local/") : path;
  return request(endpoint, { method, body, auth });
}
export const loginUser = (email, password) => {
  const normalizedEmail = email.trim().toLowerCase();
  if (LOCAL_AUTH) return call("/auth/login", { email: normalizedEmail, password });
  return signInWithCognito(normalizedEmail, password);
};
export const logoutUser = () => LOCAL_AUTH
  ? (readSession() ? request("/auth/local/logout", { method: "POST" }) : Promise.resolve())
  : signOutFromCognito();
export const fetchCurrentUser = () => call("/auth/me", undefined, "GET", true);
// Explicit payload prevents role escalation even if a form gains unexpected fields.
export const registerStudent = ({ name, email, password }) =>
  call("/auth/register", { name: name.trim(), email: email.trim().toLowerCase(), password });
const normalizeVerificationCode = (code) => String(code ?? "").replace(/\D/g, "");
export const verifyEmail = (email, code) => {
  const normalizedCode = normalizeVerificationCode(code);
  if (!/^\d{6}$/.test(normalizedCode))
    return Promise.reject(new ApiError(422, "Mã xác thực phải gồm đúng 6 chữ số."));
  return call("/auth/verify-email", {
    email: email.trim().toLowerCase(),
    code: normalizedCode,
  });
};
export const resendVerification = (email) => call("/auth/resend-verification", {
  email: email.trim().toLowerCase(),
});
export const forgotPassword = (email) => call("/auth/forgot-password", {
  email: email.trim().toLowerCase(),
});
export const resetPassword = (email, code, password) => {
  const normalizedCode = normalizeVerificationCode(code);
  if (!/^\d{6}$/.test(normalizedCode))
    return Promise.reject(new ApiError(422, "Mã xác thực phải gồm đúng 6 chữ số."));
  return call("/auth/reset-password", {
    email: email.trim().toLowerCase(),
    code: normalizedCode,
    password,
  });
};
export const updateProfile = (name) => call("/auth/me", { name: name.trim() }, "PATCH", true);
export const changePassword = (current_password, new_password) =>
  call("/auth/change-password", { current_password, new_password }, "POST", true);
