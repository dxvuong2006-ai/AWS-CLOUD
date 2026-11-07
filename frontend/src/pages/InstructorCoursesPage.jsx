import "../styles/management.css";
import { useState } from "react";
import { Link } from "react-router-dom";
import courses from "../mocks/courses.mock.json";

export default function InstructorCoursesPage() {
  const [query, setQuery] = useState("");
  const filtered = courses.filter(course => course.title.toLowerCase().includes(query.toLowerCase()));
  return <div className="page management-page">
    <div className="page-head"><div><h1>Khóa học</h1><p className="management-subtitle">Tạo và quản lý cấu trúc khóa học.</p></div><Link className="btn-primary" to="/instructor/courses/new">＋ Tạo khóa học</Link></div>
    <div className="management-toolbar"><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Tìm khóa học..." /></div>
    <div className="management-table-wrap"><table className="management-table"><thead><tr><th>Khóa học</th><th>Section</th><th>Lesson</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>
      {filtered.map(course => <tr key={course.id}><td><strong>{course.title}</strong><div className="management-kpi-label">{course.description}</div></td><td>{course.sections.length}</td><td>{course.sections.reduce((n,s)=>n+s.lessons.length,0)}</td><td><span className={`status-chip ${course.status==="PUBLISHED"?"success":"neutral"}`}>{course.status==="PUBLISHED"?"Đã publish":"Bản nháp"}</span></td><td><Link className="management-link" to={`/instructor/courses/${course.id}/edit`}>Chỉnh sửa</Link></td></tr>)}
    </tbody></table></div>
  </div>;
}
