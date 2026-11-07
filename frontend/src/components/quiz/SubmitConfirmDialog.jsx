export default function SubmitConfirmDialog({
  total,
  unanswered,
  submitting,
  onCancel,
  onConfirm,
}) {
  return (
    <div className="modal-backdrop" onClick={() => !submitting && onCancel()}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="submit-title"
        onClick={(e) => e.stopPropagation()}
      >
        <span className="submit-warning-icon" aria-hidden="true">⚠</span><h2 id="submit-title">Nộp bài?</h2>
        {unanswered > 0 ? (
          <p>
            Bạn đã trả lời {total - unanswered} / {total} câu. Còn <strong className="quiz-warn">{unanswered} câu</strong> chưa trả lời.
            Câu chưa trả lời sẽ được tính là sai.
          </p>
        ) : (
          <p>Bạn đã trả lời đủ {total} câu. Sau khi nộp, kết quả sẽ được chấm và lưu.</p>
        )}
        <div className="modal-actions">
          <button className="btn-secondary" onClick={onCancel} disabled={submitting}>
            Làm tiếp
          </button>
          <button className="btn-primary" onClick={onConfirm} disabled={submitting}>
            {submitting ? "Đang nộp..." : "Nộp bài"}
          </button>
        </div>
      </div>
    </div>
  );
}