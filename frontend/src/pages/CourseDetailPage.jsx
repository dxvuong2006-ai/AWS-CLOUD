import CourseArtwork from "../components/courses/CourseArtwork";
import "../styles/student.css";
import { useRef, useState } from "react";
import { useParams, Link, useSearchParams } from "react-router-dom";
import { useCourse } from "../hooks/useCourses";
import CourseOutline from "../components/courses/CourseOutline";
import { useCourseProgress } from "../hooks/useCourseProgress";
import { useEnrollments } from "../hooks/useEnrollments";
import { enrollCourse, enrollmentError } from "../api/enrollments.api";
import "../components/quiz/quiz.css";
export default function CourseDetailPage() {
  const {courseId}=useParams(); const [searchParams] = useSearchParams(); const fromProgress = searchParams.get("from") === "progress"; const {data:course,loading,error}=useCourse(courseId);
  const enrollments=useEnrollments(); const progress=useCourseProgress(courseId);
  const [busy,setBusy]=useState(false), [failure,setFailure]=useState(null), [success,setSuccess]=useState(false);
  const pending=useRef(false), dialog=useRef(null);
  const enrollment=enrollments.data.find(row=>row.course.id===courseId);
  const completedIds=new Set((progress?.lessons??[]).filter(l=>l.completed).map(l=>l.lesson_id));
  async function enroll() {
    if(pending.current)return; pending.current=true; setBusy(true); setFailure(null);
    try { await enrollCourse(courseId); setSuccess(true); enrollments.reload(); dialog.current.showModal(); }
    catch(err) {
      if(err.status===409) {
        setSuccess(true);
        await enrollments.reload();
        dialog.current.showModal();
      } else {
        setFailure(err);
      }
    }
    finally { pending.current=false; setBusy(false); }
  }
  if(loading)return <div className="page student-page student-CourseDetailPage">Đang tải...</div>;
  if(error)return <div className="page student-page student-CourseDetailPage"><p>Không tải được khóa học.</p><Link to="/courses">Về danh sách</Link></div>;
  return <div className={"page student-page student-CourseDetailPage " + (enrollment ? "course-enrolled" : "course-preview")}>
    <div className="breadcrumb"><Link to={fromProgress ? "/progress" : enrollment ? "/my-courses" : "/courses"}>{fromProgress ? "Tiến độ" : enrollment ? "Khóa học của tôi" : "Khám phá"}</Link> / {course.title}</div>
    <div className="page-head"><div><h1>{course.title}</h1><p className="student-subtitle">{enrollment ? <>Giảng viên · {course.instructor_name || course.instructor?.name || "LearnCloud"} · Tiến độ {enrollment.progress_percent ?? 0}%</> : course.description}</p></div>
      {enrollment && <Link className="btn-primary course-flashcard-button" to={"/flashcards?courseId=" + encodeURIComponent(courseId)}>▣ Ôn flashcard</Link>}
    </div>
    <div className="course-detail-layout">
      <div className="course-detail-main">
        {!enrollment && <section className="card course-overview"><h2>Bạn sẽ học được</h2>{course.learning_objectives?.length > 0 ? <ul className="course-objectives">{course.learning_objectives.map((objective, index) => <li key={index}>{objective}</li>)}</ul> : <p>{course.description}</p>}</section>}
        <section className="card course-content"><div className="course-content-heading"><h2>{enrollment ? "Lộ trình khóa học" : "Nội dung khóa học"}</h2><span>{course.sections?.length ?? 0} section · {course.sections?.reduce((count, section) => count + (section.lessons?.length ?? 0), 0) ?? 0} lesson</span></div>
          <CourseOutline currentLessonId={enrollment?.resume_lesson_id} sections={course.sections} courseId={enrollment ? courseId : null} completedIds={completedIds} unlockedSectionIds={enrollment?.unlocked_section_ids ?? []} returnTo={fromProgress ? "/progress" : null} />
        </section>
      </div>
      <aside className="card course-enrollment">
        <div className="course-art" aria-hidden="true"><CourseArtwork title={course.title} /></div>
        <p className="course-teacher"><span className="student-avatar" aria-hidden="true">{String(course.instructor_name || course.instructor?.name || "LearnCloud").trim().split(/\s+/).slice(-2).map(part => part[0]).join("").toUpperCase()}</span><span>Giảng viên<br /><strong>{course.instructor_name || course.instructor?.name || "LearnCloud"}</strong></span></p>
        <dl className="student-facts"><div><dt>Số section</dt><dd>{course.sections?.length ?? 0}</dd></div><div><dt>Số lesson</dt><dd>{course.sections?.reduce((count, section) => count + (section.lessons?.length ?? 0), 0) ?? 0}</dd></div></dl>
        {enrollments.loading ? <p>Đang kiểm tra đăng ký...</p> : enrollment ? <>
          <p className="badge badge-success">● Đã đăng ký</p>{enrollment.resume_lesson_id && <Link className="btn-primary" to={"/courses/" + courseId + "/lessons/" + enrollment.resume_lesson_id}>Tiếp tục học →</Link>}
        </> : <button className="btn-primary" disabled={busy || success} onClick={enroll}>{busy ? "Đang đăng ký..." : success ? "Đã đăng ký" : "Đăng ký học"}</button>}
        {!enrollment && <p className="enrollment-note">Truy cập ngay sau khi đăng ký.</p>}
      </aside>
    </div>
    {(failure || enrollments.error) && <p role="alert">{enrollmentError(failure || enrollments.error)} <button onClick={enrollments.reload}>Thử tải lại</button></p>}
    <dialog className="enrollment-dialog" ref={dialog} aria-labelledby="enrolled-title" onClose={()=>{}}>
      <div className="student-status-icon success" aria-hidden="true"><svg width="30" height="30" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="2.2"><circle cx="16" cy="16" r="12" /><path d="m10 16 4 4 8-9" /></svg></div>
      <h2 id="enrolled-title">Đăng ký thành công</h2><p>Bạn đã tham gia khóa học<br /><strong>{course.title}</strong></p>
      <div className="student-dialog-actions"><button className="btn-secondary" onClick={()=>dialog.current.close()}>Để sau</button><button autoFocus className="btn-primary" onClick={()=>dialog.current.close()}>→ Bắt đầu học</button></div><Link className="enrollment-library-link" to="/my-courses">Khóa học của tôi</Link>
    </dialog>
  </div>;
}