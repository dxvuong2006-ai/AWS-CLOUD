// Wire IDs are integers; route/UI IDs are strings.
export function normalizeQuiz(data) {
  return {
    id: String(data.id),
    title: data.title,
    passingScore: Number(data.passing_score ?? 80),
    attemptCount: data.attempt_count ?? 0,
    previousScore: data.previous_score == null ? null : Number(data.previous_score),
    questions: data.questions.map((q) => {
      const options = q.options ?? q.options_json ?? [];
      return {
        id: String(q.id),
        text: q.question,
        concept: q.topic,
        // The backend identifies options by their text, not an option table ID.
        options: options.map((text) => ({ id: text, text })),
      };
    }),
  };
}

export function serializeAnswers(answers) {
  return answers.map((answer) => {
    const id = String(answer.question_id);
    if (!/^[1-9][0-9]*$/.test(id) || !Number.isSafeInteger(Number(id))) {
      throw new Error("Invalid backend question ID");
    }
    return {
      question_id: Number(id),
      selected_answer: answer.selected_option_id,
    };
  });
}

export function normalizeAttempt(data, quiz) {
  const results = data.answers ?? [];
  return {
    id: String(data.id),
    attempt_number: data.attempt_number,
    quiz_id: data.quiz_id == null ? quiz?.id : String(data.quiz_id),
    created_at: data.created_at ?? null,
    score_percent: Number(data.score),
    passed: data.passed,
    can_retry: data.can_retry === true,
    remediation_required: data.remediation_required === true,
    correct_count: results.filter((a) => a.is_correct).length,
    total_questions: results.length,
    question_results: results.map((answer, index) => {
      const question = quiz?.questions.find(q => q.id === String(answer.question_id));
      return {
        question_id: String(answer.question_id),
        question_number: answer.position ?? index + 1,
        text: answer.question_text ?? question?.text ?? `Câu hỏi #${answer.question_id}`,
        selected_answer: answer.selected_answer ?? null,
        correct_answer: answer.correct_answer ?? null,
        explanation: answer.explanation ?? null,
        is_correct: answer.is_correct === true,
      };
    }),
    review_concepts: results.flatMap((answer, index) => {
      if (answer.is_correct) return [];
      const question = quiz?.questions.find((q) => q.id === String(answer.question_id));
      const questionIndex = quiz?.questions.findIndex((q) => q.id === String(answer.question_id));
      return [{
        concept: question?.concept || question?.text || "Câu hỏi cần ôn tập",
        question_number: questionIndex >= 0 ? questionIndex + 1 : index + 1,
      }];
    }),
  };
}

export function normalizeProgress(data) {
  return {
    ...data,
    course_id: String(data.course_id),
    lessons: (data.lessons ?? []).map((lesson) => ({
      ...lesson,
      lesson_id: String(lesson.lesson_id),
    })),
  };
}
