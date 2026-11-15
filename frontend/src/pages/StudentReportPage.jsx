import "../styles/management.css";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  listInstructorStudents,
  fetchInstructorStudent,
  listReportCourses,
} from "../api/analytics.api";
import { checkpointResult, summarizeStudentReports } from "../utils/studentReportStats";

export default function StudentReportPage() {
  const { studentId } = useParams();
  const [rows, setRows] = useState([]);
  const [selected, setSelected] = useState(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [courses, setCourses] = useState([]);
  const [courseId, setCourseId] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setError("");
    setSelected(null);
    setLoading(true);
    if (studentId) {
      fetchInstructorStudent(studentId)
        .then(data => { if (active) setSelected(data); })
        .catch(e => { if (active) setError(e.detail || e.message); })
        .finally(() => { if (active) setLoading(false); });
    } else {
      setCourseId("");
      setRows([]);
      listReportCourses()
        .then(data => {
          if (!active) return;
          setCourses(data);
          setCourseId(data.length ? String(data[0].id) : "");
          if (!data.length) setLoading(false);
        })
        .catch(e => {
          if (active) { setError(e.detail || e.message); setLoading(false); }
        });
    }
    return () => { active = false; };
  }, [studentId]);

  useEffect(() => {
    if (studentId || !courseId) return;
    let active = true;
    setLoading(true);
    setError("");
    setRows([]);
    listInstructorStudents(courseId)
      .then(data => { if (active) setRows(data); })
      .catch(e => { if (active) setError(e.detail || e.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [studentId, courseId]);

  if (error) return <div className="page management-page"><p role="alert">{error}</p></div>;

  if (selected) {
    const scoreText = selected.average_score == null
      ? "—"
      : `${selected.average_score}%`;
    return (
      <div className="page management-page">
        <div className="breadcrumb">
          <Link to="/instructor/student-report">Học viên và báo cáo</Link> / {selected.name}
        </div>
        <div className="page-head">
          <div>
            <h1>{selected.name}</h1>
            <p className="management-subtitle">
              {selected.email} · {selected.courses.map(course => course.title).join(", ") || "Chưa có khóa học"}
            </p>
          </div>
          <Link className="btn-secondary" to="/instructor/student-report">← Quay lại danh sách</Link>
        </div>
        <div className="management-grid four">
          <section className="management-card">
            <div className="management-kpi-label">Tiến độ video</div>
            <div className="management-kpi-value">{selected.progress ?? 0}%</div>
            <small>{selected.courses.length} khóa học</small>
          </section>
          <section className="management-card">
            <div className="management-kpi-label">Điểm trung bình Checkpoint</div>
            <div className="management-kpi-value">{scoreText}</div>
            <small>{selected.attempt_count ?? 0} lượt làm</small>
          </section>
          <section className="management-card">
            <div className="management-kpi-label">Lượt làm Checkpoint</div>
            <div className="management-kpi-value">{selected.attempt_count ?? 0}</div>
          </section>
          <section className="management-card">
            <div className="management-kpi-label">Phiên AI Tutor</div>
            <div className="management-kpi-value">{selected.tutor_sessions ?? 0}</div>
          </section>
        </div>
        <div className="report-detail-grid">
          <section className="management-card">
            <h2>Kết quả Checkpoint theo khóa học</h2>
            {selected.courses.map(course => {
              const result = checkpointResult(course);
              const average = course.average_score == null ? "—" : `${course.average_score}%`;
              const passRate = course.pass_rate == null ? "—" : `${course.pass_rate}%`;
              const lastScore = course.last_score == null ? "—" : `${course.last_score}%`;
              return (
                <div className="report-row" key={course.id}>
                  <strong>{course.title}</strong>
                  <span>TB {average}</span>
                  <span className={`status-chip ${result.tone}`}>{result.label}</span>
                  <small>
                    Video {course.progress}% · {course.attempt_count} lượt · Đạt {passRate} · Gần nhất {lastScore}
                  </small>
                </div>
              );
            })}
          </section>
          <section className="management-card">
            <h2>Khái niệm hay sai</h2>
            {(selected.weak_concepts || []).length
              ? selected.weak_concepts.map(item => (
                <div className="report-row" key={item.topic || item.question}>
                  <strong>{item.topic || item.question}</strong>
                  <span className="status-chip error">{item.incorrect_count} lần</span>
                </div>
              ))
              : <p>Chưa có dữ liệu lỗi.</p>}
          </section>
        </div>
      </div>
    );
  }

  const filtered = rows.filter(student =>
    student.name.toLowerCase().includes(query.toLowerCase())
    || student.email.toLowerCase().includes(query.toLowerCase())
  );
  const summary = summarizeStudentReports(filtered);
  const passRateText = summary.passRate == null ? "—" : `${summary.passRate}%`;

  return (
    <div className="page management-page">
      <div className="page-head">
        <div>
          <h1>Học viên & báo cáo</h1>
          <p className="management-subtitle">Theo dõi riêng tiến độ video và kết quả Checkpoint.</p>
        </div>
        <select
          aria-label="Chọn khóa học"
          value={courseId}
          disabled={!courses.length}
          onChange={event => {
            setCourseId(event.target.value);
            setRows([]);
            setLoading(true);
          }}
        >
          {!courses.length && <option value="">{loading ? "Đang tải khóa học…" : "Chưa có khóa học"}</option>}
          {courses.map(course => <option key={course.id} value={String(course.id)}>{course.title}</option>)}
        </select>
      </div>
      <div className="management-grid four">
        <section className="management-card">
          <div className="management-kpi-label">Học viên đăng ký</div>
          <div className="management-kpi-value">{filtered.length}</div>
        </section>
        <section className="management-card">
          <div className="management-kpi-label">Tiến độ video trung bình</div>
          <div className="management-kpi-value">{summary.averageProgress}%</div>
        </section>
        <section className="management-card">
          <div className="management-kpi-label">Tỷ lệ đạt Checkpoint</div>
          <div className="management-kpi-value">{passRateText}</div>
        </section>
        <section className="management-card">
          <div className="management-kpi-label">Học viên cần ôn</div>
          <div className="management-kpi-value">{summary.studentsNeedingReview}</div>
          <small>Theo lượt Checkpoint gần nhất</small>
        </section>
      </div>
      <section className="management-card report-list">
        <div className="spec-card-heading">
          <h2>Tiến độ học viên</h2>
          <input value={query} onChange={event => setQuery(event.target.value)} placeholder="⌕  Tìm học viên" />
        </div>
        <div className="management-table-wrap">
          <table className="management-table">
            <thead>
              <tr><th>Học viên</th><th>Tiến độ video</th><th>Điểm gần nhất</th><th>Kết quả Checkpoint</th><th /></tr>
            </thead>
            <tbody>
              {!filtered.length && (
                <tr><td colSpan={5}>
                  {loading ? "Đang tải dữ liệu…" : !courses.length ? "Chưa có khóa học."
                    : query ? "Không tìm thấy học viên phù hợp." : "Chưa có học viên đăng ký khóa học này."}
                </td></tr>
              )}
              {filtered.map(student => {
                const result = checkpointResult(student);
                return (
                  <tr key={student.id}>
                    <td><strong>{student.name}</strong><br /><small>{student.email}</small></td>
                    <td><progress max="100" value={student.progress ?? 0} /> {student.progress ?? 0}%</td>
                    <td>{student.last_score == null ? "—" : `${student.last_score}%`}</td>
                    <td><span className={`status-chip ${result.tone}`}>{result.label}</span></td>
                    <td><Link className="management-link" to={`/instructor/students/${student.id}`}>Chi tiết</Link></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
