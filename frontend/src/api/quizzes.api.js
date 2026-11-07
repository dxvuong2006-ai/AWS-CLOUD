import { requireMockEnrollment, mockRecordPass } from "../mocks/enrollment.mock";
import { mockStorageKey } from "./session";
import { request, ApiError } from "./client";
import quizData from "../mocks/quiz.mock.json";
import courses from "../mocks/courses.mock.json";
import { fetchCourseProgress } from "./progress.api";
import { normalizeQuiz, serializeAnswers, normalizeAttempt } from "./normalizers";
import { checkpointScope, completeCheckpointDraft } from "../utils/checkpointDraft";
import { quizExplanations } from "../mocks/quizExplanations";

const fetchedQuizzes = new Map();

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
const ATTEMPT_KEY = "learncloud.mock.attempts";
const HISTORY_KEY = "learncloud.mock.checkpoint-history.v1";
const MOCK_PASS_PERCENT = 80;
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const pendingRequests = new Map();
const pendingKey = (quizId) => mockStorageKey(`learncloud.pending.checkpoint:${quizId}`);
const sectionKey = (courseId, sectionId) => mockStorageKey(`learncloud.checkpoint:${courseId}:${sectionId}`);

const historyKey = (quizId) => mockStorageKey(`${HISTORY_KEY}:${quizId}`);
const readMockHistory = (quizId) => JSON.parse(localStorage.getItem(historyKey(quizId)) || "[]");

export function knownCheckpointQuizId(courseId, sectionId) {
  return USE_MOCK ? quizData[getQuizKey(courseId, sectionId)]?.id ?? null
    : sessionStorage.getItem(sectionKey(courseId, sectionId));
}

export async function fetchQuizAttempts(quizId, offset = 0) {
  const account = mockStorageKey("checkpoint-history");
  if (USE_MOCK) {
    const course = courses.find(c => c.sections.some(s => quizData[getQuizKey(c.id, s.id)]?.id === quizId));
    if (!course) throw new ApiError(404, "Không tìm thấy checkpoint.");
    requireMockEnrollment(course.id);
    const rows = readMockHistory(quizId);
    return rows.slice(offset, offset + 20).map(row => ({ ...row,
      can_retry: rows[0]?.can_retry === true, remediation_required: rows[0]?.remediation_required === true }));
  }
  const data = await request(`/quizzes/${encodeURIComponent(quizId)}/attempts?limit=20&offset=${offset}`);
  if (account !== mockStorageKey("checkpoint-history")) throw new ApiError(401, "Phiên đăng nhập đã thay đổi.");
  return data.map(row => normalizeAttempt(row));
}

export async function fetchAttemptResult(quizId, attemptId) {
  const account = mockStorageKey("checkpoint-result");
  // Existing backend has an owner-scoped paginated history endpoint, not detail.
  for (let offset = 0; ; offset += 20) {
    const rows = await fetchQuizAttempts(quizId, offset);
    if (account !== mockStorageKey("checkpoint-result")) throw new ApiError(401, "Phiên đăng nhập đã thay đổi.");
    const found = rows.find(row => String(row.id) === String(attemptId));
    if (found) return found;
    if (rows.length < 20) throw new ApiError(404, "Không tìm thấy kết quả thuộc tài khoản của bạn.");
  }
}

export async function recoverPendingCheckpoint(courseId, sectionId) {
  const quizId = knownCheckpointQuizId(courseId, sectionId);
  if (!quizId || !readPendingAttempt(quizId)) return null;
  const pending = readPendingAttempt(quizId);
  const result = await submitAttempt(quizId, USE_MOCK ? pending.answers : [], courseId, pending.lesson_id, pending.request_id);
  return { quizId, result };
}

export function readPendingAttempt(quizId) {
  const raw = sessionStorage.getItem(pendingKey(quizId));
  return raw ? JSON.parse(raw) : null;
}

