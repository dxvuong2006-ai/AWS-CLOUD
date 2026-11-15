import "../styles/management.css";
import "../styles/screens21-35.css";
import "../styles/workflows.css";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listCourses } from "../api/management.api";
export default function InstructorCoursesPage() {
  const [courses, setCourses] = useState([]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);
  useEffect(() => {
    let active = true; setLoading(true); setError("");
    listCourses().then(rows => { if (active) setCourses(rows); }).catch(e => { if (active) setError(e.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [version]);
  const filtered = courses.filter(course => course.title.toLocaleLowerCase("vi").includes(query.toLocaleLowerCase("vi")) && (!filter || course.status === filter));
  return <div className="page management-page instructor-spec-page courses-spec-page">
    <div className="page-head"><div><h1>Khóa học</h1><p className="management-subtitle">Tạo, chỉnh sửa và xuất bản khóa học.</p></div><Link className="btn-primary" to="/instructor/courses/new">＋ Tạo khóa học</Link></div>
    <div className="management-toolbar"><label className="instructor-course-search"><span aria-hidden="true">⌕</span><input aria-label="Tìm theo tên khóa học" value={query} onChange={e => setQuery(e.target.value)} placeholder="Tìm theo tên khóa học" /></label>
      <div className="workflow-tabs" aria-label="Trạng thái khóa học">{[["", "Tất cả"], ["DRAFT", "Bản nháp"], ["PUBLISHED", "Đã publish"]].map(([value, label]) => <button key={value} aria-pressed={filter === value} className={filter === value ? "active" : ""} onClick={() => setFilter(value)}>{label}</button>)}</div>
    </div>
    {loading ? <p role="status">Đang tải khóa học...</p> : error ? <div role="alert"><p>{error}</p><button onClick={() => setVersion(v => v + 1)}>Thử lại</button></div> :
      <div className="management-table-wrap"><table className="management-table"><thead><tr><th>Tên khóa học</th><th>Cấu trúc</th><th>Trạng thái</th><th>Cập nhật</th><th>Thao tác</th></tr></thead><tbody>
        {filtered.map(course => <tr key={course.id}><td><strong>{course.title}</strong></td><td>{course.sections.length} section · {course.sections.reduce((n,s) => n + s.lessons.length, 0)} lesson</td><td><span className={"status-chip " + (course.status === "PUBLISHED" ? "success" : "neutral")}>● {course.status === "PUBLISHED" ? "Đã publish" : "Bản nháp"}</span></td><td>{new Date(course.updated_at).toLocaleDateString("vi-VN")}</td><td><Link className="management-link" to={"/instructor/courses/" + course.id + "/edit"}>Mở / Sửa</Link></td></tr>)}
        {!filtered.length && <tr><td colSpan={5} className="spec-empty">Không tìm thấy khóa học phù hợp.</td></tr>}
      </tbody></table></div>}
  </div>;
}
