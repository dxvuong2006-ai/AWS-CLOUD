import "../styles/management.css";
import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { listReviewQueue } from "../api/review.api";

export default function ReviewQueuePage() {
  const [rows,setRows]=useState([]);
  const [error,setError]=useState("");
  useEffect(()=>{listReviewQueue().then(setRows).catch(e=>setError(e.detail||e.message));},[]);
  if(error)return <div className="page management-page"><p role="alert">{error}</p></div>;
  return <div className="page management-page">
    <div className="page-head"><div><h1>Hàng đợi học liệu AI</h1><p className="management-subtitle">Kiểm duyệt tóm tắt, khái niệm, flashcard và quiz trước khi publish.</p></div></div>
    <div className="management-table-wrap"><table className="management-table"><thead><tr><th>Lesson</th><th>Khóa học</th><th>Trạng thái AI</th><th>Thao tác</th></tr></thead><tbody>
      {rows.map(lesson => <tr key={lesson.id}><td><strong>{lesson.title}</strong></td><td>{lesson.course_title}</td><td><span className={`status-chip ${lesson.status==="REVIEW_REQUIRED"?"warning":"neutral"}`}>{lesson.status==="REVIEW_REQUIRED"?"Chờ duyệt":"Đã xử lý"}</span></td><td><Link className="management-link" to={`/instructor/review/${lesson.id}`}>Xem review →</Link></td></tr>)}
    </tbody></table></div>
  </div>;
}
