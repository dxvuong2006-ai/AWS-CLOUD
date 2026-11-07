import "../styles/student.css";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useEnrollments } from "../hooks/useEnrollments";
import { enrollmentError } from "../api/enrollments.api";
export const STATUS_LABELS = { NOT_STARTED: "Chưa học", IN_PROGRESS: "Đang học", COMPLETED: "Hoàn thành" };
export default function MyCoursesPage() {
  const {data,loading,error,reload}=useEnrollments(); const [filter,setFilter]=useState("");
  return <div className="page student-page student-MyCoursesPage">
    <div className="page-head"><div><h1>Khóa học của tôi</h1><p className="student-subtitle">Các khóa học bạn đã đăng ký.</p></div><Link className="btn-secondary" to="/courses">◎ Khám phá thêm</Link></div>
    <div className="student-tabs" aria-label="Trạng thái khóa học">
      <button className={!filter ? "active" : ""} onClick={()=>setFilter("")}>Tất cả</button>
      {Object.entries(STATUS_LABELS).map(([value,label])=><button key={value} className={filter===value ? "active" : ""} onClick={()=>setFilter(value)}>{label} · {data.filter(row=>row.status===value).length}</button>)}
    </div>
    {loading ? <p>Đang tải...</p> : error ? <div role="alert"><p>{enrollmentError(error)}</p><button onClick={reload}>Thử lại</button></div> : <>
      {!data.length && <p>Bạn chưa đăng ký khóa học. <Link to="/courses">Khám phá khóa học</Link></p>}
      {data.length > 0 && !data.some(row=>!filter || row.status===filter) && <p>Chưa có khóa học ở trạng thái này.</p>}
      <div className="my-course-list">{data.filter(row=>!filter || row.status===filter).map(row=><article className="card my-course-row" key={row.course.id}>
        <div className="course-art" aria-hidden="true"><svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2.6"><path d="M13 36h23a9 9 0 0 0 1-18 13 13 0 0 0-25-1 10 10 0 0 0 1 19Z" /></svg></div>
        <div className="my-course-info"><h2><Link to={"/courses/" + row.course.id}>{row.course.title}</Link></h2>
          <p>{STATUS_LABELS[row.status] || "Đã đăng ký"}</p>
          <div className="my-course-progress"><span>Tiến độ</span><strong>{row.progress_percent ?? 0}%</strong></div>
          <progress max="100" value={row.progress_percent ?? 0} aria-label="Tiến độ khóa học" />
        </div>
        <div className="my-course-actions">{row.resume_lesson_id && <Link className="btn-primary" to={"/courses/" + row.course.id + "/lessons/" + row.resume_lesson_id}>
          → {row.status === "NOT_STARTED" ? "Bắt đầu học" : "Tiếp tục học"}</Link>}
          <Link className="my-course-outline" to={"/courses/" + row.course.id}>Xem lộ trình</Link>
        </div>
      </article>)}</div>
    </>}
  </div>;
}