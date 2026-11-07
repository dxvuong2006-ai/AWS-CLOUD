import "../styles/management.css";
import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { fetchInstructorDashboard } from "../api/analytics.api";

export default function InstructorDashboardPage() {
  const [data,setData]=useState(null);
  const [error,setError]=useState("");
  useEffect(()=>{fetchInstructorDashboard().then(setData).catch(e=>setError(e.detail||e.message));},[]);
  if(error)return <div className="page management-page"><p role="alert">{error}</p></div>;
  if(!data)return <div className="page management-page"><p>Đang tải...</p></div>;
  return <div className="page management-page">
    <div className="page-head"><div><h1>Tổng quan giảng viên</h1><p className="management-subtitle">Theo dõi khóa học, học liệu AI và học viên.</p></div></div>
    <div className="management-grid">
      {[["Khóa học đã publish", data.published_courses],["Tổng lesson", data.lesson_count],["Chờ duyệt AI", data.review_required],["Học viên đang học", data.active_students]].map(([label,value]) =>
        <section className="management-card" key={label}><div className="management-kpi-label">{label}</div><div className="management-kpi-value">{value}</div></section>)}
    </div>
    <section className="management-card" style={{marginTop:18}}>
      <h2>Khóa học gần đây</h2>
      <div className="management-table-wrap"><table className="management-table"><thead><tr><th>Khóa học</th><th>Lesson</th><th>Trạng thái</th><th></th></tr></thead><tbody>
        {data.courses.map(course => <tr key={course.id}><td><strong>{course.title}</strong></td><td>{course.lesson_count}</td><td><span className={`status-chip ${course.status==="PUBLISHED"?"success":"neutral"}`}>{course.status==="PUBLISHED"?"Đã publish":"Bản nháp"}</span></td><td><Link className="management-link" to={`/instructor/courses/${course.id}/edit`}>Quản lý →</Link></td></tr>)}
      </tbody></table></div>
    </section>
  </div>;
}
