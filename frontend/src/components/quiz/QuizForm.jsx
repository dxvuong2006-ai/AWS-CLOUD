const LETTERS = ["A", "B", "C", "D", "E", "F"];

export default function QuizForm({
  question,
  index,
  total,
  selectedId,
  unanswered,
  onSelect,
  onPrev,
  onNext,
  onSubmit,
  disabled = false,
}) {
  const isLast = index === total - 1;

  return (
    <div className="card quiz-card">
      <div className="quiz-step">
        Câu {index + 1} / {total}
      </div>
      <h2 className="quiz-question">{question.text}</h2>

      <div className="quiz-options" role="radiogroup">
        {question.options.map((o, i) => (
          <button
            key={o.id}
            disabled={disabled}
            role="radio"
            aria-checked={selectedId === o.id}
            className={`quiz-option${selectedId === o.id ? " selected" : ""}`}
            onClick={() => onSelect(question.id, o.id)}
          >
            <span className="quiz-letter">{LETTERS[i]}</span>
            {o.text}
          </button>
        ))}
      </div>

      <div className="quiz-actions">
        <button className="btn-secondary" onClick={onPrev} disabled={index === 0}>
          ← Câu trước
        </button>
        {isLast ? (
          <button className="btn-primary" onClick={onSubmit}>
            Nộp bài
          </button>
        ) : (
          <button className="btn-primary" onClick={onNext}>
            Câu tiếp →
          </button>
        )}
      </div>
      {isLast && unanswered > 0 && (
        <p className="quiz-hint">
          Còn {unanswered} câu chưa trả lời. Bạn vẫn có thể nộp, câu trống tính là sai.
        </p>
      )}
    </div>
  );
}
