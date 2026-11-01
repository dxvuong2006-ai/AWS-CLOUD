import { request, ApiError } from "./client";
import quizData from "../mocks/quiz.mock.json";
import courses from "../mocks/courses.mock.json";
import { fetchCourseProgress } from "./progress.api";

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
const ATTEMPT_KEY = "learncloud.mock.attempts";
const MOCK_PASS_PERCENT = 80;
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function getQuizKey(courseId, sectionId) {
  return `${courseId}:${sectionId}`;
}

function findCourse(courseId) {
  const course = courses.find(
    (item) => String(item.id) === String(courseId)
  );

  if (!course) {
    throw new ApiError(404, "Không tìm thấy khóa học.");
  }

  return course;
}

function nextAttemptNumber(quizId) {
  let store = {};

  try {
    const parsed = JSON.parse(localStorage.getItem(ATTEMPT_KEY));

    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      store = parsed;
    }
  } catch {
    store = {};
  }

  const previous = store[quizId];
  const next = (
    Number.isInteger(previous) && previous >= 0 ? previous : 0
  ) + 1;

  store[quizId] = next;
  localStorage.setItem(ATTEMPT_KEY, JSON.stringify(store));

  return next;
}

// Có lessonId: kiểm tra đúng bài đang xem.
// Không có lessonId: section cần ít nhất một bài đã hoàn thành.
async function requireMockCheckpointAccess(
  sectionId,
  courseId,
  lessonId
) {
  const course = findCourse(courseId);
  const section = (course.sections ?? []).find(
    (item) => String(item.id) === String(sectionId)
  );

  if (!section) {
    throw new ApiError(404, "Không tìm thấy section trong khóa học.");
  }

  const progress = await fetchCourseProgress(course.id);
  const completedIds = new Set(
    (progress.lessons ?? [])
      .filter((lesson) => lesson.completed === true)
      .map((lesson) => String(lesson.lesson_id))
  );

  const sectionLessons = section.lessons ?? [];

  if (lessonId !== undefined && lessonId !== null) {
    const lesson = sectionLessons.find(
      (item) => String(item.id) === String(lessonId)
    );

    if (!lesson) {
      throw new ApiError(403, "Bài học không thuộc section này.");
    }

    if (!completedIds.has(String(lesson.id))) {
      throw new ApiError(
        403,
        "Bạn chưa đạt tiến độ cần thiết của bài học này."
      );
    }

    return;
  }

  const hasCompletedLesson = sectionLessons.some(
    (lesson) => completedIds.has(String(lesson.id))
  );

  if (!hasCompletedLesson) {
    throw new ApiError(
      403,
      "Bạn cần hoàn thành ít nhất một bài học trong section."
    );
  }
}

export async function fetchSectionQuiz(
  sectionId,
  courseId,
  lessonId
) {
  if (!USE_MOCK) {
    return request(
      `/sections/${encodeURIComponent(sectionId)}/quiz`
    );
  }

  await delay(200);

  await requireMockCheckpointAccess(
    sectionId,
    courseId,
    lessonId
  );

  const quiz = quizData[getQuizKey(courseId, sectionId)];

  if (!quiz || !quiz.questions?.length) {
    throw new ApiError(404, "Section này chưa có checkpoint.");
  }

  // Chỉ trả nội dung làm bài, không trả đáp án đúng.
  return {
    id: quiz.id,
    title: quiz.title,
    questions: quiz.questions.map(({ id, text, options }) => ({
      id,
      text,
      options,
    })),
  };
}

export async function submitAttempt(
  quizId,
  answers,
  courseId,
  lessonId
) {
  if (!USE_MOCK) {
    return request(
      `/quizzes/${encodeURIComponent(quizId)}/attempts`,
      {
        method: "POST",
        body: { answers },
      }
    );
  }

  await delay(300);

  const course = findCourse(courseId);

  // Chỉ tìm quiz trong các section thuộc khóa đang học.
  const section = (course.sections ?? []).find((item) => {
    const quiz = quizData[getQuizKey(course.id, item.id)];
    return quiz && String(quiz.id) === String(quizId);
  });

  if (!section) {
    throw new ApiError(
      404,
      "Không tìm thấy checkpoint trong khóa học."
    );
  }

  const quiz = quizData[getQuizKey(course.id, section.id)];

  if (!quiz.questions?.length) {
    throw new ApiError(404, "Checkpoint chưa có câu hỏi.");
  }

  await requireMockCheckpointAccess(
    section.id,
    course.id,
    lessonId
  );

  if (!Array.isArray(answers)) {
    throw new ApiError(400, "Danh sách câu trả lời không hợp lệ.");
  }

  const selectedByQuestion = new Map();

  for (const answer of answers) {
    const question = quiz.questions.find(
      (item) => item.id === answer?.question_id
    );

    const validOption = question?.options.some(
      (option) => option.id === answer?.selected_option_id
    );

    if (
      !question ||
      !validOption ||
      selectedByQuestion.has(question.id)
    ) {
      throw new ApiError(
        400,
        "Câu trả lời không hợp lệ hoặc bị trùng."
      );
    }

    selectedByQuestion.set(
      question.id,
      answer.selected_option_id
    );
  }

  let correct = 0;
  const reviewConcepts = [];

  quiz.questions.forEach((question, index) => {
    const selectedId = selectedByQuestion.get(question.id);

    if (selectedId === question.correct_option_id) {
      correct += 1;
    } else {
      // Không trả lời cũng tính là sai.
      reviewConcepts.push({
        concept: question.concept,
        question_number: index + 1,
      });
    }
  });

  const total = quiz.questions.length;
  const scorePercent = Math.round((correct / total) * 100);

  return {
    attempt_number: nextAttemptNumber(quiz.id),
    score_percent: scorePercent,
    correct_count: correct,
    total_questions: total,
    passed: scorePercent >= MOCK_PASS_PERCENT,
    review_concepts: reviewConcepts,
  };
}