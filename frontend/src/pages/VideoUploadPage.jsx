import "../styles/management.css";
import "../styles/screens21-35.css";
import "../styles/workflows.css";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getCourse, processingStatus, retryProcessing } from "../api/management.api";
import { uploadVideo, videoType } from "../api/uploads.api";
export default function VideoUploadPage() {
  const { courseId, lessonId } = useParams();
  const [course, setCourse] = useState(null), [status, setStatus] = useState(null);
  const [file, setFile] = useState(null), [progress, setProgress] = useState(0);
  const [busy, setBusy] = useState(false), [sent, setSent] = useState(false), [error, setError] = useState("");
  const controller = useRef(null), mounted = useRef(false), guard = useRef(false);
  useEffect(() => {
    mounted.current = true; let active = true, timer;
    getCourse(courseId).then(data => { if (active) setCourse(data); }).catch(e => { if (active) setError(e.message); });
    const poll = async () => {
      try { const value = await processingStatus(lessonId); if (active) setStatus(value); }
      catch (e) { if (active) setError(e.message); }
      finally { if (active) timer = setTimeout(poll, 5000); }
    };
    poll();
    return () => { active = false; mounted.current = false; clearTimeout(timer); controller.current?.abort(); };
  }, [courseId, lessonId]);
  const lesson = course?.sections.flatMap(s => s.lessons).find(l => String(l.id) === lessonId);
  async function upload() {
    if (!file || guard.current || !lesson) return;
    guard.current = true; setBusy(true); setError(""); setProgress(0); controller.current = new AbortController();
    try { await uploadVideo(lessonId, file, { signal: controller.current.signal, onProgress: value => mounted.current && setProgress(value) }); if (mounted.current) { setSent(true); setProgress(100); } }
    catch (e) { if (mounted.current) setError(e.name === "AbortError" ? "Đã hủy tải lên." : e.message); }
    finally { guard.current = false; if (mounted.current) setBusy(false); }
  }
  const draft = status?.status === "DRAFT" && !sent;
  return <div className="page management-page instructor-spec-page">
    <div className="breadcrumb"><Link to={"/instructor/courses/" + courseId + "/edit"}>Khóa học / {course?.title || "Cấu trúc"}</Link> / Tải video</div>
    <h1>{draft ? "Tải video bài giảng" : "Theo dõi xử lý video"}</h1><p className="management-subtitle">{lesson?.title}</p>
    {error && <p role="alert" className="workflow-error">{error}</p>}
    {!course || !status ? <p role="status">Đang tải thông tin...</p> : !lesson ? <p role="alert">Lesson không thuộc khóa học này.</p> :
    <div className="workflow-two-columns"><section className="management-card"><h2>Tệp video</h2>
      {draft && <label className="cover-upload"><strong>Chọn video bài giảng</strong><small>MP4, WebM hoặc MOV · tối đa 500 MB</small><input type="file" accept=".mp4,.webm,.mov" disabled={busy} onChange={e => { try { const selected = e.target.files?.[0]; if (selected) { videoType(selected); setFile(selected); setError(""); } } catch (failure) { setFile(null); setError(failure.message); } }} /></label>}
      {file && <div className="upload-file"><strong>{file.name}</strong><p>{(file.size / 1024 / 1024).toFixed(1)} MB</p><div className="progress-course-caption"><span>{sent ? "Đã tải xong" : busy ? "Đang tải lên" : "Sẵn sàng tải"}</span><strong>{progress}%</strong></div><progress max="100" value={progress} /></div>}
      {draft && !busy && <button className="btn-primary" disabled={!file} onClick={upload}>↑ Tải video</button>}
      {busy && <button className="btn-secondary" onClick={() => controller.current?.abort()}>Hủy tải lên</button>}
      {sent && <p role="status">Đã tải xong. Đang chờ hệ thống cập nhật trạng thái xử lý.</p>}
      {!draft && <p role="status">Trạng thái: {status.status}</p>}
      {status.error_message && <p role="alert">{status.error_message}</p>}
      {status.status === "FAILED" && <button className="btn-primary" disabled={busy} onClick={async () => { if (guard.current) return; guard.current = true; setBusy(true); setError(""); try { setStatus(await retryProcessing(lessonId)); } catch (e) { setError(e.message); } finally { setBusy(false); guard.current = false; } }}>Thử xử lý lại</button>}
      {status.status === "REVIEW_REQUIRED" && <Link className="btn-primary" to={"/instructor/review/" + lessonId}>Duyệt học liệu</Link>}
    </section><aside className="management-card"><h2>Sau khi tải xong</h2><p>Hệ thống tự xử lý video, tạo transcript và học liệu AI.</p><hr /><p>Bạn có thể rời trang sau khi tệp tải xong; tiến trình xử lý vẫn tiếp tục.</p><Link to={"/instructor/courses/" + courseId + "/edit"}>Về cấu trúc khóa học</Link></aside></div>}
  </div>;
}
