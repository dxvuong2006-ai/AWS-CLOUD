import { mockStorageKey } from "../api/session";

export function flashcardKey(courseId, sectionId, lessonId, revision, sessionId = "") {
  return mockStorageKey(`learncloud.flashcards.v1:${JSON.stringify([courseId, sectionId, lessonId, revision, sessionId])}`);
}
export function freshFlashcardProgress(cards) {
  return { queue: cards.map(card => card.id), index: 0, ratings: {}, completed: false };
}
export function restoreFlashcardProgress(key, cards) {
  const raw = localStorage.getItem(key);
  if (!raw) return freshFlashcardProgress(cards);
  let saved;
  try { saved = JSON.parse(raw); } catch { throw new Error("Tiến độ flashcard đã lưu bị lỗi. Bạn có thể bắt đầu lại."); }
  const ids = new Set(cards.map(card => card.id));
  if (!saved || !Array.isArray(saved.queue) || !saved.queue.length ||
      saved.queue.some(id => !ids.has(id)) || new Set(saved.queue).size !== saved.queue.length ||
      !Number.isInteger(saved.index) || saved.index < 0 || saved.index >= saved.queue.length ||
      !saved.ratings || Object.entries(saved.ratings).some(([id, rating]) => !ids.has(id) || !["remembered", "review"].includes(rating)) ||
      typeof saved.completed !== "boolean" || (saved.completed && saved.queue.some(id => !saved.ratings[id])))
    return freshFlashcardProgress(cards);
  return saved;
}
export function saveFlashcardProgress(key, progress) {
  localStorage.setItem(key, JSON.stringify(progress));
}
export function rateFlashcard(progress, rating) {
  if (!["remembered", "review"].includes(rating)) throw new Error("Invalid rating");
  const ratings = { ...progress.ratings, [progress.queue[progress.index]]: rating };
  const missing = progress.queue.findIndex((id, index) => index > progress.index && !ratings[id]);
  const remaining = missing >= 0 ? missing : progress.queue.findIndex(id => !ratings[id]);
  return { ...progress, ratings, index: remaining < 0 ? progress.index : remaining, completed: remaining < 0 };
}
export function reviewFlashcards(progress, cards, onlyReview = true) {
  const queue = cards.filter(card => !onlyReview || progress.ratings[card.id] === "review").map(card => card.id);
  const ratings = { ...progress.ratings };
  queue.forEach(id => delete ratings[id]);
  return { queue, ratings, index: 0, completed: false };
}

export function remediationReturn(courseId, sessionId, returnTo) {
  if (!sessionId || !returnTo) return null;
  // Only return within this course; never accept external URLs or backslash URLs.
  try {
    const url = new URL(returnTo, "https://learncloud.invalid");
    if (url.origin !== "https://learncloud.invalid" || returnTo.includes("\\") ||
        !url.pathname.startsWith(`/courses/${encodeURIComponent(courseId)}/`)) return null;
    url.searchParams.set("remediationSessionId", sessionId);
    return url.pathname + url.search + url.hash;
  } catch { return null; }
}
