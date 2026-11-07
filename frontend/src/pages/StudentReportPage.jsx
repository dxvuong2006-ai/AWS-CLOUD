import "../styles/management.css";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { listInstructorStudents, fetchInstructorStudent } from "../api/analytics.api";

export default function StudentReportPage() {
  const { studentId }=useParams();
  const [rows,setRows]=useState([]);
  const [selected,setSelected]=useState(null);
  const [query,setQuery]=useState("");
  const [error,setError]=useState("");
  useEffect(()=>{
    if(studentId) fetchInstructorStudent(studentId).then(setSelected).catch(e=>setError(e.detail||e.message));
    else listInstructorStudents().then(setRows).catch(e=>setError(e.detail||e.message));
  },[studentId]);
  if(error)return <div className="page management-page"><p role="alert">{error}</p></div>;
  if(selected)return <div className="page management-page"><div className="breadcrumb"><Link to="/instructor/student-report">Học viên và báo cáo</Link> / {selected.name}</div><h1>{selected.name}</h1><p className="management-subtitle">{selected.email}</p><div className="management-grid three">{selected.courses.map(course=><section className="management-card" key={course.id}><strong>{course.title}</strong><p>{course.progress}% hoàn thành</p><progress max="100" value={course.progress} style={{width:"100%"}} /></section>)}</div></div>;
  const filtered=rows.filter(student=>student.name.toLowerCase().includes(query.toLowerCase())||student.email.toLowerCase().includes(query.toLowerCase()));
  return <div className="page management-page"><div className="page-head"><div><h1>Học viên và báo cáo</h1><p className="management-subtitle">Theo dõi mức hoàn thành và tiến độ checkpoint.</p></div></div><div className="management-toolbar"><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Tìm học viên..." /></div><div className="management-table-wrap"><table className="management-table"><thead><tr><th>Học viên</th><th>Email</th><th>Tiến độ trung bình</th><th>Trạng thái</th><th></th></tr></thead><tbody>{filtered.map(student=><tr key={student.id}><td><strong>{student.name}</strong></td><td>{student.email}</td><td>{student.progress}%</td><td><span className={`status-chip ${student.status==="COMPLETED"?"success":"neutral"}`}>{student.status==="COMPLETED"?"Hoàn thành":"Đang học"}</span></td><td><Link className="management-link" to={`/instructor/students/${student.id}`}>Xem chi tiết</Link></td></tr>)}</tbody></table></div></div>;
}
