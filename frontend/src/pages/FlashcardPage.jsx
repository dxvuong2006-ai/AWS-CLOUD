import "../styles/student.css";

import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useEnrollments } from "../hooks/useEnrollments";
import { useCourse } from "../hooks/useCourses";
import SectionGate from "../components/learning/SectionGate";
import FlashcardDeck from "../components/learning/FlashcardDeck";
import { fetchFlashcards } from "../api/flashcards.api";
import { remediationReturn } from "../utils/flashcardProgress";
import "../components/learning/flashcard.css";

export default function FlashcardPage() {
  const { courseId, sectionId, lessonId } = useParams();
  const { user } = useAuth();
  const [params] = useSearchParams();
  if (!courseId) return <FlashcardLibrary key={user.id} />;
  return <SectionGate key={`${user.id}:${courseId}:${sectionId}:${lessonId}`} courseId={courseId} sectionId={sectionId}>
    <FlashcardLesson key={`${user.id}:${courseId}:${sectionId}:${lessonId}:${params.toString()}`} courseId={courseId} sectionId={sectionId} lessonId={lessonId} />
  </SectionGate>;
}

function FlashcardLibrary() {
  const enrollments = useEnrollments();
  const [params] = useSearchParams();
  const [selected, setSelected] = useState(params.get("courseId") || "");
  const courseId = enrollments.data.some(row => row.course.id === selected) ? selected : enrollments.data[0]?.course.id;
  return <div className="page student-page student-FlashcardPage"><h1>Flashcard</h1><p>Chọn bài học để ôn lại những khái niệm đã học.</p>
    {enrollments.loading ? <p role="status">Đang tải khóa học...</p> : enrollments.error ? <div role="alert"><p>Không tải được khóa học đã đăng ký.</p><button onClick={enrollments.reload}>Thử lại</button></div> : !enrollments.data.length ? <p>Bạn chưa đăng ký khóa học. <Link to="/courses">Khám phá khóa học</Link></p> : <>
      <div className="fc-course"><label htmlFor="fc-course-select">Khóa học</label><select id="fc-course-select" value={courseId} onChange={event => setSelected(event.target.value)}>{enrollments.data.map(row => <option key={row.course.id} value={row.course.id}>{row.course.title}</option>)}</select></div>
      <FlashcardPicker key={courseId} courseId={courseId} enrollment={enrollments.data.find(row => row.course.id === courseId)} />
    </>}
  </div>;
}

function FlashcardPicker({ courseId, enrollment }) {
  const course = useCourse(courseId);
  if (course.loading) return <p role="status">Đang tải danh sách bài...</p>;
  if (course.error) return <p role="alert">Không tải được bài học. <Link to={`/courses/${courseId}`}>Về khóa học</Link></p>;
  if (!course.data.sections.length) return <p>Khóa học chưa có bài học.</p>;
  return <div>{course.data.sections.map(section => <section key={section.id}><h2>{section.title}</h2>
    {!enrollment?.unlocked_section_ids.includes(String(section.id)) ? <p>Section đang khóa. <Link to={`/courses/${courseId}/sections/${section.id}`}>Xem điều kiện mở</Link></p> : <div className="flashcard-picker">{section.lessons.map(lesson => <Link className="card" key={lesson.id} to={`/courses/${courseId}/sections/${section.id}/lessons/${lesson.id}/flashcards`}>{lesson.title} → Ôn flashcard</Link>)}</div>}
  </section>)}</div>;
}

function FlashcardLesson({ courseId, sectionId, lessonId }) {
  const [params] = useSearchParams();
  const [state, setState] = useState({ loading: true });
  const [version, setVersion] = useState(0);
  const course = useCourse(courseId);
  const sessionId = params.get("remediationSessionId") || "";
  const returnTo = remediationReturn(courseId, sessionId, params.get("returnTo"));
  const videoSearch = returnTo ? `?${new URLSearchParams({ remediationSessionId: sessionId, returnTo })}` : "";
  useEffect(() => {
    let active = true;
    setState({ loading: true });
    fetchFlashcards(courseId, sectionId, lessonId).then(deck => { if (active) setState({ deck }); })
      .catch(error => { if (active) setState({ error }); });
    return () => { active = false; };
  }, [courseId, sectionId, lessonId, version]);
  const section = course.data?.sections.find(row => String(row.id) === String(sectionId));
  const lesson = section?.lessons.find(row => String(row.id) === String(lessonId));
  return <div className="page student-page student-FlashcardPage flashcard-lesson-page"><div className="breadcrumb"><Link to={`/courses/${courseId}`}>{course.data?.title || "Lộ trình khóa học"}</Link> / {section?.title} / {lesson?.title}</div>
    <h1>Ôn tập flashcard</h1><p className="student-subtitle">{course.data?.title} · {section?.title}</p><p><Link to={`/courses/${courseId}/lessons/${lessonId}${videoSearch}`}>← Về bài học</Link></p>
    {import.meta.env.VITE_USE_MOCK === "true" && <p role="note">Chế độ demo: thẻ mẫu từ khái niệm và tóm tắt bài học.</p>}
    {state.loading ? <p role="status">Đang tải flashcard...</p> : state.error ? <div role="alert"><p>{[404,405,501].includes(state.error.status) ? "Flashcard chưa có hoặc API chưa được kết nối." : state.error.message || "Không tải được flashcard."}</p><button onClick={() => setVersion(value => value + 1)}>Thử lại</button></div> : !state.deck.cards.length ? <p>Bài học chưa có flashcard được xuất bản.</p> :
      <FlashcardDeck key={`${state.deck.revision}:${version}`} deck={state.deck} courseId={courseId} sectionId={sectionId} lessonId={lessonId} sessionId={sessionId} returnTo={returnTo} />}
    {returnTo && (state.loading || state.error || !state.deck?.cards.length) && <p><Link to={returnTo}>← Quay lại phiên ôn tập AI</Link></p>}
  </div>;
}