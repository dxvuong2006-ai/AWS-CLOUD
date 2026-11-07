import { request } from "./client";
import courses from "../mocks/courses.mock.json";
const COMPLETE_AT_PERCENT = 95 // xem từ mức này trở lên là hoàn thành
const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
const STORE_KEY = "learncloud.mock.progress";
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function readStore() {
  try {
    return JSON.parse(localStorage.getItem(STORE_KEY)) ?? {};
  } catch {
    return {};
  }
}

function writeStore(store) {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(store));
  } catch {
    // trình duyệt chặn lưu thì bỏ qua
  }
}

// Mô phỏng response của GET /courses/{id}/progress 
function buildCourseProgress(courseId) {
  const course = courses.find((c) => c.id === courseId);
  const store = readStore();
  const lessons = (course?.sections ?? [])
    .flatMap((s) => s.lessons)
    .map((l) => {
      const saved = store[l.id] ?? { progress_percent: 0, last_position_seconds: 0 };
      return {
        lesson_id: l.id,
        progress_percent: saved.progress_percent,
        last_position_seconds: saved.last_position_seconds,
        completed: saved.progress_percent >= COMPLETE_AT_PERCENT, // ngưỡng thời lượng video để hoàn thành bài học đó
      };
    });
  const total = lessons.reduce((sum, l) => sum + l.progress_percent, 0);
  return {
    course_id: courseId,
    overall_percent: lessons.length ? Math.round(total / lessons.length) : 0,
    lessons,
  };
}

export async function fetchCourseProgress(courseId) {
  if (USE_MOCK) {
    await delay(150);
    return buildCourseProgress(courseId);
  }
  return request(`/courses/${courseId}/progress`);
}

export async function saveLessonProgress(lessonId, { progressPercent, lastPositionSeconds }) {
  const body = {
    progress_percent: progressPercent,
    last_position_seconds: lastPositionSeconds,
  };
  if (USE_MOCK) {
    await delay(100);
    const store = readStore();
    store[lessonId] = body;
    writeStore(store);
    return body;
  }
  return request(`/lessons/${lessonId}/progress`, { method: "PUT", body });
}