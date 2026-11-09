import { request } from "./client";

export const listReviewQueue = () => request("/instructor/review-queue");
export const fetchLessonContent = (lessonId) => request(`/lessons/${lessonId}/content`);
export const fetchReviewDraft = (lessonId) => request(`/lessons/${lessonId}/review-draft`);
export const updateReviewDraft = (lessonId, payload) =>
  request(`/lessons/${lessonId}/review-draft`, { method: "PUT", body: payload });
export const approveReviewDraft = (lessonId, payload) =>
  request(`/lessons/${lessonId}/review-draft/approvals`, { method: "POST", body: payload });
