export default function SummaryPanel({ summary, keyConcepts }) {
  return (
    <div className="card">
      <h3 className="card-title">Tóm tắt bài học</h3>
      <p style={{ margin: 0, lineHeight: 1.6 }}>{summary}</p>
      {keyConcepts?.length > 0 && (
        <>
          <h3 className="card-title" style={{ marginTop: 16 }}>Khái niệm chính</h3>
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            {keyConcepts.map((k) => (
              <li key={k}>{k}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}