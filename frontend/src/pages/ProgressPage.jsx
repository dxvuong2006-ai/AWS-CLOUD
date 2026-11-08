import "../styles/student.css";
import "../styles/management.css";
import "../styles/screens21-35.css";
import "../styles/workflows.css";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getHistory, getOverview } from "../api/learningOverview.api";
export default function ProgressPage() {
  const [courses, setCourses] = useState([]), [history, setHistory] = useState([]);
  const [offset, setOffset] = useState(0), [version, setVersion] = useState(0);
  const [loading, setLoading] = useState(true), [error, setError] = useState("");
  useEffect(() => { let active = true; setLoading(true); setError("");
    Promise.all([getOverview(), getHistory(offset)]).then(([rows, attempts]) => { if (active) { setCourses(rows); setHistory(attempts); } }).catch(e => { if (active) setError(e.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [offset, version]);
  return <div className="page student-page management-page progress-spec-page">
    <h1>Tiến độ học tập</h1><p className="student-subtitle">Tiến độ từng khóa học và lịch sử điểm checkpoint.</p>
    {error ? <div role="alert"><p>{error}</p><button onClick={() => setVersion(v => v + 1)}>Thử lại</button></div> : loading ? <p role="status">Đang tải tiến độ...</p> : <>
      <div className="progress-course-grid">{courses.map(row => <section className="management-card progress-course-card" key={row.course_id}>
        <div className="spec-card-heading"><h2>{row.title}</h2><Link className="management-link" to={"/courses/" + row.course_id}>Xem lộ trình</Link></div><div className="progress-course-caption"><span>Hoàn thành</span><strong>{row.progress_percent}%</strong></div><progress max="100" value={row.progress_percent} aria-label={"Tiến độ " + row.title} />
        {row.completed && <Link className="management-link" to={"/courses/" + row.course_id + "/completed"}>Xem kết quả hoàn thành →</Link>}
      </section>)}</div>
      {!courses.length && <p>Bạn chưa đăng ký khóa học. <Link to="/courses">Khám phá khóa học</Link></p>}
      <section className="management-card progress-history"><h2>Lịch sử điểm checkpoint</h2><div className="management-table-wrap"><table className="management-table"><thead><tr><th>Section</th><th>Khóa học</th><th>Điểm</th><th>Lần làm</th><th>Kết quả</th></tr></thead><tbody>
        {history.map(row => <tr key={row.id}><td><Link to={"/checkpoint-results/" + row.quiz_id + "/" + row.id}>{row.section_title}</Link></td><td>{row.course_title}</td><td>{row.score}%</td><td>Lần {row.attempt_number}</td><td><span className={"status-chip " + (row.passed ? "success" : "error")}>● {row.passed ? "Đạt" : "Cần ôn"}</span></td></tr>)}
        {!history.length && <tr><td colSpan={5}>Chưa có lượt làm checkpoint.</td></tr>}
      </tbody></table></div><div className="workflow-actions"><button className="btn-secondary" disabled={!offset} onClick={() => setOffset(v => Math.max(0, v - 20))}>Trang trước</button><button className="btn-secondary" disabled={history.length < 20} onClick={() => setOffset(v => v + 20)}>Trang sau</button></div></section>
    </>}
  </div>;
}
