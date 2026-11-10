import "../styles/student.css";
import { useState } from "react";
import { useCourses } from "../hooks/useCourses";
import { useEnrollments } from "../hooks/useEnrollments";
import { filterCourses } from "../utils/courseFilters";
import CourseCard from "../components/courses/CourseCard";

const FILTERS = [
  { value: "all", label: "Tất cả" },
  { value: "enrolled", label: "Đã đăng ký" },
  { value: "not-enrolled", label: "Chưa đăng ký" },
];

export default function CourseListPage() {
  const { data, loading, error } = useCourses();
  const enrollments = useEnrollments();
  const [query, setQuery] = useState("");
  const [enrollmentFilter, setEnrollmentFilter] = useState("all");
  const enrollmentReady = !enrollments.loading && !enrollments.error;
  const enrolledIds = new Set(enrollmentReady ? enrollments.data.map(row => String(row.course.id)) : []);
  const waitingForEnrollment = enrollmentFilter !== "all" && !enrollmentReady;
  const filtered = waitingForEnrollment ? [] : filterCourses(data, query, enrollmentFilter, enrolledIds);

  if (loading) return <div className="page student-page student-CourseListPage">Đang tải...</div>;
  if (error) return <div className="page student-page student-CourseListPage">Không tải được danh sách khóa học.</div>;

  return (
    <div className="page student-page student-CourseListPage">
      <h1>Khám phá khóa học</h1>
      <p className="student-subtitle">Chọn khóa học đã publish, xem chi tiết rồi đăng ký.</p>
      <div className="course-discovery-toolbar">
        <div className="course-search-wrap">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
            <circle cx="10.5" cy="10.5" r="7" /><path d="m16 16 5 5" />
          </svg>
          <input className="course-search" aria-label="Tìm khóa học" placeholder="Tìm theo tên khóa học"
            value={query} onChange={event => setQuery(event.target.value)} />
        </div>
        <div className="student-tabs course-enrollment-filters" role="group" aria-label="Lọc theo đăng ký">
          {FILTERS.map(filter => <button key={filter.value} type="button"
            className={enrollmentFilter === filter.value ? "active" : ""}
            aria-pressed={enrollmentFilter === filter.value}
            disabled={filter.value !== "all" && !enrollmentReady}
            onClick={() => setEnrollmentFilter(filter.value)}>{filter.label}</button>)}
        </div>
      </div>
      {enrollments.loading && <p role="status">Đang tải trạng thái đăng ký...</p>}
      {enrollments.error && <div role="alert" className="course-enrollment-error">
        <p>Không tải được trạng thái đăng ký. Bạn vẫn có thể xem tất cả khóa học.</p>
        <button type="button" className="btn-secondary" onClick={enrollments.reload}>Thử lại</button>
      </div>}
      {waitingForEnrollment ? <p role="status">Chưa có dữ liệu đăng ký để lọc khóa học.</p> :
        filtered.length === 0 ? <p role="status">Không có khóa học phù hợp với tìm kiếm và bộ lọc đã chọn.</p> :
        <div className="grid">
          {filtered.map(course => <CourseCard key={course.id} course={course}
            showProgress={false} enrolled={enrollmentReady && enrolledIds.has(String(course.id))} />)}
        </div>}
    </div>
  );
}