async function submitRealAttempt(quizId, answers, lessonId, requestId) {
  const key = pendingKey(quizId);
  if (pendingRequests.has(key)) return pendingRequests.get(key);
  const existing = readPendingAttempt(quizId);
  if (existing && requestId && existing.request_id !== requestId) throw new ApiError(409, "Cần xác nhận phiên nộp trước trước khi tạo phiên mới.");
  const scope = checkpointScope(quizId);
  // Keep the exact request across network retries AND refreshes. Never create
  // another attempt just because the first successful response was lost.
  const body = existing ?? {
    request_id: requestId ?? crypto.randomUUID(),
    answers: serializeAnswers(answers),
    ...(lessonId == null ? {} : { lesson_id: Number(lessonId) }),
  };
  sessionStorage.setItem(key, JSON.stringify(body));
  const task = (async () => {
    try {
      const data = await request(`/quizzes/${encodeURIComponent(quizId)}/attempts`, {
        method: "POST", body, timeoutMs: 15000,
      });
      const result = normalizeAttempt(data, fetchedQuizzes.get(mockStorageKey(`quiz:${quizId}`)));
      completeCheckpointDraft(quizId, body.request_id, result.id, scope);
      sessionStorage.removeItem(key);
      return result;
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

  const previous = Math.max(store[quizId] ?? 0, readMockHistory(quizId)[0]?.attempt_number ?? 0);
  const next = (
    Number.isInteger(previous) && previous >= 0 ? previous : 0
  ) + 1;

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
  const quizId = quizData[getQuizKey(courseId, sectionId)]?.id;
  if (quizId && readMockHistory(quizId)[0]?.remediation_required) {
    throw new ApiError(403, "Bạn cần hoàn thành ôn tập AI bắt buộc trước khi làm lại.");
  }
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
    fetchedQuizzes.set(mockStorageKey(`quiz:${quiz.id}`), quiz);
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
    attemptCount: readMockHistory(quiz.id)[0]?.attempt_number ?? 0,
    previousScore: readMockHistory(quiz.id)[0]?.score_percent ?? null,
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
  lessonId,
  requestId
) {
  if (!USE_MOCK) {
    return submitRealAttempt(quizId, answers, lessonId, requestId);
  }
  const key = pendingKey(quizId);
  if (pendingRequests.has(key)) return pendingRequests.get(key);
  const scope = checkpointScope(quizId);
  const body = readPendingAttempt(quizId) ?? { request_id: requestId ?? crypto.randomUUID(), answers, lesson_id: lessonId };
  if (requestId && body.request_id !== requestId) throw new ApiError(409, "Cần xác nhận phiên nộp trước.");
  sessionStorage.setItem(key, JSON.stringify(body));
  const task = gradeMockAttempt(quizId, body.answers, courseId, body.lesson_id, body.request_id)
    .then(result => {
      completeCheckpointDraft(quizId, body.request_id, result.id, scope);
      sessionStorage.removeItem(key);
      return result;
    }).catch(error => {
      if ([400, 401, 403, 404, 422].includes(error.status)) sessionStorage.removeItem(key);
      throw error;
    }).finally(() => pendingRequests.delete(key));
  pendingRequests.set(key, task);
  return task;
}

async function gradeMockAttempt(quizId, answers, courseId, lessonId, requestId) {
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
  requireMockEnrollment(course.id);
  const old = readMockHistory(quizId).find(row => row.request_id === requestId);
  const fingerprint = JSON.stringify({ answers, lessonId });
  if (old) {
    if (old.fingerprint !== fingerprint) throw new ApiError(409, "Phiên nộp đã được dùng với câu trả lời khác.");
    if (old.passed) mockRecordPass(course.id, section.id);
    const latest = readMockHistory(quizId)[0];
    return { ...old, can_retry: latest.can_retry, remediation_required: latest.remediation_required };
  }

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

  const concurrent = readMockHistory(quizId).find(row => row.request_id === requestId);
  if (concurrent) {
    if (concurrent.fingerprint !== fingerprint) throw new ApiError(409, "Phiên nộp đã được dùng với câu trả lời khác.");
    if (concurrent.passed) mockRecordPass(course.id, section.id);
    const latest = readMockHistory(quizId)[0];
    return { ...concurrent, can_retry: latest.can_retry, remediation_required: latest.remediation_required };
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

  const result = {
    id: `mock-${requestId}`,
    quiz_id: String(quizId),
    request_id: requestId,
    fingerprint,
    created_at: new Date().toISOString(),
    attempt_number: nextAttemptNumber(quiz.id),
    score_percent: scorePercent,
    correct_count: correct,
    total_questions: total,
    passed: scorePercent >= MOCK_PASS_PERCENT,
    can_retry: scorePercent >= 50,
    remediation_required: scorePercent < 50,
    question_results: quiz.questions.map((question, index) => ({
      question_id: question.id, question_number: index + 1, text: question.text,
      selected_answer: question.options.find(o => o.id === selectedByQuestion.get(question.id))?.text ?? null,
      correct_answer: question.options.find(o => o.id === question.correct_option_id)?.text ?? null,
      is_correct: selectedByQuestion.get(question.id) === question.correct_option_id,
      explanation: quizExplanations[`${quiz.id}:${question.id}`] ?? null,
    })),
    review_concepts: reviewConcepts,
  };
  localStorage.setItem(historyKey(quizId), JSON.stringify([result, ...readMockHistory(quizId)]));
  if (result.passed) mockRecordPass(course.id, section.id);
  return result;
}
