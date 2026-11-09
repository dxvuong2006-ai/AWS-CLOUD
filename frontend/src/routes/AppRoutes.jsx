import { Routes, Route, Navigate, Link } from "react-router-dom";
import TutorPage from "../pages/TutorPage";
import CourseCompletePage from "../pages/CourseCompletePage";
import VideoUploadPage from "../pages/VideoUploadPage";
import MyCoursesPage from "../pages/MyCoursesPage";
import CourseListPage from "../pages/CourseListPage";
import CourseDetailPage from "../pages/CourseDetailPage";
import LearningPage from "../pages/LearningPage";
import SectionPage from "../pages/SectionPage";
import FlashcardPage from "../pages/FlashcardPage";
import CheckpointPage from "../pages/CheckpointPage";
import CheckpointResultPage from "../pages/CheckpointResultPage";
import ProgressPage from "../pages/ProgressPage";
import InstructorDashboardPage from "../pages/InstructorDashboardPage";
import InstructorCoursesPage from "../pages/InstructorCoursesPage";
import CourseEditorPage from "../pages/CourseEditorPage";
import ReviewQueuePage from "../pages/ReviewQueuePage";
import LessonReviewPage from "../pages/LessonReviewPage";
import StudentReportPage from "../pages/StudentReportPage";
import AdminUsersPage from "../pages/AdminUsersPage";
import AdminMonitoringPage from "../pages/AdminMonitoringPage";
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
  return <div className="page forbidden-page"><section className="forbidden-card"><div className="forbidden-icon">♙</div><h1>Bạn không có quyền truy cập</h1><p>Trang này dành cho vai trò khác. Hãy quay lại trang chính của bạn.</p>
    <Link className="btn-primary" to={homeForRole(user.role)}>⌂ &nbsp;Về trang chính</Link></section></div>;
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
        <Route path="/flashcards" element={<FlashcardPage />} />
        <Route path="/courses/:courseId/sections/:sectionId/lessons/:lessonId/flashcards" element={<FlashcardPage />} />
        <Route path="/progress" element={<ProgressPage />} />
        <Route path="/tutor/attempts/:attemptId" element={<TutorPage />} />
        <Route path="/courses/:courseId/completed" element={<CourseCompletePage />} />
      </Route>
      <Route element={<ProtectedRoute roles={["INSTRUCTOR"]} />}>
        <Route path="/instructor/dashboard" element={<InstructorDashboardPage />} />
        <Route path="/instructor/courses" element={<InstructorCoursesPage />} />
        <Route path="/instructor/courses/new" element={<CourseEditorPage />} />
        <Route path="/instructor/courses/:courseId/lessons/:lessonId/upload" element={<VideoUploadPage />} />
        <Route path="/instructor/courses/:courseId/edit" element={<CourseEditorPage />} />
        <Route path="/instructor/review-queue" element={<ReviewQueuePage />} />
        <Route path="/instructor/review/:lessonId" element={<LessonReviewPage />} />
        <Route path="/instructor/student-report" element={<StudentReportPage />} />
        <Route path="/instructor/students/:studentId" element={<StudentReportPage />} />
        <Route path="/instructor/settings" element={<ProfilePage />} />
      </Route>
      <Route element={<ProtectedRoute roles={["ADMIN"]} />}>
        <Route path="/admin/users" element={<AdminUsersPage />} />
        <Route path="/admin/users/new" element={<AdminUsersPage />} />
        <Route path="/admin/users/success" element={<AdminUsersPage />} />
        <Route path="/admin/users/:userId/edit" element={<AdminUsersPage />} />
        <Route path="/admin/roles" element={<AdminUsersPage />} />
        <Route path="/admin/monitoring" element={<AdminMonitoringPage />} />
      </Route>
    </Routes>
  );
}
