import { useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useCourse } from "../hooks/useCourses";
import CourseOutline from "../components/courses/CourseOutline";
import { useCourseProgress } from "../hooks/useCourseProgress";
import { useEnrollments } from "../hooks/useEnrollments";
import { enrollCourse, enrollmentError } from "../api/enrollments.api";
import "../components/quiz/quiz.css";
export default function CourseDetailPage() {
  const {courseId}=useParams(); const {data:course,loading,error}=useCourse(courseId);
  const enrollments=useEnrollments(); const progress=useCourseProgress(courseId);
  const [busy,setBusy]=useState(false), [failure,setFailure]=useState(null), [success,setSuccess]=useState(false);
  const pending=useRef(false), dialog=useRef(null);
  const enrollment=enrollments.data.find(row=>row.course.id===courseId);
  const completedIds=new Set((progress?.lessons??[]).filter(l=>l.completed).map(l=>l.lesson_id));
  async function enroll() {
    if(pending.current)return; pending.current=true; setBusy(true); setFailure(null);
    try { await enrollCourse(courseId); setSuccess(true); enrollments.reload(); dialog.current.showModal(); }
    catch(err) { if(err.status===409) enrollments.reload(); setFailure(err); }
    finally { pending.current=false; setBusy(false); }
  }
  if(loading)return <div className="page">Đang tải...</div>;
  if(error)return <div className="page"><p>Không tải được khóa học.</p><Link to="/courses">Về danh sách</Link></div>;
  return <div className="page"><Link to="/courses">← Khám phá khóa học</Link>
    <h1>{course.title}</h1><p>{course.description}</p>
    {enrollments.loading ? <p>Đang kiểm tra đăng ký...</p> : enrollment ? <>
      <p>✓ Đã đăng ký</p>{enrollment.resume_lesson_id && <Link className="btn-primary" to={`/courses/${courseId}/lessons/${enrollment.resume_lesson_id}`}>Tiếp tục học</Link>}
    </> : <button className="btn-primary" disabled={busy || success} onClick={enroll}>{busy ? "Đang đăng ký..." : success ? "Đã đăng ký" : "Đăng ký học"}</button>}
    {(failure || enrollments.error) && <p role="alert">{enrollmentError(failure || enrollments.error)} <button onClick={enrollments.reload}>Thử tải lại</button></p>}
    <h2>Lộ trình khóa học</h2>
    {enrollment && <p><Link className="btn-secondary" to={`/flashcards?courseId=${encodeURIComponent(courseId)}`}>Ôn flashcard</Link></p>}
    <CourseOutline sections={course.sections} courseId={enrollment ? courseId : null} completedIds={completedIds} unlockedSectionIds={enrollment?.unlocked_section_ids ?? []} />
    <dialog ref={dialog} aria-labelledby="enrolled-title" onClose={()=>{}}>
      <h2 id="enrolled-title">Đăng ký thành công</h2><p>Khóa học đã được thêm vào Khóa học của tôi.</p>
      <button autoFocus className="btn-primary" onClick={()=>dialog.current.close()}>Xem lộ trình</button>
      <p><Link to="/my-courses">Khóa học của tôi</Link></p>
    </dialog>
  </div>;
}
