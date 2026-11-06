import { request, ApiError } from "./client";
import courses from "../mocks/courses.mock.json";

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function normalizeId(value) {
  return value == null ? null : String(value);
}

function normalizeCourse(course) {
  return {
    ...course,
    id: normalizeId(course.id),
    instructor_id: normalizeId(course.instructor_id),
    description: course.description ?? "",
    learning_objectives: course.learning_objectives ?? [],
    sections: (course.sections ?? []).map((section) => ({
      ...section,
      id: normalizeId(section.id),
      course_id: normalizeId(section.course_id ?? course.id),
      lessons: (section.lessons ?? []).map((lesson) => ({
        ...lesson,
        id: normalizeId(lesson.id),
        section_id: normalizeId(lesson.section_id ?? section.id),
        duration_seconds:
          lesson.duration_seconds ?? lesson.duration ?? null,
      })),
    })),
  };
}

export async function fetchCourses() {
  let data;

  if (USE_MOCK) {
    await delay(300);
    data = courses;
  } else {
    // Backend hiện trả trực tiếp một mảng CourseResponse.
    data = await request("/courses");
  }

  return data.filter(course => course.status === "PUBLISHED").map(normalizeCourse);
}

export async function fetchCourseById(id) {
  const courseId = String(id);
  let data;

  if (USE_MOCK) {
    await delay(300);
    data = courses.find((course) => String(course.id) === courseId);

    if (!data) {
      throw new ApiError(404, "Không tìm thấy khóa học.");
    }
  } else {
    data = await request(`/courses/${encodeURIComponent(courseId)}`);
  }

  if (data.status !== "PUBLISHED") throw new ApiError(404, "Kh?a h?c ch?a ???c xu?t b?n.");
  return normalizeCourse(data);
}