import { Link } from "react-router-dom";

const STATUS_LABEL = {
  PUBLISHED: "Đã publish",
  DRAFT: "Bản nháp",
};

export default function CourseCard({ course }) {
  return (
    <div className="card">
      <h3 style={{ fontSize: 15, margin: "0 0 8px" }}>{course.title}</h3>
      <p style={{ color: "var(--text-muted)", margin: "0 0 12px" }}>
        {course.description}
      </p>
      <p style={{ margin: "0 0 16px" }}>
        {course.lessons} bài học · {STATUS_LABEL[course.status] ?? course.status}
      </p>
      <Link to={`/courses/${course.id}`} className="btn-primary">
        Xem chi tiết
      </Link>
    </div>
  );
}