import "../styles/student.css";
import "../styles/management.css";
import "../styles/screens21-35.css";
import "../styles/workflows.css";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { startRemediation, advanceRemediation, submitPractice } from "../api/tutor.api";
export default function TutorPage() {
  const { attemptId } = useParams();
  const [session, setSession] = useState(null), [step, setStep] = useState(1);
  const [error, setError] = useState(""), [busy, setBusy] = useState(false), [loading, setLoading] = useState(true);
  const [index, setIndex] = useState(0), [cardIndex, setCardIndex] = useState(0), [flipped, setFlipped] = useState(false);
  const [questionIndex, setQuestionIndex] = useState(0), [answers, setAnswers] = useState({});
  const [version, setVersion] = useState(0), [showResult, setShowResult] = useState(true);
  const guard = useRef(false);
  useEffect(() => {
    let active = true; setLoading(true); setError(""); setSession(null); setAnswers({}); setIndex(0); setCardIndex(0); setQuestionIndex(0);
    startRemediation(attemptId).then(data => { if (active) { setSession(data); setStep(data.review_completed ? 3 : data.explanation_completed ? 2 : 1); setShowResult(true); } })
      .catch(e => { if (active) setError(e.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [attemptId, version]);
  async function act(fn) {
    if (guard.current) return;
    guard.current = true; setBusy(true); setError("");
    try { await fn(); } catch (e) { setError(e.message); } finally { guard.current = false; setBusy(false); }
  }
  if (loading) return <div className="page student-page"><h1>Ôn tập với AI Tutor</h1><p role="status">Đang chuẩn bị nội dung ôn tập...</p></div>;
  if (!session) return <div className="page student-page"><h1>Ôn tập với AI Tutor</h1><p role="alert">{error}</p><button className="btn-secondary" onClick={() => setVersion(v => v + 1)}>Thử lại</button><Link to="/my-courses">Về khóa học</Link></div>;
  const current = session.errors[index], card = session.cards[cardIndex], question = session.practice_questions[questionIndex], result = session.result;
  const base = "/courses/" + session.course_id;
  const checkpoint = base + "/sections/" + session.section_id + "/checkpoint";
  const resultVisible = result && showResult;
  const empty = (step === 1 && !current) || (step === 2 && !card) || (step === 3 && !question && !resultVisible);
  if (empty) return <div className="page student-page"><h1>Ôn tập với AI Tutor</h1><p role="alert">Bài này chưa có đủ nội dung ôn tập (lỗi, flashcard hoặc câu practice).</p><Link to={base}>Về lộ trình</Link></div>;
  return <div className="page student-page tutor-page">
    <h1>{resultVisible ? "Kết quả luyện tập" : "Ôn tập với AI Tutor"}</h1><p className="student-subtitle">{session.section_title}</p>
    <ol className="tutor-steps" aria-label="Các bước ôn tập">{["Giải thích lỗi", "Xem lại bài", "Luyện tập"].map((label, i) => <li key={label} className={(step === i + 1 ? "active " : "") + ((i === 0 && session.explanation_completed) || (i === 1 && session.review_completed) || (i === 2 && session.remediation_completed) ? "done" : "")}><span>{((i === 0 && session.explanation_completed) || (i === 1 && session.review_completed) || (i === 2 && session.remediation_completed)) ? "✓" : i + 1}</span>{label}</li>)}</ol>
    {error && <p role="alert" className="workflow-error">{error}</p>}
    {resultVisible ? <>
      <div className={"workflow-banner " + (result.passed ? "success" : "warning")}>{result.passed ? "Bạn đã đạt " : "Bạn mới đạt "}{result.correct} / {result.total} câu practice. {result.passed ? "Đã hoàn thành yêu cầu ôn tập cho lượt checkpoint này." : "Cần đúng ít nhất " + Math.ceil(result.total * 2 / 3) + " câu để hoàn thành."}</div>
      <section className="card practice-result"><div className="spec-card-heading"><h2>Chi tiết practice</h2><span className={"status-chip " + (result.passed ? "success" : "warning")}>{result.passed ? "Đạt" : "Chưa đạt"} {result.correct} / {result.total}</span></div>
        {result.questions.map((q, i) => <div className="practice-result-row" key={i}><span className={"result-question-icon " + (q.is_correct ? "correct" : "incorrect")}>{q.is_correct ? "✓" : "×"}</span><div><strong>Câu {i + 1} · {q.question}</strong>{!q.is_correct && <p>Đáp án đúng: {q.correct_answer}</p>}<p>{q.explanation}</p></div></div>)}
      </section><div className="workflow-actions">{result.passed ? <><Link className="btn-primary" to={checkpoint}>↻ Làm lại checkpoint</Link><Link className="btn-secondary" to={base}>Về lộ trình</Link></> :
        <><button className="btn-primary" disabled={busy} onClick={() => act(async () => { const data = await startRemediation(attemptId, true); setSession(data); setAnswers({}); setQuestionIndex(0); setStep(3); setShowResult(true); })}>↻ Làm bộ practice mới</button><button className="btn-secondary" disabled={busy} onClick={() => { setShowResult(false); setStep(2); }}>Xem lại bài học</button><button className="btn-secondary" disabled>Làm lại checkpoint</button></>}</div>
    </> : step === 1 ? <>
      <div className="tutor-explanation-layout"><nav aria-label="Các lỗi cần ôn" className="tutor-error-list">{session.errors.map((row, i) => <button key={row.id} className={index === i ? "active" : ""} disabled={busy} onClick={() => setIndex(i)}><span className="status-chip error">Lỗi {i + 1}</span><strong>{row.concept}</strong>{session.seen_errors.includes(row.id) && <span aria-label="Đã xem">✓</span>}</button>)}</nav>
        <article className="card tutor-explanation"><h2>Lỗi {index + 1} · {current.concept}</h2><p className="management-subtitle">Bạn chọn: {current.selected || "Chưa trả lời"}</p>
          <section className="misconception"><h3>Bạn đã hiểu sai điều gì</h3><p>{current.misconception}</p></section>
          <section className="explanation"><h3>Giải thích ngắn gọn</h3><p>{current.explanation}</p></section>
          <section className="example"><h3>Đối chiếu với bài giảng</h3><p>{current.example}</p></section>
          <p className="management-subtitle">Tutor tập trung vào khái niệm bạn cần ôn, không giải lại toàn bộ checkpoint.</p>
        </article></div>
      <div className="workflow-actions spread"><button className="btn-secondary" disabled={busy} onClick={() => act(async () => { setSession(await advanceRemediation(session.id, "explanation", current.id)); setIndex(i => Math.min(i + 1, session.errors.length - 1)); })}>{busy ? "Đang lưu..." : "Đã xem · Lỗi tiếp theo →"}</button><button className="btn-primary" disabled={busy || !session.explanation_completed} onClick={() => setStep(2)}>Tiếp tục: xem lại bài →</button></div>
    </> : step === 2 ? <>
      <p className="management-subtitle">Ôn hết bộ thẻ liên quan để mở bước luyện tập.</p>
      <div className="workflow-two-columns"><section className="card"><h2>Đoạn bài học liên quan</h2><div className="tutor-video-placeholder" aria-hidden="true">▶</div><h3>{session.lesson_title}</h3><Link className="btn-secondary" to={base + "/lessons/" + session.lesson_id}>Xem bài học</Link><p className="management-subtitle">Bạn có thể quay lại phiên này để tiếp tục ôn thẻ.</p></section>
        <section className="card"><div className="spec-card-heading"><h2>Flashcard liên quan</h2><span className={"status-chip " + (session.review_completed ? "success" : "neutral")}>{session.reviewed_cards.length} / {session.cards.length} đã ôn</span></div>
          <button className={"tutor-review-card " + (flipped ? "flipped" : "")} aria-pressed={flipped} onClick={() => setFlipped(v => !v)}><small>{flipped ? "Giải thích" : "Khái niệm"} · thẻ {cardIndex + 1}</small><strong>{flipped ? card.back : card.front}</strong><span>{flipped ? "Bấm để xem mặt trước" : "Bấm để lật thẻ"}</span></button>
          <div className="workflow-actions"><button className="btn-secondary" disabled={!cardIndex || busy} onClick={() => { setCardIndex(i => i - 1); setFlipped(false); }}>← Thẻ trước</button><button className="btn-primary" disabled={!flipped || busy} onClick={() => act(async () => { setSession(await advanceRemediation(session.id, "card", card.id)); setCardIndex(i => Math.min(i + 1, session.cards.length - 1)); setFlipped(false); })}>Đã ôn · Thẻ tiếp →</button></div>
        </section></div>
      <div className="workflow-actions spread"><button className="btn-secondary" onClick={() => setStep(1)}>← Quay lại</button><button className="btn-primary" disabled={!session.review_completed || busy} onClick={() => { setStep(3); setShowResult(true); }}>Sang luyện tập →</button></div>
    </> : <>
      <div className="practice-layout"><section className="card"><div className="spec-card-heading"><strong>Practice · Câu {questionIndex + 1} / {session.practice_questions.length}</strong><span className="status-chip neutral">{session.practice_source === "ai" ? "Do AI tạo" : "Từ học liệu bài giảng"}</span></div>
        <h2>{question.question}</h2><div className="practice-options">{question.options.map((option, i) => <button className={answers[questionIndex] === option ? "selected" : ""} aria-pressed={answers[questionIndex] === option} disabled={busy} key={i} onClick={() => setAnswers(previous => ({ ...previous, [questionIndex]: option }))}><span>{String.fromCharCode(65 + i)}</span>{option}</button>)}</div>
        <div className="workflow-actions spread"><button className="btn-secondary" disabled={!questionIndex || busy} onClick={() => setQuestionIndex(i => i - 1)}>← Câu trước</button>
          {questionIndex < session.practice_questions.length - 1 ? <button className="btn-primary" disabled={busy} onClick={() => setQuestionIndex(i => i + 1)}>Câu tiếp →</button> : <button className="btn-primary" disabled={busy || session.practice_questions.some((_, i) => answers[i] == null)} onClick={() => act(async () => { setSession(await submitPractice(session.id, session.practice_questions.map((_, i) => answers[i]))); setShowResult(true); })}>{busy ? "Đang chấm..." : "Nộp practice"}</button>}</div>
      </section><aside className="card"><h2>Yêu cầu</h2><div className="practice-target"><span>Cần đúng</span><strong>{Math.ceil(session.practice_questions.length * 2 / 3)} / {session.practice_questions.length} câu</strong></div><div className="practice-navigator">{session.practice_questions.map((_, i) => <button key={i} className={questionIndex === i ? "active" : ""} aria-label={"Câu " + (i + 1) + (answers[i] != null ? ", đã trả lời" : "")} disabled={busy} onClick={() => setQuestionIndex(i)}>{i + 1}</button>)}</div><p className="management-subtitle">Đạt yêu cầu mới hoàn thành bước luyện tập.</p><button className="btn-secondary" disabled={busy} onClick={() => setStep(2)}>Xem lại bài</button></aside></div>
    </>}
  </div>;
}
