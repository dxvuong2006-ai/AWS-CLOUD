import { request, ApiError } from "./client";
import lessons from "../mocks/lessons.mock.json";

export const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export async function fetchLesson(lessonId) {
  if (USE_MOCK) {
    await delay(300);
    const lesson = lessons[lessonId];
    if (!lesson) throw new ApiError(404);
    return lesson;
  }
  return request(`/lessons/${lessonId}`);
}

export async function fetchLessonVideoUrl(lessonId) {
  // Mock lessons retain their local videoUrl and never request an S3 URL.
  if (USE_MOCK) return null;
  return request(`/lessons/${lessonId}/video-url`, { cache: "no-store" });
}
