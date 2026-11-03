import { request, ApiError } from "./client";
import courses from "../mocks/courses.mock.json";

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export async function fetchCourses() {
  if (USE_MOCK) {
    await delay(300);
    return courses;
  }
  return request("/courses");
}

export async function fetchCourseById(id) {
  if (USE_MOCK) {
    await delay(300);
    const course = courses.find((c) => c.id === id);
    if (!course) throw new ApiError(404);
    return course;
  }
  return request(`/courses/${id}`);
}

function sortByPosition(items) {
  if (!Array.isArray(items)) {
    throw new Error("API phải trả về một mảng Sections hoặc Lessons.");
  }
  return [...items].sort((a, b) => (a.position ?? 0) - (b.position ?? 0));
}

async function fetchSectionLessons(sectionId) {
  const limit = 100;
  const lessons = [];
  let page;
  do {
    page = await request(
      `/sections/${sectionId}/lessons?skip=${lessons.length}&limit=${limit}`
    );
    lessons.push(...sortByPosition(page));
  } while (page.length === limit);
  return sortByPosition(lessons);
}

export async function fetchCourseOutline(courseId) {
  if (USE_MOCK) {
    const course = await fetchCourseById(courseId);
    return sortByPosition(course.sections).map((section) => ({
      ...section,
      lessons: sortByPosition(section.lessons),
    }));
  }

  const sections = await request(`/courses/${courseId}/sections`);
  return Promise.all(
    sortByPosition(sections).map(async (section) => ({
      ...section,
      lessons: await fetchSectionLessons(section.id),
    }))
  );
}
