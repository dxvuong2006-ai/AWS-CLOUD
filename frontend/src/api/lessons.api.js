import { request, ApiError } from "./client";
import { mockStorageKey } from "./session";
import { requireMockEnrollment } from "../mocks/enrollment.mock";
import lessons from "../mocks/lessons.mock.json";
import courses from "../mocks/courses.mock.json";
const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
function mockLesson(id, courseId) {
  const course = courses.find(c => String(c.id) === String(courseId));
  const section = course?.sections.find(s => s.lessons.some(l => String(l.id) === String(id)));
  if (!section || !lessons[id]) throw new ApiError(404, "Không tìm thấy bài học trong khóa học.");
  requireMockEnrollment(courseId, section.id);
  return lessons[id];
}
export function normalizeLesson(data) {
  // Require an explicit publication marker; never display an unreviewed draft.
  if (data.publication_status !== "PUBLISHED") throw new ApiError(403, "Học liệu chưa được xuất bản.");
  if (data.processing_status === "FAILED") throw new ApiError(422, "Video xử lý thất bại. Vui lòng quay lại sau.");
  if (data.processing_status !== "READY") throw new ApiError(409, "Video đang được xử lý hoặc chưa sẵn sàng.");
  return {
    id: String(data.id), section_id: String(data.section_id), course_id: String(data.course_id), title: data.title,
    summary: typeof data.summary === "string" ? data.summary : "",
    keyConcepts: (data.key_concepts ?? []).filter(value => typeof value === "string"),
    transcript: (Array.isArray(data.transcript) ? data.transcript : [])
      .filter(s => Number.isFinite(s.start) && s.start >= 0 && typeof s.text === "string")
      .map(s => ({ start: s.start, text: s.text })).sort((a,b) => a.start-b.start),
  };
}
export async function fetchLesson(lessonId, courseId) {
  const data = USE_MOCK ? mockLesson(lessonId, courseId)
    : await request(`/lessons/${encodeURIComponent(lessonId)}/content`);
  if (String(data.course_id) !== String(courseId)) throw new ApiError(404, "Bài học không thuộc khóa học này.");
  return normalizeLesson(data);
}
export async function fetchLessonVideo(lessonId, courseId) {
  const account = mockStorageKey("media");
  let result;
  if (USE_MOCK) {
    const data = mockLesson(lessonId, courseId); normalizeLesson(data);
    result = { video_url: data.videoUrl, expires_at: null };
  } else {
    result = await request(`/lessons/${encodeURIComponent(lessonId)}/video-url`);
  }
  if (account !== mockStorageKey("media")) throw new ApiError(401, "Phiên đăng nhập đã thay đổi.");
  if (typeof result.video_url !== "string" || !result.video_url ||
      !(result.video_url.startsWith("/") || /^https?:\/\//.test(result.video_url)))
    throw new ApiError(502, "Chưa có URL video hợp lệ.");
  const expiresAt = result.expires_at == null ? null : Date.parse(result.expires_at);
  if (expiresAt != null && (!Number.isFinite(expiresAt) || expiresAt <= Date.now()))
    throw new ApiError(502, "URL video đã hết hạn. Hãy thử lại.");
  return { videoUrl: result.video_url, expiresAt };
}
