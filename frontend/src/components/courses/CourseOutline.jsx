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
    <div>
      {sections.map((s, i) => (
        <div key={s.id} className="card" style={{ marginBottom: 16 }}>
          <h3 style={{ fontSize: 15, margin: "0 0 12px" }}>
            Section {i + 1}: {s.title}
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
                <li key={l.id} style={{ display: "flex", gap: 8, padding: "4px 0" }}>
                  <span
                    title={done ? "Đã hoàn thành" : "Chưa hoàn thành"}
                    style={{
                      width: 18,
                      color: done ? "var(--success)" : "var(--text-muted)",
                      fontWeight: 700,
                    }}
                  >
                    {done ? "✓" : "○"}
                  </span>
                  {courseId && unlockedSectionIds.includes(String(s.id)) ? (
                    <span><Link
                      to={`/courses/${courseId}/lessons/${l.id}`}
                      style={{
                        color: isCurrent ? "var(--accent)" : "inherit",
                        fontWeight: isCurrent ? 600 : 400,
                      }}
                    >
                      {label}
                    </Link> · <Link to={`/courses/${courseId}/sections/${s.id}/lessons/${l.id}/flashcards`}>Ôn flashcard</Link></span>
                  ) : (
                    <span>{label}</span>
                  )}
                </li>
              );
            })}
          </ul>
          {courseId && <p>{unlockedSectionIds.includes(String(s.id)) ?
            <Link to={`/courses/${courseId}/sections/${s.id}/checkpoint`}>Làm checkpoint</Link> :
            <Link to={`/courses/${courseId}/sections/${s.id}`}>Xem điều kiện mở section</Link>}</p>}
        </div>
      ))}
    </div>
  );
}
