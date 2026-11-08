import "../styles/management.css";
import { useEffect, useState } from "react";
import { listMonitoringJobs } from "../api/admin.api";

const DEMO_JOBS = [
  { id: "lesson-102", stage: "Chuyển mã", status: "SUCCEEDED" },
  { id: "lesson-103", stage: "Tạo transcript", status: "RUNNING" },
  { id: "lesson-104", stage: "Chuyển mã", status: "FAILED", error_code: "Lỗi: tệp video không hợp lệ" },
];

const statusLabel = { SUCCEEDED: "Hoàn tất", RUNNING: "Đang chạy", FAILED: "Thất bại" };

export default function AdminMonitoringPage() {
  const [jobs, setJobs] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    listMonitoringJobs().then((items) => setJobs(items.length ? items : DEMO_JOBS)).catch((e) => {
      setError(e.detail || e.message);
      setJobs(DEMO_JOBS);
    });
  }, []);

  const failed = jobs.filter((job) => job.status === "FAILED").length;
  return <div className="page management-page monitoring-page">
    <div className="page-head"><div><h1>Giám sát hệ thống</h1><p className="management-subtitle">Trạng thái xử lý, lỗi và chi phí.</p></div><span className="data-badge">Dữ liệu minh họa</span></div>
    {error && <p role="alert" className="management-alert">Không tải được dữ liệu giám sát: {error}</p>}
    {notice && <p role="status" className="management-notice">{notice}</p>}
    <div className="management-grid monitoring-kpis">
      <section className="management-card"><div className="management-kpi-label">Pipeline thành công</div><div className="management-kpi-value">94%</div></section>
      <section className="management-card"><div className="management-kpi-label">Job lỗi</div><div className="management-kpi-value">{String(failed).padStart(2, "0")}</div></section>
      <section className="management-card"><div className="management-kpi-label">Tỷ lệ API lỗi</div><div className="management-kpi-value">0,8%</div></section>
      <section className="management-card"><div className="management-kpi-label">Cảnh báo chi phí</div><div className="management-kpi-value">01</div></section>
    </div>
    <div className="monitoring-layout">
      <section className="management-card"><h2>Job xử lý gần đây</h2><div className="management-table-wrap monitoring-table-wrap"><table className="management-table"><thead><tr><th>Job</th><th>Bước</th><th>Trạng thái</th><th></th></tr></thead><tbody>{jobs.map((job) => <tr key={job.id}><td><strong>{job.id}</strong></td><td>{job.stage}</td><td><span className={`status-chip ${job.status === "FAILED" ? "error" : job.status === "RUNNING" ? "info" : "success"}`}>• &nbsp;{statusLabel[job.status] || job.status}</span></td><td>{job.status === "FAILED" && <button className="management-link link-button" onClick={() => setSelected(job)}>Xem</button>}</td></tr>)}</tbody></table></div></section>
      <section className="management-card warnings-card"><h2>Cảnh báo</h2><div className="warning-row"><div><strong>Job lesson-104 thất bại</strong><small>Kiểm tra log để xác định nguyên nhân.</small></div><span className="status-chip error">• &nbsp;Lỗi</span></div><div className="warning-row"><div><strong>Ngân sách đạt ngưỡng cảnh báo</strong><small>Rà soát tài nguyên không dùng.</small></div><span className="status-chip warning">• &nbsp;Chi phí</span></div></section>
    </div>
    {selected && <div className="workflow-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelected(null); }}><section className="monitoring-dialog" role="dialog" aria-modal="true" aria-labelledby="job-dialog-title"><div className="dialog-heading"><div><h2 id="job-dialog-title">Job {selected.id}</h2><p>Bước {selected.stage} · thất bại sau 3 lần thử</p></div><span className="status-chip error">• &nbsp;Thất bại</span></div><pre>10:42:11 Bắt đầu chuyển mã{"\n"}10:42:19 Lần thử 1 thất bại{"\n"}10:43:02 Lần thử 3 thất bại{"\n"}{selected.error_code || "Lỗi: tệp video không hợp lệ"}</pre><div className="dialog-actions"><button className="btn-secondary" onClick={() => setNotice("Mở CloudWatch cần được cấu hình theo môi trường triển khai.")}>→ &nbsp;Mở CloudWatch</button><button className="btn-primary" onClick={() => { setNotice("Chạy lại job chưa được kết nối với API quản trị."); setSelected(null); }}>↻ &nbsp;Chạy lại</button><button className="btn-secondary" onClick={() => setSelected(null)}>Đóng</button></div></section></div>}
  </div>;
}
