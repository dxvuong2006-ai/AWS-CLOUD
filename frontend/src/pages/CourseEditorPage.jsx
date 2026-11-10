import "../styles/management.css";
import "../styles/screens21-35.css";
import "../styles/workflows.css";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getCourse, saveCourse, addSection, addLesson, publishCourse } from "../api/management.api";
import EditorDialog from "../components/instructor/EditorDialog";
import { lessonVideoPresentation, shouldWatchVideoStatus } from "../utils/lessonVideoStatus";
export default function CourseEditorPage() {
  const { courseId } = useParams();
  const navigate = useNavigate();
  const [course, setCourse] = useState(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [objectives, setObjectives] = useState("");
  const [cover, setCover] = useState(null);
  const [loading, setLoading] = useState(Boolean(courseId));
  const [busy, setBusy] = useState(false);
  const [coverBusy, setCoverBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [dialog, setDialog] = useState(null);
  const [newTitle, setNewTitle] = useState("");
  const [sectionId, setSectionId] = useState("");
  const [version, setVersion] = useState(0);
  const guard = useRef(false);
  const revision = useRef(0);
  useEffect(() => {
    let active = true;
    setCourse(null); setTitle(""); setDescription(""); setObjectives(""); setCover(null); setError(""); setNotice("");
    if (!courseId) { setLoading(false); return; }
    setLoading(true);
    getCourse(courseId).then(data => { if (active) { setCourse(data); setTitle(data.title); setDescription(data.description || ""); setObjectives((data.learning_objectives || []).join("\n")); setCover(data.cover_image); } })
      .catch(e => { if (active) setError(e.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [courseId, version]);
  const watchVideoChanges = shouldWatchVideoStatus(course);
  useEffect(() => {
    if (!courseId) return;
    let active = true, inFlight = false;
    const refresh = async () => {
      if (!active || document.hidden || guard.current || inFlight) return;
      const requestedRevision = revision.current;
      inFlight = true;
      try {
        const latest = await getCourse(courseId);
        // Refresh server-backed structure/status, preserving unsaved form edits.
        if (active && !guard.current && requestedRevision === revision.current) setCourse(latest);
      } catch { /* Keep the last snapshot; normal load/retry still reports errors. */ }
      finally { inFlight = false; }
    };
    const timer = watchVideoChanges ? setInterval(refresh, 5000) : null;
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      active = false;
      if (timer) clearInterval(timer);
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [courseId, watchVideoChanges]);
  async function action(operation) {
    if (guard.current) return;
    guard.current = true; revision.current += 1; setBusy(true); setError(""); setNotice("");
    try { await operation(); } catch (e) { setError(e.message || "Không lưu được thay đổi."); }
    finally { guard.current = false; setBusy(false); }
  }
  async function save(event) {
    event.preventDefault();
    if (!title.trim()) { setError("Nhập tên khóa học."); return; }
    await action(async () => {
      const saved = await saveCourse(courseId, { title: title.trim(), description: description.trim(), learning_objectives: objectives.split("\n").map(x => x.trim()).filter(Boolean), cover_image: cover });
      if (!courseId) navigate("/instructor/courses/" + saved.id + "/edit", { replace: true });
      else { setCourse(await getCourse(courseId)); setNotice("Đã lưu thông tin khóa học."); }
    });
  }
  async function chooseCover(event) {
    const file = event.target.files?.[0]; if (!file) return;
    setError("");
    if (!["image/png", "image/jpeg"].includes(file.type) || file.size > 256000) { setError("Chọn ảnh PNG/JPG không quá 250 KB."); event.target.value = ""; return; }
    setCoverBusy(true);
    try {
      const value = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = () => reject(new Error("Không đọc được ảnh.")); reader.readAsDataURL(file); });
      setCover(value);
    } catch (e) { setError(e.message); } finally { setCoverBusy(false); }
  }
  function openDialog(type, id = "") { setDialog(type); setSectionId(String(id)); setNewTitle(""); setError(""); }
  async function createItem(event) {
    event.preventDefault();
    if (!newTitle.trim()) return;
    await action(async () => {
      if (dialog === "section") await addSection(courseId, { title: newTitle.trim(), position: Math.max(0, ...course.sections.map(s => s.position)) + 1 });
      else {
        const section = course.sections.find(s => String(s.id) === sectionId);
        if (!section) throw new Error("Chọn section.");
        await addLesson(sectionId, { title: newTitle.trim(), position: Math.max(0, ...section.lessons.map(l => l.position)) + 1 });
      }
      setCourse(await getCourse(courseId)); setDialog(null); setNotice("Đã thêm nội dung.");
    });
  }
  if (loading) return <div className="page management-page instructor-spec-page"><p role="status">Đang tải khóa học...</p></div>;
  if (courseId && !course) return <div className="page management-page instructor-spec-page"><p role="alert">{error || "Không tìm thấy khóa học."}</p><button onClick={() => setVersion(v => v + 1)}>Thử lại</button><Link to="/instructor/courses">Về khóa học</Link></div>;
  return <div className="page management-page instructor-spec-page editor-spec-page">
    <div className="breadcrumb"><Link to="/instructor/courses">Khóa học</Link> / {course ? course.title : "Tạo khóa học"}</div>
    <div className="page-head"><div><h1>{course ? course.title : "Tạo khóa học"}</h1><p className="management-subtitle">{course ? "Cấu trúc khóa học · " + (course.status === "PUBLISHED" ? "Đã publish" : "Bản nháp") : "Nhập thông tin cơ bản, sau đó thêm section và lesson."}</p></div>
      <div className="management-actions"><Link className="btn-secondary" to="/instructor/courses">Hủy</Link><button disabled={busy || coverBusy} className={course ? "btn-secondary" : "btn-primary"} form="course-editor-form" type="submit">{busy ? "Đang lưu..." : course ? "Lưu thay đổi" : "Tạo khóa học"}</button>
        {course?.status === "DRAFT" && <button className="btn-primary" disabled={busy} onClick={() => openDialog("publish")}>↑ Publish khóa học</button>}</div>
    </div>
    {error && !dialog && <p className="workflow-error" role="alert">{error}</p>}{notice && <p role="status" className="status-chip success">{notice}</p>}
    <form id="course-editor-form" className="management-form course-editor-form new-course" onSubmit={save}>
      <section className="management-card course-basic-fields"><label>Tên khóa học<input maxLength={255} value={title} onChange={e => setTitle(e.target.value)} required disabled={busy} /></label>
        <label>Mô tả<textarea value={description} onChange={e => setDescription(e.target.value)} disabled={busy} /></label>
        <label>Mục tiêu học tập<textarea value={objectives} onChange={e => setObjectives(e.target.value)} placeholder="Mỗi mục tiêu một dòng" disabled={busy} /></label></section>
      <aside className="management-card"><h2>Ảnh bìa</h2><label className="cover-upload">{cover ? <img src={cover} alt="Ảnh bìa khóa học" /> : <><span aria-hidden="true">↑</span><strong>Tải ảnh bìa</strong><small>PNG hoặc JPG · không bắt buộc · tối đa 250 KB</small></>}<input type="file" accept="image/png,image/jpeg" onChange={chooseCover} disabled={busy || coverBusy} aria-label="Chọn ảnh bìa" /></label>{cover && <button className="btn-secondary" type="button" disabled={busy} onClick={() => setCover(null)}>Xóa ảnh bìa</button>}</aside>
    </form>
    {course && <section className="management-card course-structure workflow-structure">
      <div className="spec-card-heading"><h2>Section và lesson</h2><button className="btn-secondary" disabled={busy} onClick={() => openDialog("section")}>＋ Thêm section</button></div>
      {course.sections.map((section, index) => <section className="course-structure-section" key={section.id}>
        <div className="spec-card-heading"><h3>Section {index + 1} · {section.title}</h3><button className="btn-secondary" disabled={busy} onClick={() => openDialog("lesson", section.id)}>＋ Thêm lesson</button></div>
        {section.lessons.map((lesson, i) => {
          const video = lessonVideoPresentation(lesson);
          return <div className="course-structure-lesson workflow-lesson" key={lesson.id}><strong>Bài {i + 1} · {lesson.title}</strong><div><span className={"status-chip " + video.tone}>{video.label}</span>
            {video.action === "review" ? <Link to={"/instructor/review/" + lesson.id}>Duyệt học liệu</Link> : video.action && <Link to={"/instructor/courses/" + courseId + "/lessons/" + lesson.id + "/upload"}>{video.action === "upload" ? "Tải video" : "Xem trạng thái"}</Link>}</div></div>;
        })}
        {!section.lessons.length && <p className="management-subtitle">Chưa có lesson. Thêm lesson để bắt đầu.</p>}
      </section>)}
      {!course.sections.length && <p>Thêm section đầu tiên cho khóa học.</p>}
    </section>}
    {dialog && <EditorDialog title={dialog === "publish" ? "Publish khóa học" : dialog === "section" ? "Thêm section" : "Thêm lesson"} busy={busy} onClose={() => { setDialog(null); setError(""); }}>
      {error && <p role="alert" className="workflow-error">{error}</p>}
      {dialog === "publish" ? <><p>Tất cả lesson cần được duyệt trước khi học viên có thể đăng ký khóa học.</p><div className="management-actions"><button disabled={busy} onClick={() => setDialog(null)}>Hủy</button><button className="btn-primary" disabled={busy} onClick={() => action(async () => { await publishCourse(courseId); setCourse(await getCourse(courseId)); setDialog(null); setNotice("Đã xuất bản khóa học."); })}>{busy ? "Đang xuất bản..." : "Publish khóa học"}</button></div></> :
        <form className="management-form" onSubmit={createItem}><p>{dialog === "lesson" ? "Lesson sẽ được thêm vào cuối section." : "Section sẽ được thêm vào cuối khóa học."}</p>
          <label>{dialog === "lesson" ? "Tên lesson" : "Tên section"}<input autoFocus required maxLength={255} value={newTitle} onChange={e => setNewTitle(e.target.value)} disabled={busy} /></label>
          {dialog === "lesson" && <label>Thuộc section<select value={sectionId} onChange={e => setSectionId(e.target.value)} disabled={busy} required>{course.sections.map(s => <option key={s.id} value={s.id}>{s.title}</option>)}</select></label>}
          <div className="management-actions"><button type="button" disabled={busy} onClick={() => setDialog(null)}>Hủy</button><button className="btn-primary" disabled={busy || !newTitle.trim()}>{busy ? "Đang thêm..." : dialog === "lesson" ? "Thêm lesson" : "Thêm section"}</button></div>
        </form>}
    </EditorDialog>}
  </div>;
}
