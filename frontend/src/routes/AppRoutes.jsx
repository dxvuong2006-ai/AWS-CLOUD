import { Routes, Route, Navigate, Link } from "react-router-dom";
import MyCoursesPage from "../pages/MyCoursesPage";
import CourseListPage from "../pages/CourseListPage";
import CourseDetailPage from "../pages/CourseDetailPage";
import LearningPage from "../pages/LearningPage";
import SectionPage from "../pages/SectionPage";
import CheckpointPage from "../pages/CheckpointPage";
import CheckpointResultPage from "../pages/CheckpointResultPage";
import { RegisterPage, VerifyEmailPage, RegisterSuccessPage, ForgotPasswordPage, ResetPasswordPage, ProfilePage } from "../pages/AccountPages";
import LoginPage from "../pages/LoginPage";
import ProtectedRoute from "./ProtectedRoute";
import { useAuth } from "../context/AuthContext";
import { homeForRole } from "../utils/roles";

function Home() {
  const { user } = useAuth();
  return <Navigate to={homeForRole(user.role)} replace />;
}

function Pending({ title }) {
  return <div className="page"><h1>{title}</h1><p>Chức năng đang được xây dựng.</p></div>;
}

function Forbidden() {
  const { user } = useAuth();
  return <div className="page"><h1>Không có quyền truy cập</h1>
    <Link to={homeForRole(user.role)}>Về trang chính</Link></div>;
}

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />
      <Route path="/register-success" element={<RegisterSuccessPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<Home />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/forbidden" element={<Forbidden />} />
        <Route path="*" element={<div className="page">Không tìm thấy trang.</div>} />
      </Route>
      <Route element={<ProtectedRoute roles={["STUDENT"]} />}>
        <Route path="/courses" element={<CourseListPage />} />
        <Route path="/courses/:courseId" element={<CourseDetailPage />} />
        <Route path="/courses/:courseId/lessons/:lessonId" element={<LearningPage />} />
        <Route path="/courses/:courseId/sections/:sectionId" element={<SectionPage />} />
        <Route path="/courses/:courseId/sections/:sectionId/checkpoint" element={<CheckpointPage />} />
        <Route path="/checkpoint-results/:quizId/:attemptId" element={<CheckpointResultPage />} />
        <Route path="/my-courses" element={<MyCoursesPage />} />
        <Route path="/flashcards" element={<Pending title="Flashcard" />} />
        <Route path="/progress" element={<Pending title="Tiến độ" />} />
      </Route>
      <Route element={<ProtectedRoute roles={["INSTRUCTOR"]} />}>
        <Route path="/instructor/dashboard" element={<Pending title="Tổng quan giảng viên" />} />
        <Route path="/instructor/courses" element={<Pending title="Khóa học giảng viên" />} />
        <Route path="/instructor/review-queue" element={<Pending title="Học liệu AI" />} />
        <Route path="/instructor/student-report" element={<Pending title="Học viên và báo cáo" />} />
        <Route path="/instructor/settings" element={<Pending title="Cài đặt giảng viên" />} />
      </Route>
      <Route element={<ProtectedRoute roles={["ADMIN"]} />}>
        <Route path="/admin/users" element={<Pending title="Quản trị tài khoản" />} />
        <Route path="/admin/roles" element={<Pending title="Vai trò và quyền" />} />
        <Route path="/admin/monitoring" element={<Pending title="Giám sát hệ thống" />} />
      </Route>
    </Routes>
  );
}
