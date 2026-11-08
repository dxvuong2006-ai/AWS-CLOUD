import "../styles/student.css";
import "../styles/workflows.css";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getCompletion } from "../api/learningOverview.api";
export default function CourseCompletePage() {
  const { courseId } = useParams();
  const [data, setData] = useState(null), [error, setError] = useState(""), [version, setVersion] = useState(0);
  useEffect(() => { let active = true; setData(null); setError(""); getCompletion(courseId).then(d => { if (active) setData(d); }).catch(e => { if (active) setError(e.message); }); return () => { active = false; }; }, [courseId, version]);
  return <div className="page student-page">
    {error ? <div role="alert"><p>{error}</p><button onClick={() => setVersion(v => v + 1)}>Thử lại</button></div> : !data ? <p role="status">Đang tải kết quả khóa học...</p> : <section className="card course-complete-card">
      <div className="completion-trophy" aria-hidden="true">{data.completed ? "♕" : "◷"}</div><h1>{data.completed ? "Chúc mừng bạn đã hoàn thành khóa học" : "Bạn đang trên hành trình hoàn thành khóa học"}</h1><p className="student-subtitle">{data.title}</p>
      <div className="completion-stats"><div><strong>{data.passed_sections} / {data.section_count}</strong><span>Section đạt</span></div><div><strong>{data.completed_lessons} / {data.lesson_count}</strong><span>Lesson đã học</span></div><div><strong>{data.average_score == null ? "—" : data.average_score + "%"}</strong><span>Điểm trung bình checkpoint đã đạt</span></div></div>
      <div className="workflow-actions">{data.completed ? <><Link className="btn-secondary" to="/progress">Xem tiến độ</Link><Link className="btn-primary" to="/courses">Khám phá khóa học khác</Link></> : <Link className="btn-primary" to={"/courses/" + courseId}>Tiếp tục học</Link>}</div>
    </section>}
  </div>;
}
