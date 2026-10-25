import { useParams, Link } from "react-router-dom";
import { useCourse } from "../hooks/useCourses";
import CourseOutline from "../components/courses/CourseOutline";

export default function CourseDetailPage() {
  const { courseId } = useParams();
  const { data: course, loading, error } = useCourse(courseId);

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
      <CourseOutline sections={course.sections} courseId={course.id} />
    </div>
  );
}
