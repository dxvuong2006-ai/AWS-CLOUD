import { mockStorageKey } from "../api/session";

export const checkpointScope = (quizId) => mockStorageKey(`learncloud.checkpoint.draft.v1:${quizId}`);
const activeKey = (scope) => `${scope}:active`;
const sessionKey = (scope, id) => `${scope}:session:${id}`;
const submittedKey = (scope, id) => `${scope}:submitted:${id}`;
const signature = (quiz) => JSON.stringify(quiz.questions.map(q => [q.id, q.text, q.options]));

export function restoreCheckpointDraft(quiz, courseId, sectionId) {
  const scope = checkpointScope(quiz.id);
  const id = sessionStorage.getItem(activeKey(scope));
  if (!id || sessionStorage.getItem(submittedKey(scope, id))) return null;
  const raw = sessionStorage.getItem(sessionKey(scope, id));
  if (!raw) return null;
  const draft = JSON.parse(raw);
  if (draft.scope !== scope || draft.sessionId !== id || draft.quizId !== String(quiz.id) ||
      draft.courseId !== String(courseId) || draft.sectionId !== String(sectionId)) return null;
  if (draft.signature !== signature(quiz)) {
    throw new Error("Đề đã thay đổi. Nháp cũ không thể dùng; hãy bắt đầu phiên mới.");
  }
  for (const [questionId, optionId] of Object.entries(draft.answers)) {
    if (!quiz.questions.some(q => q.id === questionId && q.options.some(o => o.id === optionId))) {
      throw new Error("Nháp không còn khớp với đề. Hãy bắt đầu phiên mới.");
    }
  }
  return { ...draft, index: Math.max(0, Math.min(draft.index || 0, quiz.questions.length - 1)) };
}

export function createCheckpointDraft(quiz, courseId, sectionId) {
  const scope = checkpointScope(quiz.id);
  const draft = { scope, sessionId: crypto.randomUUID(), quizId: String(quiz.id),
    courseId: String(courseId), sectionId: String(sectionId), signature: signature(quiz),
    answers: {}, index: 0, createdAt: Date.now() };
  // Write the record first: a quota error must not point to a missing draft.
  sessionStorage.setItem(sessionKey(scope, draft.sessionId), JSON.stringify(draft));
  sessionStorage.setItem(activeKey(scope), draft.sessionId);
  return draft;
}

export function saveCheckpointDraft(draft, answers, index) {
  if (checkpointScope(draft.quizId) !== draft.scope ||
      sessionStorage.getItem(activeKey(draft.scope)) !== draft.sessionId ||
      sessionStorage.getItem(submittedKey(draft.scope, draft.sessionId))) {
    throw new Error("Phiên làm bài đã thay đổi hoặc đã nộp. Vui lòng tải lại trang.");
  }
  const updated = { ...draft, answers: { ...answers }, index, updatedAt: Date.now() };
  sessionStorage.setItem(sessionKey(draft.scope, draft.sessionId), JSON.stringify(updated));
  return updated;
}

export function completeCheckpointDraft(quizId, sessionId, attemptId, scope = checkpointScope(quizId)) {
  // Tombstone first: a late callback must never resurrect a submitted draft.
  sessionStorage.setItem(submittedKey(scope, sessionId), String(attemptId));
  sessionStorage.removeItem(sessionKey(scope, sessionId));
  if (sessionStorage.getItem(activeKey(scope)) === sessionId) sessionStorage.removeItem(activeKey(scope));
}
