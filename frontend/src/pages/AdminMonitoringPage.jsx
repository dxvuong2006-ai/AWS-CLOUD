import "../styles/management.css";
import { useEffect, useState } from "react";
import { listMonitoringJobs } from "../api/admin.api";

export default function AdminMonitoringPage() {
  const [jobs,setJobs]=useState([]);
  const [selected,setSelected]=useState(null);
  const [error,setError]=useState("");
  useEffect(()=>{listMonitoringJobs().then(setJobs).catch(e=>setError(e.detail||e.message));},[]);
  const failed=jobs.filter(job=>job.status==="FAILED").length;
  return <div className="page management-page">
    <div className="page-head"><div><h1>Giám sát hệ thống</h1><p className="management-subtitle">Tình trạng xử lý video và dịch vụ nền.</p></div></div>
    {error&&<p role="alert">{error}</p>}
    <div className="management-grid"><section className="management-card"><div className="management-kpi-label">API</div><div className="management-kpi-value">Hoạt động</div></section><section className="management-card"><div className="management-kpi-label">Job thành công</div><div className="management-kpi-value">{jobs.filter(job=>job.status==="SUCCEEDED").length}</div></section><section className="management-card"><div className="management-kpi-label">Job thất bại</div><div className="management-kpi-value">{failed}</div></section><section className="management-card"><div className="management-kpi-label">Đang chạy</div><div className="management-kpi-value">{jobs.filter(job=>job.status==="RUNNING").length}</div></section></div>
    <section className="management-card" style={{marginTop:18}}><h2>Job gần đây</h2><div className="management-table-wrap"><table className="management-table"><thead><tr><th>Job</th><th>Lesson</th><th>Giai đoạn</th><th>Trạng thái</th><th>Thời gian</th><th></th></tr></thead><tbody>{jobs.map(job=><tr key={job.id}><td>{job.id}</td><td>{job.lesson_id}</td><td>{job.stage}</td><td><span className={`status-chip ${job.status==="FAILED"?"error":job.status==="RUNNING"?"warning":"success"}`}>{job.status==="FAILED"?"Thất bại":job.status==="RUNNING"?"Đang chạy":"Hoàn tất"}</span></td><td>{job.updated_at||""}</td><td><button className="management-link" style={{border:0,background:"transparent",cursor:"pointer"}} onClick={()=>setSelected(job)}>Chi tiết</button></td></tr>)}</tbody></table></div></section>
    {selected&&<dialog open className="enrollment-dialog" style={{position:"fixed",inset:"0",margin:"auto"}}><h2>Chi tiết job</h2><p><strong>{selected.id}</strong><br />Lesson {selected.lesson_id}<br />{selected.stage}</p>{selected.error_code&&<p role="alert">{selected.error_code}</p>}<button className="btn-primary" onClick={()=>setSelected(null)}>Đóng</button></dialog>}
  </div>;
}
