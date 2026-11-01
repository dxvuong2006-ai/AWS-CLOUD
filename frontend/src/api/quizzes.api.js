import { request, ApiError } from "./client";
import quizData from "../mocks/quiz.mock.json";
import courses from "../mocks/courses.mock.json";
import { fetchCourseProgress } from "./progress.api";

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
const ATTEMPT_KEY = "learncloud.mock.attempts";
const MOCK_PASS_PERCENT = 80; // chỉ mock dùng, backend thật mới là nơi quyết định đạt hay không
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function nextAttemptNumber(quizId) {
  let store = {};
  try {
    store = JSON.parse(localStorage.getItem(ATTEMPT_KEY)) ?? {};
  } catch {
    store = {};
  }
  store[quizId] = (store[quizId] ?? 0) + 1;
  try {
    localStorage.setItem(ATTEMPT_KEY, JSON.stringify(store));
  } catch {
    // trình duyệt chặn lưu thì bỏ qua
  }
  return store[quizId];
}

// Mock kiểm tra tiến độ đã lưu, giống quyền do server quyết định.
async function requireMockCheckpointAccess(sectionId, courseId, lessonId) {
  const course = courses.find((c) => c.id === courseId);
  const section = course?.sections.find((s) => s.id === sectionId);
  if (!section) throw new ApiError(404);
  const progress = await fetchCourseProgress(course.id);
  const lesson = section.lessons.find((l) => l.id === lessonId);
  const completed = lesson && progress.lessons.some(
    (l) => l.lesson_id === lesson.id && l.completed
  );
  if (!completed) {
    throw new ApiError(403, "Hãy xem ít nhất 95% video của bài học trước khi làm checkpoint.");
  }
}

export async function fetchSectionQuiz(sectionId, courseId, lessonId) {
  if (USE_MOCK) {
    await delay(200);
    const quiz = quizData[sectionId];
    if (!quiz) throw new ApiError(404);
    await requireMockCheckpointAccess(sectionId, courseId, lessonId);
    // Bỏ đáp án đúng và khái niệm trước khi trả ra, giống backend thật
    return {
      id: quiz.id,
      title: quiz.title,
      questions: quiz.questions.map(({ id, text, options }) => ({ id, text, options })),
    };
  }
  return request(`/sections/${sectionId}/quiz`);
}

// answers: [{ question_id, selected_option_id }]
export async function submitAttempt(quizId, answers, courseId, lessonId) {
  if (USE_MOCK) {
    await delay(300);
    const quiz = Object.values(quizData).find((q) => q.id === quizId);
    if (!quiz) throw new ApiError(404);

    const sectionId = Object.keys(quizData).find((id) => quizData[id].id === quizId);
    await requireMockCheckpointAccess(sectionId, courseId, lessonId);

    let correct = 0;
    const reviewConcepts = [];
    quiz.questions.forEach((q, i) => {
      const picked = answers.find((a) => a.question_id === q.id)?.selected_option_id;
      if (picked === q.correct_option_id) {
        correct += 1;
      } else {
        reviewConcepts.push({ concept: q.concept, question_number: i + 1 });
      }
    });

    const total = quiz.questions.length;
    const scorePercent = Math.round((correct / total) * 100);
    return {
      attempt_number: nextAttemptNumber(quizId),
      score_percent: scorePercent,
      correct_count: correct,
      total_questions: total,
      passed: scorePercent >= MOCK_PASS_PERCENT,
      review_concepts: reviewConcepts,
    };
  }
  return request(`/quizzes/${quizId}/attempts`, {
    method: "POST",
    body: { answers },
  });
}