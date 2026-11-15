const normalize = value => String(value ?? "").trim();

export function validateReviewQuestions(questions = []) {
  const errors = [];
  questions.forEach((question, index) => {
    const number = index + 1;
    const options = Array.isArray(question.options) ? question.options : [];
    const normalizedOptions = options.map(normalize);
    const answer = normalize(question.correct_answer);

    if (options.length < 2) {
      errors.push(`Câu hỏi ${number}: Cần ít nhất 2 lựa chọn.`);
    }
    if (new Set(normalizedOptions).size !== normalizedOptions.length) {
      errors.push(`Câu hỏi ${number}: Các lựa chọn phải khác nhau.`);
    }
    if (!normalizedOptions.includes(answer)) {
      errors.push(`Câu hỏi ${number}: Đáp án đúng không nằm trong các lựa chọn.`);
    }
  });
  return errors;
}

export function updateReviewQuestionOption(question, optionIndex, value) {
  const options = [...question.options];
  const previousValue = options[optionIndex];
  options[optionIndex] = value;
  const correctAnswer = normalize(question.correct_answer) === normalize(previousValue)
    ? value
    : question.correct_answer;
  return { ...question, options, correct_answer: correctAnswer };
}

export function removeReviewQuestionOption(question, optionIndex) {
  const removed = question.options[optionIndex];
  const options = question.options.filter((_, index) => index !== optionIndex);
  const removesCorrectAnswer = normalize(question.correct_answer) === normalize(removed);
  return {
    ...question,
    options,
    correct_answer: removesCorrectAnswer ? "" : question.correct_answer,
  };
}
