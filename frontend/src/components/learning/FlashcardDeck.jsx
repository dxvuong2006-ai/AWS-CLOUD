import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { flashcardKey, freshFlashcardProgress, restoreFlashcardProgress, saveFlashcardProgress, rateFlashcard, reviewFlashcards } from "../../utils/flashcardProgress";
import { mockStorageKey } from "../../api/session";
import "./flashcard.css";

export default function FlashcardDeck({ deck, courseId, sectionId, lessonId, sessionId, returnTo }) {
  const storageKey = flashcardKey(courseId, sectionId, lessonId, deck.revision, sessionId);
  const owner = useRef(mockStorageKey("flashcards"));
  const [initial] = useState(() => {
    try { return { progress: restoreFlashcardProgress(storageKey, deck.cards), error: "" }; }
    catch (error) { return { progress: freshFlashcardProgress(deck.cards), error: error.message }; }
  });
  const [progress, setProgress] = useState(initial.progress);
  const [failure, setFailure] = useState(initial.error);
  const [flipped, setFlipped] = useState(false);
  const card = deck.cards.find(row => row.id === progress.queue[progress.index]);
  function update(next) {
    if (owner.current !== mockStorageKey("flashcards")) { setFailure("Phiên đăng nhập đã thay đổi. Hãy tải lại trang."); return; }
    setProgress(next); setFlipped(false);
    try { saveFlashcardProgress(storageKey, next); setFailure(""); }
    catch { setFailure("Chưa lưu được tiến độ. Lựa chọn vẫn còn trên trang; hãy thử lưu lại trước khi rời trang."); }
  }
  const reviewCount = deck.cards.filter(row => progress.ratings[row.id] === "review").length;
  return <section className="flashcard-study" aria-label="Ôn tập flashcard">
    {failure && <div role="alert"><p>{failure}</p><button onClick={() => update(progress)}>Thử lưu lại</button><button onClick={() => update(freshFlashcardProgress(deck.cards))}>Bắt đầu lại</button></div>}
    {progress.completed ? <div className="card flashcard-finish"><span className="flashcard-success" aria-hidden="true">✓</span><h2>Hoàn thành {progress.queue.length} / {progress.queue.length} thẻ</h2>
      <div className="flashcard-stats"><div><strong>{deck.cards.filter(row => progress.ratings[row.id] === "remembered").length}</strong>Đã nhớ</div><div><strong>{reviewCount}</strong>Cần ôn lại</div></div>
      <p className="flashcard-eligibility-note">Hoàn thành flashcard không tự mở khóa checkpoint. Nếu lượt checkpoint gần nhất dưới 50%, bạn cần hoàn thành cả ôn tập AI và bài practice trước khi làm lại.</p><div className="flashcard-actions"><button className="btn-secondary" disabled={!reviewCount} onClick={() => update(reviewFlashcards(progress, deck.cards))}>Ôn lại {reviewCount} thẻ cần ôn</button>
        <Link className="btn-primary" to={`/courses/${courseId}/sections/${sectionId}/checkpoint`} state={{ lessonId }}>→ Làm checkpoint</Link></div>
      <button className="btn-secondary" onClick={() => update(reviewFlashcards(progress, deck.cards, false))}>Ôn lại tất cả</button>
      <p><Link to={`/courses/${courseId}`}>Về lộ trình khóa học</Link></p>
    </div> : <>
      <div className="flashcard-counter"><span>Thẻ {progress.index + 1} / {progress.queue.length}</span><span>{Math.round(progress.queue.filter(id => progress.ratings[id]).length / progress.queue.length * 100)}%</span></div>
      <progress max={progress.queue.length} value={progress.queue.filter(id => progress.ratings[id]).length} aria-label="Số thẻ đã ôn" />
      <div className="flashcard-flip" data-flipped={flipped} key={card.id}>
        <div className="flashcard-flip-rotor">
          <div className="flashcard-face flashcard-side-front" aria-hidden={flipped} inert={flipped}>
            <span className="flashcard-badge">Khái niệm</span>
            <h2>{card.front}</h2>
            <small>Hãy thử nhớ câu trả lời trước khi lật thẻ.</small>
          </div>
          <div className="flashcard-face is-flipped flashcard-side-back" aria-hidden={!flipped} inert={!flipped}>
            <span className="flashcard-badge">Đáp án</span>
            <h2>{card.back}</h2>
            {card.sourceSeconds != null && <small>Nguồn <span className="time-chip">{Math.floor(card.sourceSeconds / 60)}:{String(Math.floor(card.sourceSeconds % 60)).padStart(2, "0")}</span></small>}
          </div>
        </div>
        <button type="button" className={"flashcard-flip-toggle " + (flipped ? "flashcard-return" : "btn-primary")} aria-pressed={flipped} onClick={() => setFlipped(value => !value)}>{flipped ? "Xem mặt trước" : "↻ Lật thẻ"}</button>
        <span className="flashcard-announcement" aria-live="polite" aria-atomic="true">{flipped ? "Đáp án: " + card.back : "Khái niệm: " + card.front}</span>
      </div>
      {!flipped && <div className="flashcard-actions"><button className="btn-secondary" disabled={progress.index === 0} onClick={() => update({ ...progress, index: progress.index - 1 })}>← Thẻ trước</button>
        <button className="btn-secondary" disabled={progress.index === progress.queue.length - 1} onClick={() => update({ ...progress, index: progress.index + 1 })}>Thẻ tiếp →</button></div>}
      {flipped && <div className="flashcard-actions"><button className="btn-secondary" onClick={() => update(rateFlashcard(progress, "review"))}>Cần ôn lại</button><button className="btn-primary" onClick={() => update(rateFlashcard(progress, "remembered"))}>Đã nhớ</button></div>}
    </>}
    {returnTo && <p><Link to={returnTo}>← Quay lại phiên ôn tập AI</Link></p>}
  </section>;
}
