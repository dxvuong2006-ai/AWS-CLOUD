import { getScoreBand, PASS_THRESHOLD } from "../../utils/scoreBand";

export default function QuizResult({ result }) {
  const band = getScoreBand(result.score_percent, { passed: result.passed });

  return (
    <div className={result.passed ? "checkpoint-result result-passed" : "checkpoint-result"}>
    {result.passed && <div className="result-success-banner">✓ Bạn đã đạt checkpoint. Quay lại lộ trình để xem section tiếp theo.</div>}
    <div className="result-grid">
      <div className="card">
        <h2>{result.passed ? "Đạt checkpoint" : result.score_percent < 50 ? "Cần ôn tập AI bắt buộc" : "Chưa đạt — có thể ôn và làm lại"}</h2>
        <div className="result-label">Điểm của bạn · Lượt làm {result.attempt_number}</div>
        <div className="result-score">{result.score_percent}%</div>
        <span className={`badge badge-${band.tone}`}>
          ● {result.passed ? "Đạt" : "Chưa đạt"}
        </span>
        <p className="result-sub">
          {result.correct_count}/{result.total_questions} câu đúng · cần đạt {PASS_THRESHOLD}%
        </p>
        {result.created_at && <p>Đã nộp: {new Date(result.created_at).toLocaleString("vi-VN")}</p>}
        {result.passed ? <p>Bạn đã đạt checkpoint. Quay lại lộ trình để xem section tiếp theo.</p>
          : result.remediation_required ? <>
            <p>Hoàn thành cả ba việc trước khi làm lại:</p>
            <ol><li>Xem AI giải thích các lỗi.</li><li>Xem lại bài học hoặc flashcard liên quan.</li><li>Làm 2–3 câu practice và đúng ít nhất 2/3.</li></ol>
          </> : <p>{result.can_retry ? "Bạn có thể xem lại bài và làm lại checkpoint." : "Hiện bạn chưa được phép làm lại checkpoint này."}</p>}
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
              <button className="btn-secondary" disabled title="Chức năng ôn tập AI chưa sẵn sàng">
                Ôn với Tutor
              </button>
            </div>
          ))
        )}
      </div>
    </div>
    <section className="checkpoint-review" aria-label="Chi tiết từng câu">
      <h2>Chi tiết từng câu</h2>
      {!(result.question_results ?? []).length && <p>Chưa có chi tiết câu trả lời cho lượt làm này.</p>}
      {(result.question_results ?? []).map(row => <article className="card" key={row.question_id}>
        <h3><span className={"result-question-icon " + (row.is_correct ? "correct" : "incorrect")} aria-hidden="true">{row.is_correct ? "✓" : "×"}</span>Câu {row.question_number} · {row.text}</h3>
        <p className={`badge badge-${row.is_correct ? "success" : "error"}`}>{row.is_correct ? "Đúng" : "Sai"}</p>
        <p>Bạn chọn: <strong>{row.selected_answer ?? "Chưa trả lời — tính là sai"}</strong></p>
        {row.correct_answer != null && <p>Đáp án đúng: <strong>{row.correct_answer}</strong></p>}
        <p><strong>Giải thích: </strong>{row.explanation || "Chưa có lời giải cho câu này."}</p>
      </article>)}
    </section>
    </div>
  );
}
