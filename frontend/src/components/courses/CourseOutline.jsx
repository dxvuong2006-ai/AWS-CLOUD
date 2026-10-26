import { Link } from "react-router-dom";

export default function CourseOutline({
  sections,
  courseId,
  currentLessonId,
  completedIds = new Set(),
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
          </h3>
          <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
            {s.lessons.map((l) => {
              const label = `${l.title} · ${Math.round(l.duration / 60)} phút`;
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
      ))}
    </div>
  );
}