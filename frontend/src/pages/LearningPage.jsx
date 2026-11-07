import { MOCK_COMPLETION_PERCENT } from "../config/learning";
import { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useCourse } from "../hooks/useCourses";
import { useLesson } from "../hooks/useLesson";
import { useLessonProgress } from "../hooks/useLessonProgress";
import { fetchSectionQuiz } from "../api/quizzes.api";
import "../components/learning/learning.css";
import VideoPlayer from "../components/learning/VideoPlayer";
import TranscriptPanel from "../components/learning/TranscriptPanel";
import SummaryPanel from "../components/learning/SummaryPanel";
import SectionGate from "../components/learning/SectionGate";
import { nextLesson } from "../utils/sectionAccess";
import { useAuth } from "../context/AuthContext";

function errorMessage(err) {
  if ([403,409,422,502].includes(err?.status)) return err.message;
  if ([404,405,501].includes(err?.status)) return "Bài học chưa có học liệu khả dụng. Vui lòng thử lại sau.";
  return "Không tải được bài học.";
}

// Tìm lesson nằm ở section nào, là bài thứ mấy trong section đó
function locateLesson(sections, lessonId) {
  const list = sections ?? [];
  for (let s = 0; s < list.length; s++) {
    const i = list[s].lessons.findIndex((l) => l.id === lessonId);
    if (i !== -1) {
      return { section: list[s], sectionNo: s + 1, lessonNo: i + 1 };
    }
  }
  return null;
}

export default function LearningPage() {
  const { courseId, lessonId } = useParams();
  const { user } = useAuth();
  return <SectionGate key={`${user.id}:${courseId}:${lessonId}`} courseId={courseId} lessonId={lessonId}><LearningContent /></SectionGate>;
}

