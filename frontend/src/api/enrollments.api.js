import { request, ApiError } from "./client";
import { mockStorageKey } from "./session";
import { fetchCourseProgress } from "./progress.api";
import { fetchCourseById } from "./courses.api";
import { mockEnrollments, mockEnroll, mockUnlockedSections, mockPassedSections } from "../mocks/enrollment.mock";
const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
function normalize(row) {
  if (!row?.course?.id) throw new ApiError(502, "D? li?u ??ng k? h?c kh?ng h?p l?.");
  return { ...row, course: { ...row.course, id: String(row.course.id) },
    resume_lesson_id: row.resume_lesson_id == null ? null : String(row.resume_lesson_id),
    unlocked_section_ids: (row.unlocked_section_ids ?? []).map(String) };
}
export async function fetchMyCourses() {
  if (!USE_MOCK) {
    const data = await request("/students/me/courses");
    if (!Array.isArray(data)) throw new ApiError(502, "D? li?u kh?a h?c kh?ng h?p l?.");
    return data.map(normalize);
  }
  const accountKey = mockStorageKey("learncloud.mock.progress.v2");
  const saved = JSON.parse(localStorage.getItem(accountKey) || "{}");
  const rows = await Promise.all(Object.values(mockEnrollments()).map(async row => {
    const course = await fetchCourseById(row.course_id);
    const progress = await fetchCourseProgress(course.id);
    const unlocked = mockUnlockedSections(course);
    const available = course.sections.filter(s => unlocked.includes(s.id)).flatMap(s => s.lessons);
    const recent = available.filter(l => saved[l.id]?.updated_at)
      .sort((a,b) => saved[b.id].updated_at - saved[a.id].updated_at)[0];
    const started = progress.lessons.some(l => l.watched_seconds > 0);
    const completed = course.sections.length > 0 && course.sections.every(s => mockPassedSections(course.id).includes(s.id)) && progress.lessons.every(l => l.completed);
    return { ...row, course, progress_percent: progress.overall_percent,
      status: completed ? "COMPLETED" : started ? "IN_PROGRESS" : "NOT_STARTED",
      resume_lesson_id: recent?.id ?? available[0]?.id ?? null,
      unlocked_section_ids: unlocked };
  }));
  if (accountKey !== mockStorageKey("learncloud.mock.progress.v2")) throw new ApiError(401, "Phi?n ??ng nh?p ?? thay ??i.");
  return rows;
}
export async function enrollCourse(courseId) {
  if (USE_MOCK) return mockEnroll(courseId);
  return request(`/courses/${encodeURIComponent(courseId)}/enroll`, { method: "POST" });
}
export const enrollmentError = (error) => [404, 405, 501].includes(error?.status)
  ? "Ch?c n?ng ??ng k? h?c ch?a ???c k?t n?i ??y ??. Vui l?ng th? l?i sau."
  : error?.message || "Kh?ng t?i ???c ??ng k? h?c. Vui l?ng th? l?i.";
