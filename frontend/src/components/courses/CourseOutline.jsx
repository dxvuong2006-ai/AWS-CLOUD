export default function CourseOutline({ sections }) {
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
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            {(s.lessons ?? []).map((l) => {
              const durationSeconds = l.duration_seconds ?? l.duration;
              const duration =
                Number.isFinite(durationSeconds) && durationSeconds > 0
                  ? ` · ${Math.round(durationSeconds / 60)} phút`
                  : "";

              return (
                <li key={l.id}>
                  {l.title}
                  {duration}
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}