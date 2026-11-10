import { request } from "./client";
export const startRemediation = (attemptId, regenerate = false) => {
  if (!/^\d+$/.test(String(attemptId))) return Promise.reject(new Error("Ôn tập AI cần tài khoản và lượt làm trên API thật. Lượt làm demo không được gửi lên server."));
  return request("/student/remediation", { method: "POST", body: { attempt_id: Number(attemptId), regenerate } });
};
export const getRemediation = sessionId => request("/student/remediation/" + encodeURIComponent(sessionId));
export const advanceRemediation = (sessionId, kind, itemId) => request("/student/remediation/" + encodeURIComponent(sessionId) + "/advance", { method: "POST", body: { kind, item_id: String(itemId) } });
export const submitPractice = (sessionId, answers) => request("/student/remediation/" + encodeURIComponent(sessionId) + "/practice", { method: "POST", body: { answers } });
