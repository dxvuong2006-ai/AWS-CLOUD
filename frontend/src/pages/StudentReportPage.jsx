import "../styles/management.css";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { listInstructorStudents, fetchInstructorStudent, listReportCourses } from "../api/analytics.api";

export default function StudentReportPage() {
  const { studentId }=useParams();
  const [rows,setRows]=useState([]);
  const [selected,setSelected]=useState(null);
  const [query,setQuery]=useState("");
  const [error,setError]=useState("");
  const [courses,setCourses]=useState([]);
  const [courseId,setCourseId]=useState("");
  const [loading,setLoading]=useState(true);
  useEffect(()=>{
    let active=true;
    setError("");
    setSelected(null);
    setLoading(true);
    if(studentId) {
      fetchInstructorStudent(studentId)
        .then(data=>{if(active)setSelected(data);})
        .catch(e=>{if(active)setError(e.detail||e.message);})
        .finally(()=>{if(active)setLoading(false);});
    } else {
      setCourseId("");
      setRows([]);
      listReportCourses()
        .then(data=>{
          if(!active)return;
          setCourses(data);
          setCourseId(data.length?String(data[0].id):"");
          if(!data.length)setLoading(false);
        })
        .catch(e=>{if(active){setError(e.detail||e.message);setLoading(false);}});
    }
    return ()=>{active=false;};
  },[studentId]);
  useEffect(()=>{
    if(studentId||!courseId)return;
    let active=true;
    setLoading(true);
    setError("");
    setRows([]);
    listInstructorStudents(courseId)
      .then(data=>{if(active)setRows(data);})
      .catch(e=>{if(active)setError(e.detail||e.message);})
      .finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false;};
  },[studentId,courseId]);
  if(error)return <div className="page management-page"><p role="alert">{error}</p></div>;
  if(selected){const avg=selected.courses.length?Math.round(selected.courses.reduce((sum,course)=>sum+course.progress,0)/selected.courses.length):0; return <div className="page management-page"><div className="breadcrumb"><Link to="/instructor/student-report">Học viên và báo cáo</Link> / {selected.name}</div><div className="page-head"><div><h1>{selected.name}</h1><p className="management-subtitle">{selected.email} · {selected.courses.map(course=>course.title).join(", ") || "Chưa có khóa học"}</p></div><Link className="btn-secondary" to="/instructor/student-report">← Quay lại danh sách</Link></div><div className="management-grid four"><section className="management-card"><div className="management-kpi-label">Tiến độ</div><div className="management-kpi-value">{avg}%</div><small>{selected.courses.length} section/khóa học</small></section><section className="management-card"><div className="management-kpi-label">Điểm trung bình</div><div className="management-kpi-value">{selected.average_score ?? "—"}%</div><small>{selected.attempt_count || 0} lần làm</small></section><section className="management-card"><div className="management-kpi-label">Lần làm checkpoint</div><div className="management-kpi-value">{selected.attempt_count || 0}</div></section><section className="management-card"><div className="management-kpi-label">Phiên AI Tutor</div><div className="management-kpi-value">{selected.tutor_sessions || 0}</div></section></div><div className="report-detail-grid"><section className="management-card"><h2>Kết quả theo section</h2>{selected.courses.map(course=><div className="report-row" key={course.id}><strong>{course.title}</strong><span>{course.progress}%</span><progress max="100" value={course.progress} /></div>)}</section><section className="management-card"><h2>Khái niệm hay sai</h2>{(selected.weak_concepts || []).length ? selected.weak_concepts.map(item=><div className="report-row" key={item.topic || item.question}><strong>{item.topic || item.question}</strong><span className="status-chip error">{item.incorrect_count} lần</span></div>) : <p>Chưa có dữ liệu lỗi.</p>}</section></div></div>;}
  const filtered=rows.filter(student=>student.name.toLowerCase().includes(query.toLowerCase())||student.email.toLowerCase().includes(query.toLowerCase()));
  const average=filtered.length?Math.round(filtered.reduce((sum,student)=>sum+(student.progress||0),0)/filtered.length):0;
  return <div className="page management-page"><div className="page-head"><div><h1>Học viên & báo cáo</h1><p className="management-subtitle">Theo dõi tiến độ và tỷ lệ đạt checkpoint.</p></div><select aria-label="Chọn khóa học" value={courseId} disabled={!courses.length} onChange={e=>{setCourseId(e.target.value);setRows([]);setLoading(true);}}>{!courses.length&&<option value="">{loading?"Đang tải khóa học…":"Chưa có khóa học"}</option>}{courses.map(course=><option key={course.id} value={String(course.id)}>{course.title}</option>)}</select></div><div className="management-grid four"><section className="management-card"><div className="management-kpi-label">Học viên đăng ký</div><div className="management-kpi-value">{filtered.length}</div></section><section className="management-card"><div className="management-kpi-label">Tiến độ trung bình</div><div className="management-kpi-value">{average}%</div></section><section className="management-card"><div className="management-kpi-label">Tỷ lệ đạt checkpoint</div><div className="management-kpi-value">—</div></section><section className="management-card"><div className="management-kpi-label">Học viên cần ôn</div><div className="management-kpi-value">{filtered.filter(student=>(student.progress||0)<50).length}</div><small>Điểm dưới 50%</small></section></div><section className="management-card report-list"><div className="spec-card-heading"><h2>Tiến độ học viên</h2><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="⌕  Tìm học viên" /></div><div className="management-table-wrap"><table className="management-table"><thead><tr><th>Học viên</th><th>Tiến độ</th><th>Điểm gần nhất</th><th>Kết quả</th><th></th></tr></thead><tbody>{!filtered.length&&<tr><td colSpan={5}>{loading?"Đang tải dữ liệu…":!courses.length?"Chưa có khóa học.":query?"Không tìm thấy học viên phù hợp.":"Chưa có học viên đăng ký khóa học này."}</td></tr>}{filtered.map(student=><tr key={student.id}><td><strong>{student.name}</strong><br /><small>{student.email}</small></td><td><progress max="100" value={student.progress || 0} /></td><td>{student.last_score ?? "—"}{student.last_score != null ? "%" : ""}</td><td><span className={`status-chip ${(student.progress||0)>=80?"success":(student.progress||0)<50?"error":"warning"}`}>{(student.progress||0)>=80?"Đạt":(student.progress||0)<50?"Cần ôn":"Chưa đạt"}</span></td><td><Link className="management-link" to={`/instructor/students/${student.id}`}>Chi tiết</Link></td></tr>)}</tbody></table></div></section></div>;
}
