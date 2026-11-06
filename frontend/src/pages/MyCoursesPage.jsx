import { useState } from "react";
import { Link } from "react-router-dom";
import { useEnrollments } from "../hooks/useEnrollments";
import { enrollmentError } from "../api/enrollments.api";
export const STATUS_LABELS = { NOT_STARTED: "Chưa học", IN_PROGRESS: "Đang học", COMPLETED: "Hoàn thành" };
export default function MyCoursesPage() {
  const {data,loading,error,reload}=useEnrollments(); const [filter,setFilter]=useState("");
  return <div className="page"><h1>Khóa học của tôi</h1>
    <label>Trạng thái <select value={filter} onChange={e=>setFilter(e.target.value)}>
      <option value="">Tất cả</option>{Object.entries(STATUS_LABELS).map(([value,label])=><option key={value} value={value}>{label}</option>)}
    </select></label>
    {loading ? <p>Đang tải...</p> : error ? <div role="alert"><p>{enrollmentError(error)}</p><button onClick={reload}>Thử lại</button></div> : <>
      {!data.length && <p>Bạn chưa đăng ký khóa học. <Link to="/courses">Khám phá khóa học</Link></p>}
      {data.length > 0 && !data.some(row=>!filter || row.status===filter) && <p>Chưa có khóa học ở trạng thái này.</p>}
      <div className="grid">{data.filter(row=>!filter || row.status===filter).map(row=><article className="card" key={row.course.id}>
        <h2><Link to={`/courses/${row.course.id}`}>{row.course.title}</Link></h2>
        <p>{STATUS_LABELS[row.status] || "Đã đăng ký"} · {row.progress_percent ?? 0}% nội dung đã xem</p>
        {row.resume_lesson_id && <Link className="btn-primary" to={`/courses/${row.course.id}/lessons/${row.resume_lesson_id}`}>
          {row.status === "NOT_STARTED" ? "Bắt đầu học" : "Tiếp tục học"}</Link>}
        <p><Link to={`/courses/${row.course.id}`}>Xem lộ trình</Link></p>
      </article>)}</div>
    </>}
  </div>;
}
