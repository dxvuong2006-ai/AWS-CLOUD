import "../styles/student.css";
import { useEffect, useRef, useState } from "react";
import { useParams, useLocation, useSearchParams, Link } from "react-router-dom";
import { useCourse } from "../hooks/useCourses";
import { fetchSectionQuiz, submitAttempt, readPendingAttempt, recoverPendingCheckpoint, knownCheckpointQuizId } from "../api/quizzes.api";
import { createCheckpointDraft, restoreCheckpointDraft, saveCheckpointDraft } from "../utils/checkpointDraft";
import CheckpointHistory from "../components/quiz/CheckpointHistory";
import QuizForm from "../components/quiz/QuizForm";
import QuizNavigator from "../components/quiz/QuizNavigator";
import QuizResult from "../components/quiz/QuizResult";
import SubmitConfirmDialog from "../components/quiz/SubmitConfirmDialog";
import "../components/quiz/quiz.css";

function errorMessage(err) {
  if (err?.status === 403) {
    const detail = err.message;
    if (detail === "Mandatory AI review and practice must be completed before retrying." ||
        detail === "Bạn cần hoàn thành ôn tập AI bắt buộc trước khi làm lại.") {
      return "Lượt checkpoint gần nhất dưới 50% nên bạn cần hoàn thành ôn tập AI bắt buộc trước khi làm lại: xem giải thích lỗi, ôn bài hoặc flashcard và đạt bài practice. Chỉ hoàn thành flashcard chưa đủ mở lại checkpoint. Mở kết quả lượt làm gần nhất bên dưới để bắt đầu ôn tập AI.";
    }
    if (detail === "Complete the current lesson before this checkpoint.") {
      return "Bạn cần hoàn thành tiến độ xem bài học trước khi làm checkpoint. Hoàn thành flashcard không thay thế tiến độ xem bài học.";
    }
    if (detail === "Pass the previous section checkpoint first.") {
      return "Bạn cần đạt checkpoint của section trước để mở checkpoint này.";
    }
    return detail && detail !== "HTTP 403" ? detail : "Bạn chưa mở khóa checkpoint này.";
  }
  if (err?.status === 404) return "Section này chưa có checkpoint.";
  return "Không tải được checkpoint.";
}

