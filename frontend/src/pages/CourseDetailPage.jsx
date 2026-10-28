import { useParams, Link } from "react-router-dom";
import { useCourse, useCourseOutline } from "../hooks/useCourses";
import CourseOutline from "../components/courses/CourseOutline";
import { useCourseProgress } from "../hooks/useCourseProgress";

function errorMessage(error, resource) {
  if (error.status === 401) return "Vui lòng đăng nhập lại để xem khóa học (401).";
  if (error.status === 403) return "Bạn chưa có quyền xem nội dung này. Hãy kiểm tra quyền truy cập hoặc đăng ký khóa học (403).";
  if (error.status === 404) return `Không tìm thấy ${resource} (404).`;
  if (error.status >= 500) return "Máy chủ đang gặp lỗi. Vui lòng thử lại sau.";
  return `Không tải được ${resource}. Vui lòng thử lại.`;
}

export default function CourseDetailPage() {
  const { courseId } = useParams();
  const { data: course, loading, error } = useCourse(courseId);
  const outline = useCourseOutline(courseId);
  const progress = useCourseProgress(courseId);
  const completedIds = new Set(
    (progress?.lessons ?? []).filter((l) => l.completed).map((l) => l.lesson_id)
  );
  if (loading) return <div className="page">Đang tải...</div>;
  if (error) {
    return (
      <div className="page">
        <p role="alert">{errorMessage(error, "khóa học")}</p>
        <Link to="/courses">← Về danh sách</Link>
      </div>
    );
  }

  return (
    <div className="page">
      <Link to="/courses">← Về danh sách</Link>
      <h1 style={{ marginTop: 16 }}>{course.title}</h1>
      <p style={{ color: "var(--text-muted)" }}>{course.description}</p>
      {outline.loading ? (
        <p role="status">Đang tải nội dung khóa học...</p>
      ) : outline.error ? (
        <p role="alert">{errorMessage(outline.error, "nội dung khóa học")}</p>
      ) : (
        <CourseOutline
          sections={outline.data}
          courseId={course.id}
          completedIds={completedIds}
        />
      )}
    </div>
  );
}
