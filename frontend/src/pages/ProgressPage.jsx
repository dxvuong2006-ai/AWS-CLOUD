
import "../styles/student.css";
import "../styles/management.css";
import { Link } from "react-router-dom";
import { useEnrollments } from "../hooks/useEnrollments";
import { enrollmentError } from "../api/enrollments.api";
import { fetchCourseProgress } from "../api/progress.api";
import { useEffect, useState } from "react";

export default function ProgressPage() {
  const enrollments = useEnrollments();
  const [rows, setRows] = useState([]);
  const [error, setError] = useState(null);
  useEffect(() => {
    let active = true;
    if (!enrollments.loading && !enrollments.error) {
      Promise.all(enrollments.data.map(async row => {
        const progress = await fetchCourseProgress(row.course.id);
        return { ...row, progress };
      })).then(value => active && setRows(value)).catch(err => active && setError(err));
    }
    return () => { active = false; };
  }, [enrollments.loading, enrollments.error, enrollments.data]);

  return <div className="page student-page management-page">
    <div className="page-head"><div><h1>Tiến độ và lịch sử điểm</h1><p className="management-subtitle">Theo dõi tiến độ từng khóa học và bài học đã hoàn thành.</p></div></div>
    {(enrollments.error || error) && <p role="alert">{enrollmentError(enrollments.error || error)} <button className="btn-secondary" onClick={enrollments.reload}>Thử lại</button></p>}
    {enrollments.loading ? <p>Đang tải...</p> : !enrollments.data.length ? <p>Bạn chưa đăng ký khóa học. <Link to="/courses">Khám phá khóa học</Link></p> :
      rows.map(row => <section className="management-card" key={row.course.id} style={{marginBottom:18}}>
        <div style={{display:"flex",justifyContent:"space-between",gap:16}}><h2 style={{margin:0}}>{row.course.title}</h2><strong>{row.progress?.overall_percent ?? row.progress_percent ?? 0}%</strong></div>
        <progress max="100" value={row.progress?.overall_percent ?? row.progress_percent ?? 0} aria-label={`Tiến độ ${row.course.title}`} style={{width:"100%",margin:"12px 0"}} />
        <div className="management-table-wrap"><table className="management-table"><thead><tr><th>Bài học</th><th>Tiến độ</th><th>Trạng thái</th></tr></thead><tbody>
          {(row.progress?.lessons ?? []).map(lesson => <tr key={lesson.lesson_id}><td>{row.course.sections?.flatMap(s => s.lessons).find(l => String(l.id) === String(lesson.lesson_id))?.title || lesson.lesson_id}</td><td>{lesson.progress_percent}%</td><td><span className={`status-chip ${lesson.completed ? "success" : "neutral"}`}>{lesson.completed ? "Hoàn thành" : "Đang học"}</span></td></tr>)}
        </tbody></table></div>
      </section>)}
  </div>;
}
