import { requireMockEnrollment, mockRecordPass } from "../mocks/enrollment.mock";
import { mockStorageKey } from "./session";
import { request, ApiError } from "./client";
import quizData from "../mocks/quiz.mock.json";
import courses from "../mocks/courses.mock.json";
import { fetchCourseProgress } from "./progress.api";
import { normalizeQuiz, serializeAnswers, normalizeAttempt } from "./normalizers";

const fetchedQuizzes = new Map();

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
const ATTEMPT_KEY = "learncloud.mock.attempts";
const MOCK_PASS_PERCENT = 80;
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const pendingRequests = new Map();
const pendingKey = (quizId) => mockStorageKey(`learncloud.pending.checkpoint:${quizId}`);
const sectionKey = (courseId, sectionId) => mockStorageKey(`learncloud.checkpoint:${courseId}:${sectionId}`);

export async function recoverPendingCheckpoint(courseId, sectionId) {
  if (USE_MOCK) return null;
  const quizId = sessionStorage.getItem(sectionKey(courseId, sectionId));
  if (!quizId || !readPendingAttempt(quizId)) return null;
  const result = await submitRealAttempt(quizId, [], undefined);
  return { quizId, result };
}

export function readPendingAttempt(quizId) {
  if (USE_MOCK) return null;
  const raw = sessionStorage.getItem(pendingKey(quizId));
  return raw ? JSON.parse(raw) : null;
}

async function submitRealAttempt(quizId, answers, lessonId) {
  const key = pendingKey(quizId);
  if (pendingRequests.has(key)) return pendingRequests.get(key);
  const existing = readPendingAttempt(quizId);
  // Keep the exact request across network retries AND refreshes. Never create
  // another attempt just because the first successful response was lost.
  const body = existing ?? {
    request_id: crypto.randomUUID(),
    answers: serializeAnswers(answers),
    ...(lessonId == null ? {} : { lesson_id: Number(lessonId) }),
  };
  sessionStorage.setItem(key, JSON.stringify(body));
  const task = (async () => {
    try {
      const data = await request(`/quizzes/${encodeURIComponent(quizId)}/attempts`, {
        method: "POST", body, timeoutMs: 15000,
      });
      sessionStorage.removeItem(key);
      return normalizeAttempt(data, fetchedQuizzes.get(String(quizId)));
    } catch (error) {
      // A definite validation/access rejection permits editing a new request.
      // Unknown outcomes and conflicts retain the key for safe replay.
      if ([400, 401, 403, 404, 422].includes(error.status)) sessionStorage.removeItem(key);
      throw error;
    } finally {
      pendingRequests.delete(key);
    }
  })();
  pendingRequests.set(key, task);
  return task;
}

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
    const parsed = JSON.parse(localStorage.getItem(mockStorageKey(ATTEMPT_KEY)));

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
  localStorage.setItem(mockStorageKey(ATTEMPT_KEY), JSON.stringify(store));

  return next;
}

// Có lessonId: kiểm tra đúng bài đang xem.
// Không có lessonId: section cần ít nhất một bài đã hoàn thành.
async function requireMockCheckpointAccess(
  sectionId,
  courseId,
  lessonId
) {
  requireMockEnrollment(courseId, sectionId);
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
    const suffix = lessonId == null ? "" : `?lesson_id=${encodeURIComponent(lessonId)}`;
    const quiz = normalizeQuiz(await request(
      `/sections/${encodeURIComponent(sectionId)}/quiz${suffix}`
    ));
    fetchedQuizzes.set(quiz.id, quiz);
    sessionStorage.setItem(sectionKey(courseId, sectionId), quiz.id);
    return quiz;
  }

  const accountKey = mockStorageKey(ATTEMPT_KEY);
  await delay(200);
  if (mockStorageKey(ATTEMPT_KEY) !== accountKey) {
    throw new ApiError(401, "Phiên đăng nhập đã thay đổi.");
  }

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
    return submitRealAttempt(quizId, answers, lessonId);
  }

  const accountKey = mockStorageKey(ATTEMPT_KEY);
  await delay(300);
  if (mockStorageKey(ATTEMPT_KEY) !== accountKey) {
    throw new ApiError(401, "Phiên đăng nhập đã thay đổi.");
  }

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

  if (mockStorageKey(ATTEMPT_KEY) !== accountKey) {
    throw new ApiError(401, "Phiên đăng nhập đã thay đổi.");
  }

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

  if (scorePercent >= MOCK_PASS_PERCENT) mockRecordPass(course.id, section.id);

  return {
    attempt_number: nextAttemptNumber(quiz.id),
    score_percent: scorePercent,
    correct_count: correct,
    total_questions: total,
    passed: scorePercent >= MOCK_PASS_PERCENT,
    review_concepts: reviewConcepts,
  };
}
