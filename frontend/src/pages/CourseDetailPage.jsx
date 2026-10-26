import { useParams, Link } from "react-router-dom";
import { useCourse } from "../hooks/useCourses";
import CourseOutline from "../components/courses/CourseOutline";
import { useCourseProgress } from "../hooks/useCourseProgress";

export default function CourseDetailPage() {
  const { courseId } = useParams();
  const { data: course, loading, error } = useCourse(courseId);
  const progress = useCourseProgress(courseId);
  const completedIds = new Set(
    (progress?.lessons ?? []).filter((l) => l.completed).map((l) => l.lesson_id)
  );
  if (loading) return <div className="page">Đang tải...</div>;
  if (error) {
    return (
      <div className="page">
        <p>Không tải được khóa học.</p>
        <Link to="/courses">← Về danh sách</Link>
      </div>
    );
  }

  return (
    <div className="page">
      <Link to="/courses">← Về danh sách</Link>
      <h1 style={{ marginTop: 16 }}>{course.title}</h1>
      <p style={{ color: "var(--text-muted)" }}>{course.description}</p>
      <CourseOutline
        sections={course.sections}
        courseId={course.id}
        completedIds={completedIds}
      />
    </div>
  );
}