export default function CheckpointPage() {
  const { courseId, sectionId } = useParams();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const fromProgress = searchParams.get("from") === "progress";
  const progressSuffix = fromProgress ? "?from=progress" : "";
  const fromLessonId = location.state?.lessonId;
  const course = useCourse(courseId);
  const [quiz, setQuiz] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [answers, setAnswers] = useState({});
  const [index, setIndex] = useState(0);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [result, setResult] = useState(null);
  const [started, setStarted] = useState(false);
  const [submissionPending, setSubmissionPending] = useState(false);
  const submissionBusy = useRef(false);
  const generation = useRef(0);
  const draft = useRef(null);
  const [draftError, setDraftError] = useState(null);
  const [restored, setRestored] = useState(false);
  const [loadVersion, setLoadVersion] = useState(0);

  useEffect(() => {
    generation.current += 1;
    submissionBusy.current = false;
    setSubmitting(false);
    draft.current = null;
    setDraftError(null);
    setRestored(false);
    setQuiz(null);
    let cancelled = false;
    setLoading(true);
    setStarted(false);
    setConfirmOpen(false);
    setSubmitError(null);
    setError(null);
    setResult(null);
    setAnswers({});
    setIndex(0);
    setSubmissionPending(false);
    recoverPendingCheckpoint(courseId, sectionId).then(async (recovered) => {
      // A low-score retry is blocked, but replaying the same submission is valid.
      if (recovered?.result.can_retry === false) {
        return { id: recovered.quizId, questions: [], recoveredResult: recovered.result };
      }
      const q = await fetchSectionQuiz(sectionId, courseId, fromLessonId);
      return { ...q, recoveredResult: recovered?.result };
    })
      .then((q) => {
        if (cancelled) return;
        setQuiz(q);
        if (q.recoveredResult) setResult(q.recoveredResult);
        if (!q.recoveredResult) {
          try {
            const saved = restoreCheckpointDraft(q, courseId, sectionId);
            if (saved) {
              draft.current = saved;
              setAnswers(saved.answers);
              setIndex(saved.index);
              setStarted(true);
              setRestored(true);
            }
          } catch (err) { setDraftError(err); }
        }
        const pending = readPendingAttempt(q.id);
        if (pending) {
          setAnswers(Object.fromEntries(pending.answers.map(a => [String(a.question_id), a.selected_answer])));
          setSubmissionPending(true);
          setStarted(true);
        }
      })
      .catch((e) => !cancelled && setError(e))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
      generation.current += 1;
    };
  }, [courseId, sectionId, fromLessonId, loadVersion]);

  const historyQuizId = quiz?.id ?? knownCheckpointQuizId(courseId, sectionId);

  // Quay lại đúng bài học vừa học (LearningPage gửi kèm lessonId), không có thì về khóa học
  const backTo = fromLessonId
    ? `/courses/${courseId}/lessons/${fromLessonId}`
    : `/courses/${courseId}`;
  const backLabel = fromLessonId ? "← Quay lại bài học" : "← Về khóa học";

  if (loading || course.loading) return <div className="page student-page student-CheckpointPage">Đang tải...</div>;
  if (error) {
    return (
      <div className="page student-page student-CheckpointPage">
        <p>{errorMessage(error)}</p>
        <button className="btn-secondary" onClick={() => setLoadVersion(v => v + 1)}>Thử lại</button>
        <Link className="student-route-button" to={backTo}>{backLabel}</Link>
        {historyQuizId && <CheckpointHistory quizId={historyQuizId} />}
      </div>
    );
  }

  const sections = course.data?.sections ?? [];
  const sectionIdx = sections.findIndex((s) => s.id === sectionId);
  const section = sectionIdx >= 0 ? sections[sectionIdx] : null;
  const total = quiz.questions.length;
  const unanswered = quiz.questions.filter((q) => !answers[q.id]).length;

  const handleLeave = (e) => {
    if (draftError && !result && !window.confirm("Chưa lưu được nháp. Rời trang có thể mất các lựa chọn mới. Bạn vẫn muốn rời trang?")) {
      e.preventDefault();
    }
  };

  const handleSelect = (questionId, optionId) => {
    if (submissionPending || !draft.current) return;
    const next = { ...draft.current.answers, [questionId]: optionId };
    setAnswers(next);
    draft.current = { ...draft.current, answers: next };
    persistDraft(next, index);
  };

  const persistDraft = (selected, position) => {
    try {
      draft.current = saveCheckpointDraft(draft.current, selected, position);
      setDraftError(null);
      return true;
    } catch (err) { setDraftError(err); return false; }
  };
  const start = () => {
    try {
      draft.current = createCheckpointDraft(quiz, courseId, sectionId);
      setAnswers({}); setIndex(0); setDraftError(null); setRestored(false); setStarted(true);
    } catch (err) { setDraftError(err); }
  };
  const goTo = (position) => {
    setIndex(position);
    if (draft.current && !submissionPending) persistDraft(draft.current.answers, position);
  };

  const handleSubmit = async () => {
    if (submissionBusy.current) return;
    if (!submissionPending && (!draft.current || !persistDraft(answers, index))) return;
    const currentGeneration = generation.current;
    submissionBusy.current = true;
    setSubmissionPending(true);
    setSubmitting(true);
    setSubmitError(null);
    try {
      // Chỉ gửi câu đã trả lời, backend tính câu thiếu là sai
      const payload = quiz.questions
        .filter((q) => answers[q.id])
        .map((q) => ({ question_id: q.id, selected_option_id: answers[q.id] }));
      const submitted = await submitAttempt(quiz.id, payload, courseId, fromLessonId, draft.current?.sessionId);
      if (generation.current !== currentGeneration) return;
      setResult(submitted);
      draft.current = null;
      setDraftError(null);
      setRestored(false);
      setQuiz(q => ({ ...q, attemptCount: submitted.attempt_number, previousScore: submitted.score_percent }));
      setSubmissionPending(false);
    } catch (err) {
      if (generation.current !== currentGeneration) return;
      setSubmitError(err);
      setSubmissionPending(Boolean(readPendingAttempt(quiz.id)));
    } finally {
      if (generation.current === currentGeneration) {
        submissionBusy.current = false;
        setSubmitting(false);
        setConfirmOpen(false);
      }
    }
  };

  const handleRetry = () => {
    if (result?.can_retry !== true) return;
    setAnswers({});
    setIndex(0);
    setResult(null);
    setSubmitError(null);
    setConfirmOpen(false);
    setStarted(false);
    setLoadVersion(v => v + 1);
  };

  const subtitle = section
    ? `Section ${sectionIdx + 1} · ${section.title}${result ? "" : ` · ${total} câu hỏi`}`
    : "";

  return (
    <div className="page student-page student-CheckpointPage">
      <Link className="back-link" to={backTo} onClick={handleLeave}>
        {backLabel}
      </Link>

      <div className="page-head">
        <div>
          <h1>{result ? "Kết quả checkpoint" : "Checkpoint Section " + (sectionIdx + 1)}</h1>
          <div className="student-subtitle">{subtitle}{result && <> · Lần làm {result.attempt_number}</>}</div>
        </div>

      </div>

      {submitError && (
        <p style={{ color: "var(--error)" }}>
          Không nộp được bài. Câu trả lời của bạn vẫn còn, hãy thử nộp lại.
        </p>
      )}
      {draftError && <p role="alert" className="quiz-warn">Chưa lưu được nháp: {draftError.message} Các lựa chọn mới vẫn ở trang này. {draft.current && <button onClick={() => persistDraft(answers, index)}>Thử lưu lại</button>}</p>}
      {restored && !result && <p role="status">Đã khôi phục đáp án và vị trí câu hỏi của phiên đang làm.</p>}
      {started && !result && !draftError && <p className="checkpoint-save-note">Đáp án được lưu trong tab này ngay khi chọn. Không đóng tab nếu chưa nộp bài.</p>}
      {submissionPending && <p role="status">Đang chờ xác nhận lần nộp trước. Hãy nộp lại để lấy kết quả; câu trả lời được giữ nguyên.</p>}

      {result ? (
        <>
          <QuizResult result={result} />
          <div className="result-existing-actions">
            <button className="btn-secondary" disabled={result.can_retry !== true} onClick={handleRetry} title={result.can_retry !== true ? "Chưa được phép làm lại checkpoint" : undefined}>Làm lại checkpoint</button>
            {result.remediation_required && <span>Nút mở sau khi hoàn thành ôn tập bắt buộc.</span>}
          </div>
          {result.id && <p><Link to={`/checkpoint-results/${encodeURIComponent(quiz.id)}/${encodeURIComponent(result.id)}${progressSuffix}`}>Mở lại kết quả lượt làm này</Link></p>}
          {result.passed && (
            <p style={{ marginTop: 20 }}>
              <Link className="btn-primary" to={`/courses/${courseId}`}>
                Về lộ trình
              </Link>
              <Link className="btn-secondary" to={"/courses/" + courseId + "/completed"}>Xem tổng kết khóa học</Link>
            </p>
          )}
        </>
      ) : !started ? (
        <div className="checkpoint-intro"><div className="card checkpoint-start"><h2>Trước khi bắt đầu</h2>
          <dl className="student-facts"><div><dt>Số câu hỏi</dt><dd>{total}</dd></div><div><dt>Điểm đạt</dt><dd>80%</dd></div><div><dt>Thời gian</dt><dd>Không giới hạn</dd></div><div><dt>Lần làm</dt><dd>Lần {(quiz.attemptCount ?? 0) + 1}</dd></div></dl>
          {quiz.attemptCount > 0 && <p>Đã làm {quiz.attemptCount} lần. Điểm lần gần nhất: {quiz.previousScore}%.</p>}
          <p>
            Bạn có thể chuyển giữa các câu để kiểm tra đáp án trước khi nộp.
            Câu chưa trả lời sẽ được tính là sai.
          </p>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 12,
              marginTop: 20,
            }}
          >
            <button
              type="button"
              className="btn-primary"
              disabled={total === 0}
              onClick={start}
            >
              Bắt đầu làm bài
            </button>
            <Link className="btn-secondary" to={`/courses/${courseId}`}>
              Về lộ trình khóa học
            </Link>
          </div>
        </div><aside className="card checkpoint-rules"><h3>Kết quả sẽ dẫn tới</h3><p><span className="badge badge-success">● ≥ 80%</span><span>Đạt, mở section tiếp theo.</span></p><p><span className="badge badge-warning">● 50–79%</span><span>Ôn lại, có thể hỏi AI Tutor và làm lại ngay.</span></p><p><span className="badge badge-error">● &lt; 50%</span><span>Bắt buộc ôn tập với AI trước khi làm lại.</span></p></aside></div>
      ) : (
        <div className="quiz-layout">
          <QuizForm
            disabled={submissionPending || submitting}
            question={quiz.questions[index]}
            index={index}
            total={total}
            selectedId={answers[quiz.questions[index].id]}
            unanswered={unanswered}
            onSelect={handleSelect}
            onPrev={() => goTo(Math.max(0, index - 1))}
            onNext={() => goTo(Math.min(total - 1, index + 1))}
            onSubmit={() => setConfirmOpen(true)}
          />
          <QuizNavigator
            questions={quiz.questions}
            answers={answers}
            currentIndex={index}
            onGo={goTo}
          />
        </div>
      )}

      {(!started || result) && historyQuizId && <CheckpointHistory quizId={historyQuizId} refreshKey={result?.id} />}

      {confirmOpen && (
        <SubmitConfirmDialog
          total={total}
          unanswered={unanswered}
          submitting={submitting}
          onCancel={() => setConfirmOpen(false)}
          onConfirm={handleSubmit}
        />
      )}
    </div>
  );
}
