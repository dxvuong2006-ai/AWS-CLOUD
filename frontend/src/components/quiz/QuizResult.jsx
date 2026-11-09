import { Link } from "react-router-dom";
import "../../styles/screens21-35.css";
import { getScoreBand, PASS_THRESHOLD } from "../../utils/scoreBand";

export default function QuizResult({ result }) {
  const band = getScoreBand(result.score_percent, { passed: result.passed });

  return (
    <div className={result.passed ? "checkpoint-result result-passed" : "checkpoint-result result-review" + (result.remediation_required ? " result-remediation" : "")}>
    {result.passed && <div className="result-success-banner">✓ Bạn đã đạt checkpoint. Quay lại lộ trình để xem section tiếp theo.</div>}
    {!result.passed && <div className={"result-review-banner " + (result.remediation_required ? "required" : "optional")} role="status">
      <span aria-hidden="true">{result.remediation_required ? "△" : "ⓘ"}</span>
      {result.remediation_required ? "Bạn cần hoàn thành ôn tập với AI Tutor trước khi được làm lại checkpoint." : result.can_retry ? "Bạn có thể ôn lại bài hoặc làm lại checkpoint ngay." : "Bạn chưa đạt checkpoint. Hãy xem lại các câu trả lời bên dưới."}
    </div>}
    <div className="result-grid">
      <div className="card">
        <div className="result-label">Điểm của bạn</div>
        <div className="result-score">{result.score_percent}%</div>
        <span className={`badge badge-${band.tone}`}>
          ● {result.passed ? "Đạt" : result.remediation_required ? "Cần ôn tập bắt buộc" : "Chưa đạt"}
        </span>
        <p className="result-sub">
          {result.correct_count} / {result.total_questions} câu đúng{!result.passed && <> · cần đạt {PASS_THRESHOLD}%</>}
        </p>
        {result.created_at && <p className="result-date">Lượt làm {result.attempt_number} · Đã nộp: {new Date(result.created_at).toLocaleString("vi-VN")}</p>}
        {result.passed ? <p className="result-pass-note">Bạn đã đạt checkpoint. Quay lại lộ trình để xem section tiếp theo.</p>
          : null}
      </div>

      {result.remediation_required && <section className="card result-requirements">
        <h2>Việc cần hoàn thành để làm lại</h2>
        <ol>
          <li><strong>Nghe AI giải thích từng lỗi</strong><small>{result.review_concepts.length} khái niệm cần ôn</small></li>
          <li><strong>Xem lại một phần bài học hoặc flashcard liên quan</strong><small>Hoàn thành ít nhất một</small></li>
          <li><strong>Trả lời 2–3 câu practice do AI tạo</strong><small>Cần đúng ít nhất 2 / 3 câu</small></li>
        </ol>
      </section>}
      <details className="card result-concepts">
        <summary className="card-title">Khái niệm cần xem lại</summary>
        {result.review_concepts.length === 0 ? (
          <p>Bạn không có khái niệm nào cần xem lại.</p>
        ) : (
          result.review_concepts.map((c) => (
            <div key={`${c.concept}-${c.question_number}`} className="review-row">
              <div>
                <strong>{c.concept}</strong>
                <small>Sai ở câu {c.question_number}</small>
              </div>
              {result.id && <Link className="btn-secondary" to={"/tutor/attempts/" + result.id}>Ôn với Tutor</Link>}
            </div>
          ))
        )}
      </details>
    </div>
    <section className="checkpoint-review" aria-label="Chi tiết từng câu">
      <h2>Chi tiết từng câu</h2>
      {!(result.question_results ?? []).length && <p>Chưa có chi tiết câu trả lời cho lượt làm này.</p>}
      {(result.question_results ?? []).map(row => <details className="card result-question" key={row.question_id} open={result.passed && !row.is_correct}>
        <summary><h3><span className={"result-question-icon " + (row.is_correct ? "correct" : "incorrect")} aria-hidden="true">{row.is_correct ? "✓" : "×"}</span>Câu {row.question_number} · {row.text}</h3></summary>
        <p className={`badge badge-${row.is_correct ? "success" : "error"}`}>{row.is_correct ? "Đúng" : "Sai"}</p>
        <p>Bạn chọn: <strong>{row.selected_answer ?? "Chưa trả lời — tính là sai"}</strong></p>
        {row.correct_answer != null && <p>Đáp án đúng: <strong>{row.correct_answer}</strong></p>}
        <p><strong>Giải thích: </strong>{row.explanation || "Chưa có lời giải cho câu này."}</p>
      </details>)}
    </section>
    {!result.passed && <div className="result-tutor-action">
      {result.id ? <Link className="btn-primary" to={"/tutor/attempts/" + result.id}>
        <span aria-hidden="true">✧</span> {result.remediation_required ? "Bắt đầu ôn tập với AI" : "Ôn với AI Tutor"}
      </Link> : <p className="result-tutor-note">Chưa nhận được mã lượt làm. Hãy tải lại kết quả.</p>}
    </div>}
    </div>
  );
}
