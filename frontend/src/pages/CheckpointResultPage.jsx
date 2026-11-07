import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchAttemptResult } from "../api/quizzes.api";
import QuizResult from "../components/quiz/QuizResult";
import "../components/quiz/quiz.css";

export default function CheckpointResultPage() {
  const { quizId, attemptId } = useParams();
  const [result, setResult] = useState(null), [error, setError] = useState(null);
  const [loading, setLoading] = useState(true), [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true; setLoading(true); setResult(null); setError(null);
    fetchAttemptResult(quizId, attemptId).then(data => { if (active) setResult(data); })
      .catch(err => { if (active) setError(err); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [quizId, attemptId, retry]);
  return <div className="page"><Link to="/my-courses">← Khóa học của tôi</Link><h1>Kết quả checkpoint</h1>
    {loading ? <p>Đang tải kết quả...</p> : error ? <div role="alert">
      <p>{[403,404].includes(error.status) ? "Không tìm thấy kết quả thuộc tài khoản của bạn." : "Không tải được kết quả. Vui lòng thử lại."}</p>
      <button onClick={() => setRetry(v => v + 1)}>Thử lại</button>
    </div> : <QuizResult result={result} />}
  </div>;
}
