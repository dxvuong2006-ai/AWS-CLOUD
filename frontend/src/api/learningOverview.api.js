import { request } from "./client";
export const getCompletion = courseId => request("/courses/" + encodeURIComponent(courseId) + "/completion");
export const getHistory = (offset = 0) => request("/students/me/checkpoint-history?offset=" + offset + "&limit=20");
export const getOverview = () => request("/students/me/learning-overview");
