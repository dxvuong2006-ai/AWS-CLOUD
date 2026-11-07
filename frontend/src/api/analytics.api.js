import { request } from "./client";

export const fetchInstructorDashboard = () => request("/instructor/dashboard");
export const listInstructorStudents = () => request("/instructor/students");
export const fetchInstructorStudent = (studentId) => request(`/instructor/students/${studentId}`);
