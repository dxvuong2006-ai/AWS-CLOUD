import { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useCourse } from "../hooks/useCourses";
import { useLesson } from "../hooks/useLesson";
import { useLessonProgress } from "../hooks/useLessonProgress";
import "../components/learning/learning.css";
import VideoPlayer from "../components/learning/VideoPlayer";
import TranscriptPanel from "../components/learning/TranscriptPanel";
import SummaryPanel from "../components/learning/SummaryPanel";

function errorMessage(err) {
  if (err?.status === 403) return "Bạn chưa mở khóa bài học này.";
  if (err?.status === 404) return "Không tìm thấy bài học.";
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
  const course = useCourse(courseId);
  const lesson = useLesson(lessonId);
  const progress = useLessonProgress(courseId, lessonId);
  const videoRef = useRef(null);
  const lastSavedAt = useRef(0);
  const [currentTime, setCurrentTime] = useState(0);

  // Đổi sang bài khác thì đặt lại bộ đếm
  useEffect(() => {
    lastSavedAt.current = 0;
    setCurrentTime(0);
  }, [lessonId]);

  if (lesson.loading || course.loading || progress.loading) {
    return <div className="page">Đang tải...</div>;
  }
  if (lesson.error || course.error) {
    return (
      <div className="page">
        <p>{errorMessage(lesson.error ?? course.error)}</p>
        <Link to={`/courses/${courseId}`}>← Về khóa học</Link>
      </div>
    );
  }

  const where = locateLesson(course.data.sections, lessonId);
  const done = progress.courseProgress?.lessons.find(
    (l) => l.lesson_id === lessonId
  )?.completed;

  const handleTimeUpdate = (t) => {
    setCurrentTime(t);
    if (Math.abs(t - lastSavedAt.current) >= 10) {
      lastSavedAt.current = t;
      progress.save(t, videoRef.current?.duration);
    }
  };

  const saveNow = () => {
    const v = videoRef.current;
    if (v) progress.save(v.currentTime, v.duration);
  };

  const handleSeek = (seconds) => {
    if (videoRef.current) {
      videoRef.current.currentTime = seconds;
      videoRef.current.play();
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
          <button className="btn-primary" disabled title="Chưa có checkpoint">
            → Làm checkpoint
          </button>
        </div>
      </div>

      {progress.saveError && (
        <p style={{ color: "var(--error)" }}>
          Không lưu được tiến độ học. Tiến độ gần nhất có thể chưa được ghi.
        </p>
      )}

      <div className="learning-layout">
        <div className="learning-main">
          <VideoPlayer
            src={lesson.data.videoUrl}
            videoRef={videoRef}
            onTimeUpdate={handleTimeUpdate}
            startAt={progress.lastPosition}
            onPause={saveNow}
            onEnded={saveNow}
          />
          <SummaryPanel summary={lesson.data.summary} />
        </div>
        <TranscriptPanel
          segments={lesson.data.transcript}
          currentTime={currentTime}
          onSeek={handleSeek}
        />
      </div>
    </div>
  );
}