function LearningContent() {
  const { courseId, lessonId } = useParams();
  const course = useCourse(courseId);
  const lesson = useLesson(lessonId, courseId);
  const progress = useLessonProgress(courseId, lessonId);
  const videoRef = useRef(null);
 
  const [currentTime, setCurrentTime] = useState(0);

  // Đổi sang bài khác thì đặt lại bộ đếm
useEffect(() => {
  setCurrentTime(0);
}, [lessonId]);

  const where = locateLesson(course.data?.sections, lessonId);
  const sectionId = where?.section.id;
  const next = nextLesson(course.data?.sections, lessonId);
  const [checkpointAccess, setCheckpointAccess] = useState(null);

  // Kiểm tra quyền từ API mỗi khi tiến độ đã lưu thay đổi.
  useEffect(() => {
    let cancelled = false;
    setCheckpointAccess((previous) => {
      const sameLesson =
        previous?.courseId === courseId &&
        previous?.sectionId === sectionId &&
        previous?.lessonId === lessonId;

      // Giữ trạng thái hiện tại khi kiểm tra lại cùng bài.
      // Chuyển bài/section/khóa thì reset quyền.
      return sameLesson ? previous : null;
    });
    if (!sectionId) return;
    fetchSectionQuiz(sectionId, courseId, lessonId)
      .then(() => {
        if (!cancelled) setCheckpointAccess({ courseId, sectionId, lessonId, allowed: true });
      })
      .catch((err) => {
        if (!cancelled) setCheckpointAccess({
          courseId,
          sectionId,
          lessonId,
          allowed: false,
          message: err.status === 403
            ? (err.message && err.message !== "HTTP 403"
              ? err.message
              : "Checkpoint chưa được mở. Hãy tiếp tục học để đủ điều kiện.")
            : err.status === 404
              ? "Section này chưa có checkpoint."
              : "Chưa xác nhận được quyền làm checkpoint. Hãy thử lại.",
        });
      });
    return () => { cancelled = true; };
  }, [courseId, sectionId, lessonId, progress.courseProgress]);

  const canTakeCheckpoint =
    checkpointAccess?.lessonId === lessonId && checkpointAccess?.courseId === courseId &&
    checkpointAccess?.sectionId === sectionId && checkpointAccess?.allowed === true;

  if (lesson.loading || course.loading || progress.loading) {
    return <div className="page">Đang tải...</div>;
  }
  if (lesson.error || course.error || !where) {
    return (
      <div className="page">
        <p>{errorMessage(lesson.error ?? course.error)}</p>
        <button onClick={lesson.reload}>Thử lại</button>
        <Link to={`/courses/${courseId}`}>← Về khóa học</Link>
      </div>
    );
  }

  if (progress.error) return <div className="page"><p role="alert">Không tải được tiến độ học. Hãy thử lại để khôi phục đúng vị trí.</p><button onClick={progress.reload}>Thử lại</button><p><Link to={`/courses/${courseId}`}>Về khóa học</Link></p></div>;
  const done = progress.courseProgress?.lessons.find(
    (l) => l.lesson_id === lessonId
  )?.completed;


  const handleSeek = (seconds) => {
    if (videoRef.current) {
      if (!Number.isFinite(seconds) || !Number.isFinite(videoRef.current.duration)) return;
      videoRef.current.currentTime = Math.max(0, Math.min(seconds, videoRef.current.duration));
      videoRef.current.play().catch(() => {});
    }
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="breadcrumb">
            <Link to={`/courses/${courseId}`}>{course.data.title}</Link>
            {where && ` / Section ${where.sectionNo} · ${where.section.title}`}
          </div>
            <h1>
              {where ? `Bài ${where.lessonNo} · ` : ""}
              {lesson.data.title}
              {done && (
                <span style={{ marginLeft: 12, fontSize: 13, color: "var(--success)" }}>
                  ✓ Đã hoàn thành
                </span>
              )}
            </h1>
        </div>
        <div className="page-actions">
          <button className="btn-secondary" disabled title="Chưa có flashcard">
            Flashcard
          </button>
          {where && (
            canTakeCheckpoint ? (
              <Link
                className="btn-primary"
                to={`/courses/${courseId}/sections/${sectionId}/checkpoint`}
                state={{ lessonId }}
              >
                → Làm checkpoint
              </Link>
            ) : (
              <button
                className="btn-secondary"
                disabled
                title={checkpointAccess?.lessonId === lessonId && checkpointAccess?.courseId === courseId && checkpointAccess?.sectionId === sectionId
                  ? checkpointAccess.message
                  : "Đang kiểm tra quyền làm checkpoint..."}
              >
                → Làm checkpoint
              </button>
            )
          )}
        </div>
      </div>

      {import.meta.env.VITE_USE_MOCK === "true" && <p role="note">Chế độ demo: video và học liệu mẫu. Ngưỡng hoàn thành bài: {MOCK_COMPLETION_PERCENT}%.</p>}
      {progress.saveError && (
        <p style={{ color: "var(--error)" }}>
          Không lưu được tiến độ học. Tiến độ gần nhất có thể chưa được ghi.
          <button onClick={progress.retry}>Thử lưu lại</button>
        </p>
      )}

      <div className="learning-layout">
        <div className="learning-main">
          {lesson.mediaError && <div role="alert"><p>{lesson.mediaError.message}</p><button disabled={lesson.refreshing} onClick={lesson.refreshVideo}>Tải lại video</button></div>}
          {lesson.refreshing && <p role="status">Đang lấy lại video...</p>}
          <VideoPlayer
            key={`${courseId}:${lessonId}`}
            src={lesson.media?.videoUrl}
            sourceVersion={lesson.sourceVersion}
            onError={lesson.onVideoError}
            videoRef={videoRef}
            onTimeUpdate={setCurrentTime}
            startAt={progress.lastPosition}
            onProgress={progress.save}
            onStart={progress.start}
          />
          <SummaryPanel summary={lesson.data.summary} keyConcepts={lesson.data.keyConcepts} />
        </div>
        <TranscriptPanel
          segments={lesson.data.transcript}
          currentTime={currentTime}
          onSeek={handleSeek}
        />
      </div>
      <nav aria-label="Điều hướng bài học" style={{ display: "flex", justifyContent: "space-between", marginTop: 24 }}>
        <Link to={`/courses/${courseId}`}>← Lộ trình khóa học</Link>
        {next && <Link to={`/courses/${courseId}/lessons/${next.id}`}>Bài tiếp theo: {next.title} →</Link>}
      </nav>
    </div>
  );
}
