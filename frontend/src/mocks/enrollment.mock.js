import courses from "./courses.mock.json";
import { mockStorageKey } from "../api/session";
import { ApiError } from "../api/client";
const KEY = "learncloud.mock.enrollments.v1";
const PASSES = "learncloud.mock.checkpoint-passes.v1";
const read = (key) => JSON.parse(localStorage.getItem(mockStorageKey(key)) || "{}");
export const mockEnrollments = () => read(KEY);
export function mockEnroll(courseId) {
  const course = courses.find(c => String(c.id) === String(courseId) && c.status === "PUBLISHED");
  if (!course) throw new ApiError(404, "Kh?ng t?m th?y kh?a h?c ?? xu?t b?n.");
  const rows = read(KEY);
  if (!rows[courseId]) {
    rows[courseId] = { course_id: String(courseId), enrolled_at: new Date().toISOString() };
    localStorage.setItem(mockStorageKey(KEY), JSON.stringify(rows));
  }
  return rows[courseId];
}
export function mockPassedSections(courseId) {
  return read(PASSES)[courseId] || [];
}
export function mockRecordPass(courseId, sectionId) {
  const rows = read(PASSES);
  rows[courseId] = [...new Set([...(rows[courseId] || []), String(sectionId)])];
  localStorage.setItem(mockStorageKey(PASSES), JSON.stringify(rows));
}
export function mockUnlockedSections(course) {
  const passed = mockPassedSections(course.id);
  const unlocked = [];
  for (const section of course.sections ?? []) {
    unlocked.push(String(section.id));
    if (!passed.includes(String(section.id))) break;
  }
  return unlocked;
}
export function requireMockEnrollment(courseId, sectionId) {
  if (!read(KEY)[courseId]) throw new ApiError(403, "B?n c?n ??ng k? kh?a h?c tr??c khi h?c.");
  const course = courses.find(c => String(c.id) === String(courseId) && c.status === "PUBLISHED");
  if (!course) throw new ApiError(404, "Kh?a h?c ch?a ???c xu?t b?n.");
  if (sectionId != null && !mockUnlockedSections(course).includes(String(sectionId)))
    throw new ApiError(403, "H?y ??t checkpoint c?a section tr??c ?? m? b?i h?c n?y.");
  return course;
}
