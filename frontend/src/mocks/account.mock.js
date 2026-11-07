// Development simulation only. Never use real passwords here.
import { ApiError } from "../api/client";
import { readSession } from "../api/session";

const KEY = "learncloud.mock.accounts.v1";
const TTL = 10 * 60 * 1000;
const COOLDOWN = 60 * 1000;
const MESSAGE = "Nếu email phù hợp, mã hướng dẫn đã được gửi. Vui lòng kiểm tra hộp thư.";
const emailKey = (email) => String(email).trim().toLowerCase();
const read = () => JSON.parse(localStorage.getItem(KEY) || '{"users":{},"codes":{}}');
const write = (data) => localStorage.setItem(KEY, JSON.stringify(data));
async function hash(value) {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(bytes), (b) => b.toString(16).padStart(2,"0")).join("");
}
async function passwordHash(password, salt) { return hash(salt + ":" + password); }
function validatePassword(password) {
  if (typeof password !== "string" || password.length < 8 || password.length > 128)
    throw new ApiError(422, "Mật khẩu phải có từ 8 đến 128 ký tự.");
}
function issue(data, email, purpose) {
  const key = purpose + ":" + email;
  const old = data.codes[key];
  const now = Date.now();
  if (old && now < old.nextAt) return old.nextAt;
  const windowStart = old && now - old.windowStart < 3600000 ? old.windowStart : now;
  const sends = windowStart === old?.windowStart ? old.sends : 0;
  if (sends >= 5) return windowStart + 3600000;
  data.codes[key] = { code: "123456", expiresAt: now + TTL, nextAt: now + COOLDOWN,
    attempts: 0, consumed: false, windowStart, sends: sends + 1 };
  return now + COOLDOWN;
}
function consume(data, email, purpose, code) {
  const row = data.codes[purpose + ":" + email];
  if (!row || row.consumed || Date.now() >= row.expiresAt || row.attempts >= 5)
    throw new ApiError(400, "Mã không hợp lệ hoặc đã hết hạn. Hãy yêu cầu mã mới.");
  if (row.code !== code) {
    row.attempts += 1; write(data);
    throw new ApiError(400, "Mã không hợp lệ hoặc đã hết hạn.");
  }
  row.consumed = true;
}
function publicUser(user) {
  return { id: user.id, name: user.name, email: user.email, role: "STUDENT" };
}
function current(data) {
  const token = readSession()?.token;
  const user = Object.values(data.users).find((u) => token === `mock:${u.id}:${u.version}`);
  if (!user || !user.verified) throw new ApiError(401, "Phiên đăng nhập đã hết hạn.");
  return user;
}
export async function accountMock(action, payload = {}) {
  const data = read();
  const email = emailKey(payload.email ?? "");
  if (action === "register") {
    if (!payload.name?.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
      throw new ApiError(422, "Vui lòng kiểm tra họ tên và email.");
    validatePassword(payload.password);
    if (data.users[email]) throw new ApiError(409, "Email đã được đăng ký.");
    const salt = crypto.randomUUID();
    data.users[email] = { id: crypto.randomUUID(), name: payload.name.trim(), email,
      salt, hash: await passwordHash(payload.password, salt), verified: false, version: 0 };
    const nextAt = issue(data, email, "verify"); write(data);
    return { verification_required: true, message: "Mã xác minh mô phỏng đã sẵn sàng.", retry_after: Math.ceil((nextAt-Date.now())/1000) };
  }
  if (action === "resend" || action === "forgot") {
    const nextAt = issue(data, email, action === "resend" ? "verify" : "reset");
    write(data);
    return { message: MESSAGE, retry_after: Math.max(0, Math.ceil((nextAt-Date.now())/1000)) };
  }
  if (action === "verify") {
    consume(data, email, "verify", payload.code);
    if (!data.users[email]) throw new ApiError(400, "Mã không hợp lệ hoặc đã hết hạn.");
    data.users[email].verified = true; write(data);
    return { message: "Đã xác minh email." };
  }
  if (action === "reset") {
    validatePassword(payload.password);
    consume(data, email, "reset", payload.code);
    const user = data.users[email];
    if (!user?.verified) throw new ApiError(400, "Mã không hợp lệ hoặc đã hết hạn.");
    user.hash = await passwordHash(payload.password, user.salt);
    user.version += 1; write(data);
    return { message: "Đã đặt lại mật khẩu." };
  }
  if (action === "login") {
    const user = data.users[email];
    if (!user || await passwordHash(payload.password, user.salt) !== user.hash)
      throw new ApiError(401, "Email hoặc mật khẩu không đúng.");
    if (!user.verified) throw new ApiError(403, "Email chưa được xác minh.");
    return { user: publicUser(user), access_token: `mock:${user.id}:${user.version}`, expires_in: 3600 };
  }
  const user = current(data);
  if (action === "me") return publicUser(user);
  if (action === "profile") {
    if (!payload.name?.trim()) throw new ApiError(422, "Họ tên không được để trống.");
    user.name = payload.name.trim(); write(data); return publicUser(user);
  }
  if (action === "password") {
    validatePassword(payload.new_password);
    if (await passwordHash(payload.current_password, user.salt) !== user.hash)
      throw new ApiError(400, "Mật khẩu hiện tại không đúng.");
    if (payload.current_password === payload.new_password)
      throw new ApiError(400, "Mật khẩu mới phải khác mật khẩu hiện tại.");
    user.hash = await passwordHash(payload.new_password, user.salt);
    user.version += 1; write(data); return { message: "Đã đổi mật khẩu." };
  }
  throw new ApiError(400, "Thao tác không hợp lệ.");
}
