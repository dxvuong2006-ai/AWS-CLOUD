const test = require("node:test");
const assert = require("node:assert/strict");
const { readFile } = require("node:fs/promises");
const path = require("node:path");

async function loadSaveHelper() {
  const file = path.resolve(__dirname, "../src/utils/saveReviewDraft.js");
  const source = await readFile(file, "utf8");
  return import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
}

async function loadQuizValidation() {
  const file = path.resolve(__dirname, "../src/utils/reviewQuizValidation.js");
  const source = await readFile(file, "utf8");
  return import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
}

test("failed draft save returns an error and no successful draft", async () => {
  const { saveReviewDraft } = await loadSaveHelper();
  const result = await saveReviewDraft(async () => {
    const error = new Error("Draft API unavailable");
    error.detail = "Draft API unavailable";
    throw error;
  }, 42, { flashcards: [], questions: [] });

  assert.equal(result.draft, null);
  assert.equal(result.error, "Draft API unavailable");
});

test("successful draft save returns the server's persisted response", async () => {
  const { saveReviewDraft } = await loadSaveHelper();
  const persisted = { revision: "abc", flashcards: [], questions: [] };
  const result = await saveReviewDraft(async () => persisted, 42, {});

  assert.equal(result.draft, persisted);
  assert.equal(result.error, "");
});

test("full draft payload includes both editable collections and revision", async () => {
  const { buildReviewDraftPayload } = await loadSaveHelper();
  const draft = {
    title: "Title", summary: "Summary", key_concepts: [{ term: "T", definition: "D" }],
    flashcards: [{ front: "F", back: "B", position: 1 }], quiz_title: "Quiz",
    questions: [{ question: "Q?", options: ["A", "B"], correct_answer: "A", explanation: "X" }],
    revision: "version-1",
  };

  assert.deepEqual(buildReviewDraftPayload(draft), {
    title: draft.title,
    summary: draft.summary,
    key_concepts: draft.key_concepts,
    flashcards: draft.flashcards,
    quiz_title: draft.quiz_title,
    questions: draft.questions,
    expected_revision: draft.revision,
  });
});

test("quiz validation accepts a correct answer that is one of the options", async () => {
  const { validateReviewQuestions } = await loadQuizValidation();
  assert.deepEqual(validateReviewQuestions([{
    question: "Question?", options: ["A", "B"], correct_answer: "B",
  }]), []);
});

test("quiz validation identifies the exact question with an invalid answer", async () => {
  const { validateReviewQuestions } = await loadQuizValidation();
  const questions = Array.from({ length: 4 }, (_, index) => ({
    question: `Question ${index + 1}?`, options: ["A", "B"], correct_answer: "A",
  }));
  questions[3].correct_answer = "Old option";

  assert.deepEqual(validateReviewQuestions(questions), [
    "Câu hỏi 4: Đáp án đúng không nằm trong các lựa chọn.",
  ]);
});

test("editing or deleting an option cannot leave a stale correct answer", async () => {
  const {
    removeReviewQuestionOption,
    updateReviewQuestionOption,
    validateReviewQuestions,
  } = await loadQuizValidation();
  const question = {
    question: "Question?", options: ["A", "B"], correct_answer: "A",
  };

  const edited = updateReviewQuestionOption(question, 0, "Updated A");
  assert.equal(edited.correct_answer, "Updated A");
  assert.deepEqual(validateReviewQuestions([edited]), []);

  const removed = removeReviewQuestionOption(edited, 0);
  assert.equal(removed.correct_answer, "");
  assert.ok(validateReviewQuestions([removed]).includes(
    "Câu hỏi 1: Đáp án đúng không nằm trong các lựa chọn.",
  ));
});

test("correcting an invalid answer allows a subsequent save with current edits", async () => {
  const { saveReviewDraft } = await loadSaveHelper();
  const { validateReviewQuestions } = await loadQuizValidation();
  const draft = {
    summary: "Instructor summary",
    flashcards: [{ front: "Front", back: "Back", position: 1 }],
    questions: [{
      question: "Question?", options: ["A", "B"], correct_answer: "Old option",
    }],
  };
  assert.equal(validateReviewQuestions(draft.questions).length, 1);
  draft.questions[0].correct_answer = "B";
  assert.deepEqual(validateReviewQuestions(draft.questions), []);

  let submitted;
  const result = await saveReviewDraft(async (_lessonId, payload) => {
    submitted = payload;
    return { ...payload, revision: "saved-revision" };
  }, 31, draft);

  assert.equal(result.draft.revision, "saved-revision");
  assert.equal(submitted.summary, "Instructor summary");
  assert.deepEqual(submitted.flashcards, draft.flashcards);
  assert.equal(submitted.questions[0].correct_answer, "B");
});

test("a rejected save does not mutate the instructor's current draft", async () => {
  const { saveReviewDraft } = await loadSaveHelper();
  const draft = {
    summary: "Unsaved summary", flashcards: [{ front: "F", back: "B" }],
    questions: [{ options: ["A", "B"], correct_answer: "Old option" }],
  };
  const snapshot = structuredClone(draft);
  const result = await saveReviewDraft(async () => {
    throw new Error("HTTP 422");
  }, 31, draft);

  assert.equal(result.draft, null);
  assert.deepEqual(draft, snapshot);
});
