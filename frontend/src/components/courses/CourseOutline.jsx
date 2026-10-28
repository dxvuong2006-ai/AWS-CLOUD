import { Link } from "react-router-dom";

export default function CourseOutline({
  sections,
  courseId,
  currentLessonId,
  completedIds = new Set(),
}) {
  if (!sections) return null;
  if (sections.length === 0) {
    return <p>Khóa học chưa có nội dung.</p>;
  }

  return (
    <div>
      {[...sections]
        .sort((a, b) => (a.position ?? 0) - (b.position ?? 0))
        .map((s, i) => {
          const lessons = [...(s.lessons ?? [])].sort(
            (a, b) => (a.position ?? 0) - (b.position ?? 0)
          );
          return (
            <div key={s.id} className="card" style={{ marginBottom: 16 }}>
              <h3 style={{ fontSize: 15, margin: "0 0 12px" }}>
                Section {i + 1}: {s.title}
              </h3>
              {lessons.length === 0 && <p>Section này chưa có bài học.</p>}
              <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
                {lessons.map((l) => {
                  const durationSeconds = l.duration_seconds ?? l.duration;
                  const label = Number.isFinite(durationSeconds) && durationSeconds > 0
                    ? `${l.title} · ${Math.round(durationSeconds / 60)} phút`
                    : l.title;
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
                      {courseId ? (
                        <Link
                          to={`/courses/${courseId}/lessons/${l.id}`}
                          style={{
                            color: isCurrent ? "var(--accent)" : "inherit",
                            fontWeight: isCurrent ? 600 : 400,
                          }}
                        >
                          {label}
                        </Link>
                      ) : (
                        <span>{label}</span>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
    </div>
  );
}
