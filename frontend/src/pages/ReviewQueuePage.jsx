import "../styles/management.css";
import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { listReviewQueue } from "../api/review.api";

export default function ReviewQueuePage() {
  const [rows,setRows]=useState([]);
  const [filter,setFilter]=useState("ALL");
  const [error,setError]=useState("");
  useEffect(()=>{listReviewQueue().then(setRows).catch(e=>setError(e.detail||e.message));},[]);
  if(error)return <div className="page management-page"><p role="alert">{error}</p></div>;
  const visible = filter === "ALL" ? rows : rows.filter(row => row.status === filter);
  const count = status => rows.filter(row => row.status === status).length;
  return <div className="page management-page">
    <div className="page-head"><div><h1>Hàng đợi học liệu AI</h1><p className="management-subtitle">Kiểm duyệt tóm tắt, khái niệm, flashcard và quiz trước khi publish.</p></div></div>
    <div className="queue-filters" role="tablist">{[["ALL","Tất cả"],["REVIEW_REQUIRED",`Chờ duyệt · ${count("REVIEW_REQUIRED")}`],["PROCESSING",`Đang xử lý · ${count("PROCESSING")}`],["FAILED",`Thất bại · ${count("FAILED")}`]].map(([value,label])=><button key={value} className={filter===value?"active":""} onClick={()=>setFilter(value)}>{label}</button>)}</div>
    <div className="management-table-wrap"><table className="management-table"><thead><tr><th>Lesson</th><th>Khóa học</th><th>Trạng thái AI</th><th>Thao tác</th></tr></thead><tbody>
      {visible.map(lesson => <tr key={lesson.id}><td><strong>{lesson.title}</strong></td><td>{lesson.course_title}</td><td><span className={`status-chip ${lesson.status==="REVIEW_REQUIRED"?"warning":lesson.status==="FAILED"?"error":"neutral"}`}>{lesson.status==="REVIEW_REQUIRED"?"Chờ duyệt":lesson.status==="FAILED"?"Thất bại":lesson.status==="PROCESSING"?"Đang xử lý":"Đã xử lý"}</span></td><td>{lesson.status==="REVIEW_REQUIRED" ? <Link className="management-link" to={`/instructor/review/${lesson.id}`}>Duyệt</Link> : lesson.status==="FAILED" ? <Link className="management-link" to={`/instructor/courses/${lesson.course_id}/lessons/${lesson.id}/upload`}>Chạy lại</Link> : <Link className="management-link" to={`/instructor/courses/${lesson.course_id}/lessons/${lesson.id}/upload`}>Xem</Link>}</td></tr>)}
      {!visible.length && <tr><td className="spec-empty" colSpan="4">Không có học liệu ở trạng thái này.</td></tr>}
    </tbody></table></div>
  </div>;
}
