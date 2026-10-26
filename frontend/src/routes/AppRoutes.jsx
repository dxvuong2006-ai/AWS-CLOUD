import { Routes, Route, Navigate } from "react-router-dom";
import CourseListPage from "../pages/CourseListPage";
import CourseDetailPage from "../pages/CourseDetailPage";

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/courses" replace />} />
      <Route path="/courses" element={<CourseListPage />} />
      <Route path="/courses/:courseId" element={<CourseDetailPage />} />
      <Route
        path="*"
        element={<div className="page">Không tìm thấy trang.</div>}
      />
    </Routes>
  );
}
