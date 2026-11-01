import { Routes, Route, Navigate } from "react-router-dom";
import CourseListPage from "../pages/CourseListPage";
import CourseDetailPage from "../pages/CourseDetailPage";
import LearningPage from "../pages/LearningPage";
import CheckpointPage from "../pages/CheckpointPage";
export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/courses" replace />} />
      <Route path="/courses" element={<CourseListPage />} />
      <Route path="/courses/:courseId" element={<CourseDetailPage />} />
      <Route path="/courses/:courseId/lessons/:lessonId" element={<LearningPage />} />
      <Route path="*" element={<div className="page">Không tìm thấy trang.</div>} />
      <Route
        path="/courses/:courseId/sections/:sectionId/checkpoint"
        element={<CheckpointPage />}
      />
    </Routes>
  );
}