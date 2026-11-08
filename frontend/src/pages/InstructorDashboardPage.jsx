import "../styles/screens21-35.css";
import "../styles/management.css";
import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { fetchInstructorDashboard } from "../api/analytics.api";

export default function InstructorDashboardPage() {
  const [data,setData]=useState(null);
  const [error,setError]=useState("");
  const [version,setVersion]=useState(0);
  useEffect(()=>{let active=true; setError(""); fetchInstructorDashboard().then(value=>{if(active)setData(value);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[version]);
  if(error)return <div className="page management-page instructor-spec-page dashboard-spec-page"><p role="alert">{error}</p><button onClick={()=>setVersion(v=>v+1)}>Thử lại</button></div>;
  if(!data)return <div className="page management-page instructor-spec-page dashboard-spec-page"><p>Đang tải...</p></div>;
  return <div className="page management-page instructor-spec-page dashboard-spec-page">
    <div className="page-head"><div><h1>Tổng quan</h1><p className="management-subtitle">Theo dõi khóa học, trạng thái xử lý và hoạt động học tập.</p></div><Link className="btn-primary" to="/instructor/courses/new">＋ Tạo khóa học</Link></div>
    <div className="management-grid">
      {[["Khóa học", data.course_count],["Lesson chờ duyệt", data.review_required],["Học viên", data.active_students],["Tỷ lệ đạt", data.pass_rate == null ? "—" : data.pass_rate + "%"]].map(([label,value]) =>
        <section className="management-card" key={label}><div className="management-kpi-label">{label}</div><div className="management-kpi-value">{value}</div></section>)}
    </div>
    <div className="dashboard-detail-grid">
      <section className="management-card">
        <div className="spec-card-heading"><h2>Khóa học gần đây</h2><Link className="management-link" to="/instructor/courses">Xem tất cả</Link></div>
        <div className="dashboard-course-list">
          {data.courses.map(course => <div className="dashboard-course-row" key={course.id}>
            <div><Link className="dashboard-course-title" to={"/instructor/courses/" + course.id + "/edit"}>{course.title}</Link><p>{course.lesson_count} lesson</p></div>
            <span className={"status-chip " + (course.status === "PUBLISHED" ? "success" : "neutral")}>● {course.status === "PUBLISHED" ? "Đã publish" : "Bản nháp"}</span>
          </div>)}
          {!data.courses.length && <p className="management-subtitle">Chưa có khóa học.</p>}
        </div>
      </section>
      <section className="management-card">
        <div className="spec-card-heading"><h2>Cần xử lý</h2><Link className="management-link" to="/instructor/review-queue">Xem tất cả</Link></div>
        {(data.tasks || []).map(task => <div className="dashboard-course-row" key={task.id}><div><Link className="dashboard-course-title" to={task.status === "REVIEW_REQUIRED" ? "/instructor/review/" + task.id : "/instructor/courses/" + task.course_id + "/lessons/" + task.id + "/upload"}>{task.title}</Link><p>{task.course_title}</p></div><span className={"status-chip " + (task.status === "FAILED" ? "error" : task.status === "REVIEW_REQUIRED" ? "warning" : "neutral")}>{task.status === "FAILED" ? "Thất bại" : task.status === "REVIEW_REQUIRED" ? "Chờ duyệt" : "Đang xử lý"}</span></div>)}
        {!data.tasks?.length && <p className="management-subtitle">Không có học liệu cần xử lý.</p>}
        <Link className="management-link" to="/instructor/review-queue">Mở hàng chờ học liệu AI →</Link>
      </section>
    </div>
  </div>;
}
