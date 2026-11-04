import { request, ApiError } from "./client";
import lessons from "../mocks/lessons.mock.json";

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function normalizeLesson(lesson) {
  return {
    ...lesson,
    id: String(lesson.id),
    section_id:
      lesson.section_id == null ? null : String(lesson.section_id),

    // Backend hiện chưa trả các trường học liệu này.
    // Giữ dữ liệu mock nếu có; không lấy video mock thay cho bài thật.
    videoUrl: lesson.video_url ?? lesson.videoUrl ?? null,
    keyConcepts: lesson.key_concepts ?? lesson.keyConcepts ?? [],
    summary: lesson.summary ?? "",
    transcript: Array.isArray(lesson.transcript)
      ? lesson.transcript
      : [],
  };
}

export async function fetchLesson(lessonId) {
  const id = String(lessonId);
  let data;

  if (USE_MOCK) {
    await delay(300);
    data = lessons[id];

    if (!data) {
      throw new ApiError(404, "Không tìm thấy bài học.");
    }
  } else {
    data = await request(`/lessons/${encodeURIComponent(id)}`);
  }

  return normalizeLesson(data);
}