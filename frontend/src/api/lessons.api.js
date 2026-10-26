import { request, ApiError } from "./client";
import lessons from "../mocks/lessons.mock.json";

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
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