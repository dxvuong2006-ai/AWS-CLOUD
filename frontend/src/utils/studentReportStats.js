const count = value => Number.isFinite(Number(value)) ? Number(value) : 0;

export function summarizeStudentReports(students) {
  const rows = Array.isArray(students) ? students : [];
  const totalAttempts = rows.reduce((sum, row) => sum + count(row.attempt_count), 0);
  const passedAttempts = rows.reduce((sum, row) => sum + count(row.passed_attempts), 0);
  const progress = rows.reduce((sum, row) => sum + count(row.progress), 0);

  return {
    averageProgress: rows.length ? Math.round(progress / rows.length) : 0,
    passRate: totalAttempts ? Math.round(100 * passedAttempts / totalAttempts) : null,
    studentsNeedingReview: rows.filter(row =>
      count(row.attempt_count) > 0 && row.last_passed === false
    ).length,
  };
}

export function checkpointResult(student) {
  if (count(student?.attempt_count) === 0 || typeof student?.last_passed !== "boolean") {
    return { label: "Chưa có lượt làm", tone: "neutral" };
  }
  return student.last_passed
    ? { label: "Đạt", tone: "success" }
    : { label: "Chưa đạt", tone: "error" };
}
