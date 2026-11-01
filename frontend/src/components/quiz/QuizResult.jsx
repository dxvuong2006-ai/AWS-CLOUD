import { getScoreBand, PASS_THRESHOLD } from "../../utils/scoreBand";

export default function QuizResult({ result }) {
  const band = getScoreBand(result.score_percent);

  return (
    <div className="result-grid">
      <div className="card">
        <div className="result-label">Điểm của bạn</div>
        <div className="result-score">{result.score_percent}%</div>
        <span className={`badge badge-${band.tone}`}>
          ● {result.passed ? "Đạt" : "Chưa đạt"}
        </span>
        <p className="result-sub">
          {result.correct_count}/{result.total_questions} câu đúng · cần đạt {PASS_THRESHOLD}%
        </p>
        <p>{band.message}</p>
      </div>

      <div className="card">
        <h3 className="card-title">Khái niệm cần xem lại</h3>
        {result.review_concepts.length === 0 ? (
          <p>Bạn không có khái niệm nào cần xem lại.</p>
        ) : (
          result.review_concepts.map((c) => (
            <div key={`${c.concept}-${c.question_number}`} className="review-row">
              <div>
                <strong>{c.concept}</strong>
                <small>Sai ở câu {c.question_number}</small>
              </div>
              <button className="btn-secondary" disabled title="AI Tutor làm ở tuần 4">
                Ôn với Tutor
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}