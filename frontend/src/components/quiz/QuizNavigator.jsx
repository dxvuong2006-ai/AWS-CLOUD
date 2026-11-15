import ProgressBar from "../progress/ProgressBar";
import { PASS_THRESHOLD } from "../../utils/scoreBand";

export default function QuizNavigator({ questions, answers, currentIndex, onGo }) {
  const answered = questions.filter((q) => answers[q.id]).length;

  return (
    <div className="card quiz-progress-panel">
      <h3 className="card-title">Tiến độ làm bài</h3>
      <div className="quiz-nav">
        {questions.map((q, i) => (
          <button
            key={q.id}
            className={`quiz-nav-btn${answers[q.id] ? " answered" : ""}${
              i === currentIndex ? " current" : ""
            }`}
            onClick={() => onGo(i)}
          >
            {i + 1}
          </button>
        ))}
      </div>

      <ProgressBar
        label="Đã trả lời"
        valueText={`${answered} / ${questions.length}`}
        value={(answered / questions.length) * 100}
      />

      <div className="quiz-threshold">
        <span>Điểm đạt</span>
        <strong>{PASS_THRESHOLD}%</strong>
      </div>
      <p className="quiz-note">Kết quả được lưu sau khi bạn nộp bài.</p>
    </div>
  );
}