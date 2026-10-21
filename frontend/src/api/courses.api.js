import { request } from "./client";
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
    if (!course) throw new Error("HTTP 404");
    return course;
  }
  return request(`/courses/${id}`);
}