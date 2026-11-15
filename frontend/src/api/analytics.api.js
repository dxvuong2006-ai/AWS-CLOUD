import { request } from "./client";

export const fetchInstructorDashboard = () => request("/instructor/dashboard");
export const listReportCourses = () => request("/instructor/courses");
export const listInstructorStudents = (courseId) => request(
  `/instructor/students${courseId ? `?course_id=${encodeURIComponent(courseId)}` : ""}`,
);
export const fetchInstructorStudent = (studentId) => request(`/instructor/students/${studentId}`);
