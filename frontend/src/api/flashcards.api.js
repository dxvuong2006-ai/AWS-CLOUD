import { request, ApiError } from "./client";
import { mockStorageKey } from "./session";
import { requireMockEnrollment } from "../mocks/enrollment.mock";
import lessons from "../mocks/lessons.mock.json";
const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

export function normalizeFlashcards(data, courseId, sectionId, lessonId) {
  if (String(data?.course_id) !== String(courseId) || String(data?.section_id) !== String(sectionId) ||
      String(data?.lesson_id) !== String(lessonId)) throw new ApiError(502, "Bộ thẻ không khớp bài học.");
  if (data.publication_status !== "PUBLISHED") throw new ApiError(403, "Flashcard chưa được xuất bản.");
  if (!Array.isArray(data.cards) || !data.revision) throw new ApiError(502, "Dữ liệu flashcard không hợp lệ.");
  const ids = new Set();
  const cards = data.cards.map(card => {
    if (card.id == null || ids.has(String(card.id)) || typeof card.front !== "string" || !card.front.trim() ||
        typeof card.back !== "string" || !card.back.trim()) throw new ApiError(502, "Nội dung flashcard không hợp lệ.");
    ids.add(String(card.id));
    return { id: String(card.id), front: card.front, back: card.back,
      sourceSeconds: Number.isFinite(card.source_seconds) && card.source_seconds >= 0 ? card.source_seconds : null };
  });
  return { revision: String(data.revision), cards };
}

export async function fetchFlashcards(courseId, sectionId, lessonId) {
  const account = mockStorageKey("flashcards");
  let data;
  if (USE_MOCK) {
    const course = requireMockEnrollment(courseId, sectionId);
    const section = course.sections.find(row => String(row.id) === String(sectionId));
    const lesson = lessons[lessonId];
    if (!section?.lessons.some(row => String(row.id) === String(lessonId)) || !lesson)
      throw new ApiError(404, "Không tìm thấy bài học.");
    data = { course_id: courseId, section_id: sectionId, lesson_id: lessonId,
      publication_status: lesson.publication_status, revision: "demo-1",
      cards: (lesson.key_concepts ?? []).map((concept, index) => ({
        id: `${lessonId}-${index}`, front: concept, back: lesson.summary,
      })) };
  } else data = await request(`/lessons/${encodeURIComponent(lessonId)}/flashcards`);
  if (account !== mockStorageKey("flashcards")) throw new ApiError(401, "Phiên đăng nhập đã thay đổi.");
  return normalizeFlashcards(data, courseId, sectionId, lessonId);
}
