import { Link } from "react-router-dom";

export default function CourseOutline({
  sections,
  courseId,
  currentLessonId,
  completedIds = new Set(),
  unlockedSectionIds = [],
}) {
  if (!sections || sections.length === 0) {
    return <p>Khóa học chưa có nội dung.</p>;
  }

  return (
    <div className={courseId ? "course-outline is-enrolled" : "course-outline"}>
      {sections.map((s, i) => (
        <div key={s.id} className={"card outline-section " + (courseId && !unlockedSectionIds.includes(String(s.id)) ? "is-locked" : "")}>
          <h3 className="outline-section-title" style={{ fontSize: 15, margin: "0 0 12px" }}>
            {courseId && <span className="outline-section-marker" aria-hidden="true">{unlockedSectionIds.includes(String(s.id)) ? "●" : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8 10V6a4 4 0 0 1 8 0v4" /></svg>}</span>}Section {i + 1} · {s.title}<span className="outline-count">{s.lessons?.length ?? 0} lesson</span>
            {courseId && !unlockedSectionIds.includes(String(s.id)) && " · Đang khóa"}
          </h3>
          <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
            {(s.lessons ?? []).map((l) => {
              const durationSeconds = l.duration_seconds ?? l.duration;
              const duration =
                Number.isFinite(durationSeconds) && durationSeconds > 0
                  ? ` · ${Math.round(durationSeconds / 60)} phút`
                  : "";
              const label = `${l.title}${duration}`;
              const isCurrent = l.id === currentLessonId;
              const done = completedIds.has(l.id);
              return (
                <li key={l.id} className={"outline-lesson " + (done ? "is-done" : isCurrent ? "is-current" : "")}>
                  <span
                    title={done ? "Đã hoàn thành" : "Chưa hoàn thành"}
                    style={{
                      width: 18,
                      color: done ? "var(--success)" : "var(--text-muted)",
                      fontWeight: 700,
                    }}
                  >
                    {done ? "✓" : courseId && unlockedSectionIds.includes(String(s.id)) ? "○" : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8 10V6a4 4 0 0 1 8 0v4" /></svg>}
                  </span>
                  {courseId && unlockedSectionIds.includes(String(s.id)) ? (
                    <span className="outline-lesson-content"><Link
                      to={`/courses/${courseId}/lessons/${l.id}`}
                      style={{
                        color: isCurrent ? "var(--accent)" : "inherit",
                        fontWeight: isCurrent ? 600 : 400,
                      }}
                    >
                      {label}
                    </Link>{done && <span className="outline-done">● Đã học</span>}{isCurrent && <span className="outline-resume">Học tiếp</span>}<Link className="outline-flashcard-link" to={`/courses/${courseId}/sections/${s.id}/lessons/${l.id}/flashcards`}>Ôn flashcard</Link></span>
                  ) : (
                    <span>{label}</span>
                  )}
                </li>
              );
            })}
          </ul>
          {courseId && <p className="outline-checkpoint-row"><span>{unlockedSectionIds.includes(String(s.id)) ? "Checkpoint Section " + (i + 1) : "Section đang khóa"}</span>{unlockedSectionIds.includes(String(s.id)) ?
            <Link to={`/courses/${courseId}/sections/${s.id}/checkpoint`}>Làm checkpoint</Link> :
            <Link to={`/courses/${courseId}/sections/${s.id}`}>Xem điều kiện mở section</Link>}</p>}
        </div>
      ))}
    </div>
  );
}
