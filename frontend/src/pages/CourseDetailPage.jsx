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
  if(loading)return <div className="page">?ang t?i...</div>;
  if(error)return <div className="page"><p>Kh?ng t?i ???c kh?a h?c.</p><Link to="/courses">V? danh s?ch</Link></div>;
  return <div className="page"><Link to="/courses">? Kh?m ph? kh?a h?c</Link>
    <h1>{course.title}</h1><p>{course.description}</p>
    {enrollments.loading ? <p>?ang ki?m tra ??ng k?...</p> : enrollment ? <>
      <p>? ?? ??ng k?</p>{enrollment.resume_lesson_id && <Link className="btn-primary" to={`/courses/${courseId}/lessons/${enrollment.resume_lesson_id}`}>Ti?p t?c h?c</Link>}
    </> : <button className="btn-primary" disabled={busy || success} onClick={enroll}>{busy ? "?ang ??ng k?..." : success ? "?? ??ng k?" : "??ng k? h?c"}</button>}
    {(failure || enrollments.error) && <p role="alert">{enrollmentError(failure || enrollments.error)} <button onClick={enrollments.reload}>Th? t?i l?i</button></p>}
    <h2>L? tr?nh kh?a h?c</h2>
    <CourseOutline sections={course.sections} courseId={enrollment ? courseId : null} completedIds={completedIds} unlockedSectionIds={enrollment?.unlocked_section_ids ?? []} />
    <dialog ref={dialog} aria-labelledby="enrolled-title" onClose={()=>{}}>
      <h2 id="enrolled-title">??ng k? th?nh c?ng</h2><p>Kh?a h?c ?? ???c th?m v?o Kh?a h?c c?a t?i.</p>
      <button autoFocus className="btn-primary" onClick={()=>dialog.current.close()}>Xem l? tr?nh</button>
      <p><Link to="/my-courses">Kh?a h?c c?a t?i</Link></p>
    </dialog>
  </div>;
}
