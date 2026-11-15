import "../styles/student.css";
import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { fetchAttemptResult } from "../api/quizzes.api";
import QuizResult from "../components/quiz/QuizResult";
import "../components/quiz/quiz.css";

export default function CheckpointResultPage() {
  const { quizId, attemptId } = useParams();
  const [searchParams] = useSearchParams();
  const fromProgress = searchParams.get("from") === "progress";
  const [result, setResult] = useState(null), [error, setError] = useState(null);
  const [loading, setLoading] = useState(true), [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true; setLoading(true); setResult(null); setError(null);
    fetchAttemptResult(quizId, attemptId).then(data => { if (active) setResult(data); })
      .catch(err => { if (active) setError(err); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [quizId, attemptId, retry]);
  return <div className="page student-page student-CheckpointResultPage"><Link className="student-back-button" to={fromProgress ? "/progress" : "/my-courses"}>{fromProgress ? "← Tiến độ" : "← Khóa học của tôi"}</Link><h1>Kết quả checkpoint</h1>
    {loading ? <p>Đang tải kết quả...</p> : error ? <div role="alert">
      <p>{[403,404].includes(error.status) ? "Không tìm thấy kết quả thuộc tài khoản của bạn." : "Không tải được kết quả. Vui lòng thử lại."}</p>
      <button onClick={() => setRetry(v => v + 1)}>Thử lại</button>
    </div> : <QuizResult result={result} />}
  </div>;
}
