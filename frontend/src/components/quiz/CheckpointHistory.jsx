import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchQuizAttempts } from "../../api/quizzes.api";

export default function CheckpointHistory({ quizId, refreshKey }) {
  const [rows, setRows] = useState([]);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retry, setRetry] = useState(0);
  useEffect(() => { setOffset(0); }, [quizId, refreshKey]);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(null);
    fetchQuizAttempts(quizId, offset).then(data => { if (active) setRows(data); })
      .catch(err => { if (active) setError(err); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [quizId, offset, refreshKey, retry]);
  return <section className="card checkpoint-history" aria-label="Lịch sử checkpoint">
    <h2>Lịch sử làm bài</h2>
    {loading ? <p>Đang tải lịch sử...</p> : error ? <p role="alert">Không tải được lịch sử. <button onClick={() => setRetry(v => v + 1)}>Thử lại</button></p>
      : !rows.length ? <p>Chưa có lượt làm ở trang này.</p> : <ul>{rows.map(row => <li key={row.id}>
        <Link to={`/checkpoint-results/${encodeURIComponent(quizId)}/${encodeURIComponent(row.id)}`}>Lượt {row.attempt_number}: {row.score_percent}% · {row.passed ? "Đạt" : "Chưa đạt"}</Link>
      </li>)}</ul>}
    <div className="checkpoint-actions">
      <button className="btn-secondary" disabled={loading || offset === 0} onClick={() => setOffset(v => Math.max(0, v - 20))}>Trang trước</button>
      <button className="btn-secondary" disabled={loading || !!error || rows.length < 20} onClick={() => setOffset(v => v + 20)}>Trang sau</button>
    </div>
  </section>;
}
