import { useState } from "react";
import { Link } from "react-router-dom";
import { useEnrollments } from "../hooks/useEnrollments";
import { enrollmentError } from "../api/enrollments.api";
export const STATUS_LABELS = { NOT_STARTED: "Ch?a h?c", IN_PROGRESS: "?ang h?c", COMPLETED: "Ho?n th?nh" };
export default function MyCoursesPage() {
  const {data,loading,error,reload}=useEnrollments(); const [filter,setFilter]=useState("");
  return <div className="page"><h1>Kh?a h?c c?a t?i</h1>
    <label>Tr?ng th?i <select value={filter} onChange={e=>setFilter(e.target.value)}>
      <option value="">T?t c?</option>{Object.entries(STATUS_LABELS).map(([value,label])=><option key={value} value={value}>{label}</option>)}
    </select></label>
    {loading ? <p>?ang t?i...</p> : error ? <div role="alert"><p>{enrollmentError(error)}</p><button onClick={reload}>Th? l?i</button></div> : <>
      {!data.length && <p>B?n ch?a ??ng k? kh?a h?c. <Link to="/courses">Kh?m ph? kh?a h?c</Link></p>}
      {data.length > 0 && !data.some(row=>!filter || row.status===filter) && <p>Ch?a c? kh?a h?c ? tr?ng th?i n?y.</p>}
      <div className="grid">{data.filter(row=>!filter || row.status===filter).map(row=><article className="card" key={row.course.id}>
        <h2><Link to={`/courses/${row.course.id}`}>{row.course.title}</Link></h2>
        <p>{STATUS_LABELS[row.status] || "?? ??ng k?"} ? {row.progress_percent ?? 0}% n?i dung ?? xem</p>
        {row.resume_lesson_id && <Link className="btn-primary" to={`/courses/${row.course.id}/lessons/${row.resume_lesson_id}`}>
          {row.status === "NOT_STARTED" ? "B?t ??u h?c" : "Ti?p t?c h?c"}</Link>}
        <p><Link to={`/courses/${row.course.id}`}>Xem l? tr?nh</Link></p>
      </article>)}</div>
    </>}
  </div>;
}
