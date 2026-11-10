export default function SummaryPanel({ summary, keyConcepts }) {
  const text = typeof summary === "string" ? summary.trim() : "";
  const concepts = Array.isArray(keyConcepts)
    ? keyConcepts.filter((concept) => typeof concept === "string")
    : [];

  return (
    <div className="card lesson-summary">
      <h3 className="card-title">Tóm tắt bài học</h3>
      <p style={{ margin: 0, lineHeight: 1.6 }}>{text || "Chưa có tóm tắt"}</p>
      {concepts.length > 0 && (
        <>
          <h3 className="card-title" style={{ marginTop: 16 }}>Khái niệm chính</h3>
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            {concepts.map((k) => (
              <li key={k}>{k}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
