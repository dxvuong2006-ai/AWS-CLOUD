import "../styles/management.css";
import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { fetchLessonContent, fetchReviewDraft, updateReviewDraft, approveReviewDraft } from "../api/review.api";
import { buildReviewDraftPayload, saveReviewDraft } from "../utils/saveReviewDraft";
import {
  removeReviewQuestionOption,
  updateReviewQuestionOption,
  validateReviewQuestions,
} from "../utils/reviewQuizValidation";

export default function LessonReviewPage() {
  const { lessonId } = useParams();
  const [params, setParams] = useSearchParams();
  const [lesson, setLesson] = useState(null);
  const [draft, setDraft] = useState(null);
  const [tab, setTab] = useState(params.get("tab") || "summary");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [approved, setApproved] = useState(false);
  const [approveOpen, setApproveOpen] = useState(false);

  useEffect(() => {
    Promise.all([fetchLessonContent(lessonId), fetchReviewDraft(lessonId)])
      .then(([lessonData, draftData]) => { setLesson(lessonData); setDraft(draftData); })
      .catch(e => setError(e.detail || e.message));
  }, [lessonId]);

  function changeTab(value) {
    setTab(value);
    setParams(value === "summary" ? {} : { tab: value });
  }

  async function save() {
    const validationErrors = validateReviewQuestions(draft.questions);
    if (validationErrors.length) {
      setSaved(false);
      setError(validationErrors[0]);
      setTab("quiz");
      setParams({ tab: "quiz" });
      return null;
    }
    setSaving(true);
    setSaved(false);
    setError("");
    try {
      const result = await saveReviewDraft(
        updateReviewDraft, lessonId, buildReviewDraftPayload(draft),
      );
      if (!result.draft) { setError(result.error); return null; }
      setDraft(result.draft); setSaved(true); setError("");
      return result.draft;
    }
    finally { setSaving(false); }
  }

  async function approve() {
    try {
      // Persist the instructor's current edits before approving that exact revision.
      const savedDraft = await save();
      if (!savedDraft) { setApproveOpen(false); return; }
      await approveReviewDraft(lessonId, { expected_revision: savedDraft.revision });
      setApproved(true);
      setApproveOpen(false);
    } catch (e) { setError(e.detail || e.message); }
  }

  if (error && !lesson) return <div className="page management-page"><p role="alert">{error}</p><Link to="/instructor/review-queue">Về hàng đợi</Link></div>;
  if (!lesson || !draft) return <div className="page management-page"><p>Đang tải...</p></div>;

  const transcript = lesson.transcript || [];
  const concepts = draft.key_concepts || [];
  const cards = draft.flashcards || [];
  const questions = draft.questions || [];
  const quizValidationErrors = validateReviewQuestions(questions);
  const updateConcept = (index, field, value) => editDraft({
    ...draft, key_concepts: concepts.map((item, itemIndex) => itemIndex === index ? { ...item, [field]: value } : item),
  });
  const updateCard = (index, field, value) => editDraft({
    ...draft, flashcards: cards.map((item, itemIndex) => itemIndex === index ? { ...item, [field]: value } : item),
  });
  const updateQuestion = (index, field, value) => editDraft({
    ...draft, questions: questions.map((item, itemIndex) => itemIndex === index ? { ...item, [field]: value } : item),
  });
  const editDraft = nextDraft => { setDraft(nextDraft); setSaved(false); setError(""); };

  return <div className="page management-page instructor-spec-page review-spec-page">
    <div className="breadcrumb"><Link to="/instructor/review-queue">Học liệu AI</Link> / {lesson.title}</div>
    <div className="page-head"><div><h1>Kiểm duyệt học liệu AI</h1><p className="management-subtitle">Đối chiếu với transcript trước khi xuất bản.</p></div><div className="management-actions"><button className="btn-secondary" onClick={save} disabled={saving}>{saving ? "Đang lưu…" : "Lưu nháp"}</button><button className="btn-primary" onClick={() => setApproveOpen(true)} disabled={approved || saving}>{approved ? "Đã duyệt" : "☑ Duyệt & publish"}</button></div></div>
    {error && <p role="alert" className="workflow-error">{error}</p>}
    {saved && <p role="status" className="review-saved">Đã lưu bản nháp.</p>}
    {approved && <p role="status" className="status-chip success">Lesson đã được phê duyệt.</p>}
    <div className="review-layout">
      <aside className="review-panel transcript-panel"><div className="review-panel-heading"><h2>Transcript nguồn</h2><span className="status-chip warning">Bản nháp AI</span></div>{transcript.map((line, index) => <div className="review-row" key={index}><strong>{line.start ?? index * 5}s</strong><p>{line.text}</p></div>)}</aside>
      <section className="review-panel review-content">
        <div className="management-tabs">{[["summary", "Tóm tắt"], ["concepts", `Khái niệm · ${concepts.length}`], ["flashcards", `Flashcard · ${cards.length}`], ["quiz", `Quiz · ${questions.length}`]].map(([value, label]) => <button className={tab === value ? "active" : ""} key={value} onClick={() => changeTab(value)}>{label}</button>)}</div>
        {tab === "summary" && <><h2>Tóm tắt bài học</h2><textarea className="review-summary-editor" value={draft.summary} onChange={e => editDraft({ ...draft, summary: e.target.value })} /><p className="review-note">ⓘ Chỉnh sửa trực tiếp trong khung. Học viên chỉ thấy sau khi bạn duyệt.</p></>}
        {tab === "concepts" && <><h2>Khái niệm</h2>{concepts.map((item, index) => <div className="concept-card" key={index}><input value={item.term} onChange={e => updateConcept(index, "term", e.target.value)} /><textarea value={item.definition} onChange={e => updateConcept(index, "definition", e.target.value)} /><button type="button" onClick={() => editDraft({ ...draft, key_concepts: concepts.filter((_, itemIndex) => itemIndex !== index) })}>Xóa</button></div>)}<button className="btn-secondary" onClick={() => editDraft({ ...draft, key_concepts: [...concepts, { term: "Khái niệm mới", definition: "Mô tả khái niệm" }] })}>＋ Thêm khái niệm</button></>}
        {tab === "flashcards" && <><div className="spec-card-heading"><h2>Flashcards · {cards.length}</h2><button className="btn-secondary" onClick={() => editDraft({ ...draft, flashcards: [...cards, { front: "Mặt trước mới", back: "Mặt sau mới", position: cards.length + 1 }] })}>＋ Thêm flashcard</button></div>{cards.map((card, index) => <div className="review-edit-card" key={index}><label>Mặt trước<input value={card.front} onChange={e => updateCard(index, "front", e.target.value)} /></label><label>Mặt sau<textarea value={card.back} onChange={e => updateCard(index, "back", e.target.value)} /></label><button className="management-link review-delete" onClick={() => editDraft({ ...draft, flashcards: cards.filter((_, itemIndex) => itemIndex !== index) })}>Xóa</button></div>)}{!cards.length && <p>Chưa có flashcard trong bản nháp.</p>}</>}
        {tab === "quiz" && (
          <>
            <div className="spec-card-heading">
              <h2>Quiz · {questions.length} câu</h2>
              <button
                className="btn-secondary"
                onClick={() => editDraft({
                  ...draft,
                  questions: [...questions, {
                    question: "Câu hỏi mới",
                    options: ["Đáp án A", "Đáp án B"],
                    correct_answer: "Đáp án A",
                    explanation: "Giải thích đáp án.",
                  }],
                })}
              >＋ Thêm câu hỏi</button>
            </div>
            {questions.map((question, index) => (
              <div className="review-edit-card" key={index}>
                <label>
                  Câu hỏi
                  <input
                    value={question.question}
                    onChange={e => updateQuestion(index, "question", e.target.value)}
                  />
                </label>
                <fieldset className="review-question-options">
                  <legend>Các lựa chọn</legend>
                  {question.options.map((option, optionIndex) => (
                    <div className="review-question-option" key={optionIndex}>
                      <input
                        aria-label={`Câu hỏi ${index + 1}, lựa chọn ${optionIndex + 1}`}
                        value={option}
                        onChange={e => editDraft({
                          ...draft,
                          questions: questions.map((item, itemIndex) => itemIndex === index
                            ? updateReviewQuestionOption(item, optionIndex, e.target.value)
                            : item),
                        })}
                      />
                      <button
                        type="button"
                        className="management-link review-delete"
                        aria-label={`Xóa lựa chọn ${optionIndex + 1} câu hỏi ${index + 1}`}
                        onClick={() => editDraft({
                          ...draft,
                          questions: questions.map((item, itemIndex) => itemIndex === index
                            ? removeReviewQuestionOption(item, optionIndex)
                            : item),
                        })}
                      >Xóa lựa chọn</button>
                    </div>
                  ))}
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => editDraft({
                      ...draft,
                      questions: questions.map((item, itemIndex) => itemIndex === index
                        ? { ...item, options: [...item.options, `Lựa chọn ${item.options.length + 1}`] }
                        : item),
                    })}
                  >＋ Thêm lựa chọn</button>
                </fieldset>
                <label>
                  Đáp án đúng
                  <select
                    value={question.options.find(option => String(option).trim() === String(question.correct_answer ?? "").trim()) ?? ""}
                    onChange={e => updateQuestion(index, "correct_answer", e.target.value)}
                  >
                    <option value="">Chọn đáp án đúng</option>
                    {question.options.map((option, optionIndex) => (
                      <option key={optionIndex} value={option}>
                        {option || `Lựa chọn ${optionIndex + 1} (trống)`}
                      </option>
                    ))}
                  </select>
                </label>
                {quizValidationErrors
                  .filter(message => message.startsWith(`Câu hỏi ${index + 1}:`))
                  .map(message => (
                    <p role="alert" className="workflow-error" key={message}>{message}</p>
                  ))}
                <label>
                  Giải thích
                  <textarea
                    value={question.explanation}
                    onChange={e => updateQuestion(index, "explanation", e.target.value)}
                  />
                </label>
                <button
                  className="management-link review-delete"
                  onClick={() => editDraft({
                    ...draft,
                    questions: questions.filter((_, itemIndex) => itemIndex !== index),
                  })}
                >Xóa câu hỏi</button>
              </div>
            ))}
          </>
        )}
      </section>
    </div>
    {approveOpen && <div className="workflow-modal-backdrop" role="presentation"><section className="workflow-modal" role="dialog" aria-modal="true" aria-labelledby="approve-lesson-title"><h2 id="approve-lesson-title">Duyệt và publish lesson?</h2><p>Học viên sẽ thấy các nội dung sau khi bạn xác nhận.</p><div className="approval-checklist">{[["Tóm tắt", Boolean(draft.summary.trim())], [`Khái niệm · ${concepts.length}`, concepts.length > 0], [`Flashcard · ${cards.length}`, cards.length > 0], [`Quiz · ${questions.length} câu`, questions.length > 0]].map(([label, ready]) => <div key={label}><span>{label}</span><span className={"status-chip " + (ready ? "success" : "warning")}>{ready ? "● Đã kiểm tra" : "● Cần bổ sung"}</span></div>)}</div><div className="management-actions"><button className="btn-secondary" onClick={() => setApproveOpen(false)}>Hủy</button><button className="btn-primary" disabled={saving || !draft.summary.trim() || !concepts.length || !cards.length || !questions.length} onClick={approve}>☑ Duyệt & publish</button></div></section></div>}
  </div>;
}
