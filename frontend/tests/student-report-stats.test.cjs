const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");

async function loadStats() {
  const file = path.resolve(__dirname, "../src/utils/studentReportStats.js");
  const source = await fs.readFile(file, "utf8");
  return import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
}

test("video completion does not imply a Checkpoint pass when no attempt exists", async () => {
  const { checkpointResult, summarizeStudentReports } = await loadStats();
  const student = {
    progress: 100, attempt_count: 0, passed_attempts: 0,
    last_score: null, last_passed: null,
  };

  assert.deepEqual(checkpointResult(student), {
    label: "Chưa có lượt làm", tone: "neutral",
  });
  assert.equal(summarizeStudentReports([student]).passRate, null);
  assert.equal(summarizeStudentReports([student]).averageProgress, 100);
  assert.equal(summarizeStudentReports([student]).studentsNeedingReview, 0);
});

test("list summary weights pass rate by attempts and reports the latest result", async () => {
  const { checkpointResult, summarizeStudentReports } = await loadStats();
  const latestFail = {
    progress: 40, attempt_count: 3, passed_attempts: 2,
    last_score: 60, last_passed: false,
  };
  const latestPass = {
    progress: 80, attempt_count: 1, passed_attempts: 1,
    last_score: 90, last_passed: true,
  };
  const summary = summarizeStudentReports([latestFail, latestPass]);

  assert.equal(summary.passRate, 75);
  assert.equal(summary.averageProgress, 60);
  assert.equal(summary.studentsNeedingReview, 1);
  assert.deepEqual(checkpointResult(latestFail), {
    label: "Chưa đạt", tone: "error",
  });
  assert.deepEqual(checkpointResult(latestPass), {
    label: "Đạt", tone: "success",
  });
});

test("unknown or missing latest result is never labeled as passed", async () => {
  const { checkpointResult } = await loadStats();
  assert.equal(checkpointResult({ attempt_count: 2, last_passed: null }).tone, "neutral");
  assert.equal(checkpointResult({ attempt_count: 1 }).label, "Chưa có lượt làm");
});
