export function buildReviewDraftPayload(draft) {
  return {
    title: draft.title,
    summary: draft.summary,
    key_concepts: draft.key_concepts,
    flashcards: draft.flashcards,
    quiz_title: draft.quiz_title,
    questions: draft.questions,
    expected_revision: draft.revision,
  };
}

export async function saveReviewDraft(updateReviewDraft, lessonId, payload) {
  try {
    return { draft: await updateReviewDraft(lessonId, payload), error: "" };
  } catch (error) {
    return {
      draft: null,
      error: error?.detail || error?.message || "Could not save the review draft.",
    };
  }
}
