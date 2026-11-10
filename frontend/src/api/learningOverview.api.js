import { request } from "./client";
import courses from "../mocks/courses.mock.json";
import quizData from "../mocks/quiz.mock.json";
import { mockEnrollments } from "../mocks/enrollment.mock";
import { mockStorageKey } from "./session";
import { fetchCourseProgress } from "./progress.api";

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
const HISTORY_KEY = "learncloud.mock.checkpoint-history.v1";

function readMockHistory(quizId) {
  const key = mockStorageKey(`${HISTORY_KEY}:${quizId}`);
  return JSON.parse(localStorage.getItem(key) || "[]");
}

async function mockOverview() {
  const enrolled = mockEnrollments();
  return Promise.all(Object.keys(enrolled).map(async (courseId) => {
    const course = courses.find((item) => String(item.id) === String(courseId));
    if (!course) return null;
    const progress = await fetchCourseProgress(course.id);
    const passedSections = course.sections.filter((section) => {
      const quiz = quizData[`${course.id}:${section.id}`];
      return quiz && readMockHistory(quiz.id).some((attempt) => attempt.passed === true && attempt.score_percent >= 80);
    }).length;
    const scores = course.sections.flatMap((section) => {
      const quiz = quizData[`${course.id}:${section.id}`];
      return quiz ? readMockHistory(quiz.id).filter((attempt) => attempt.passed).map((attempt) => attempt.score_percent) : [];
    });
    return {
      course_id: String(course.id),
      title: course.title,
      section_count: course.sections.length,
      passed_sections: passedSections,
      lesson_count: course.sections.reduce((total, section) => total + section.lessons.length, 0),
      completed_lessons: progress.lessons.filter((lesson) => lesson.completed).length,
      average_score: scores.length ? Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length) : null,
      completed: course.sections.length > 0 && passedSections === course.sections.length &&
        progress.lessons.every((lesson) => lesson.completed),
      progress_percent: progress.overall_percent,
    };
  })).then((rows) => rows.filter(Boolean));
}

function mockHistory(offset, limit) {
  return courses.flatMap((course) => course.sections.flatMap((section) => {
    const quiz = quizData[`${course.id}:${section.id}`];
    if (!quiz) return [];
    return readMockHistory(quiz.id).map((attempt) => ({
      id: attempt.id,
      quiz_id: String(quiz.id),
      course_id: String(course.id),
      course_title: course.title,
      section_id: String(section.id),
      section_title: section.title,
      score: attempt.score_percent,
      passed: attempt.passed,
      attempt_number: attempt.attempt_number,
      created_at: attempt.created_at,
    }));
  })).sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || ""))).slice(offset, offset + limit);
}

export const getCompletion = courseId => request("/courses/" + encodeURIComponent(courseId) + "/completion");
export const getHistory = (offset = 0) => USE_MOCK
  ? Promise.resolve(mockHistory(offset, 20))
  : request("/students/me/checkpoint-history?offset=" + offset + "&limit=20");
export const getOverview = () => USE_MOCK ? mockOverview() : request("/students/me/learning-overview");
