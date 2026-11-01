export const SCORE_BANDS = Object.freeze({
  PASS: "PASS",
  REVIEW: "REVIEW",
  REMEDIATION: "REMEDIATION",
});

export const PASS_THRESHOLD = 80;
export const REVIEW_THRESHOLD = 50;

const BAND_INFO = {
  [SCORE_BANDS.PASS]: {
    label: "Đạt",
    tone: "success",
    color: "var(--color-success)",
    showTutor: false,
    message:
      "Bạn đã hoàn thành bài kiểm tra. Hãy tiếp tục học tập để nâng cao kiến thức của mình.",
  },
  [SCORE_BANDS.REVIEW]: {
    label: "Cần xem lại",
    tone: "warning",
    color: "var(--color-warning)",
    showTutor: true,
    message:
      "Bạn gần đạt rồi. Hãy xem lại nội dung và hỏi AI Tutor về các câu làm sai.",
  },
  [SCORE_BANDS.REMEDIATION]: {
    label: "Cần bổ sung",
    tone: "error",
    color: "var(--color-error)",
    showTutor: true,
    message: "Bạn cần bổ sung kiến thức để đạt được kết quả tốt hơn.",
  },
};

// Normalize a score to a value between 0 and 100
function normalizeScore(score) {
  if (score === null || score === undefined || score === "") return null;
  const n = typeof score === "number" ? score : Number(score);
  if (!Number.isFinite(n)) return null;
  return Math.min(100, Math.max(0, n));
}

// Get the score band
export function getScoreBand(
  score,
  { passingScore = PASS_THRESHOLD, passed } = {},
) {
  const value = normalizeScore(score);
  if (value === null) {
    return {
      band: null,
      score: null,
      label: "Chưa có điểm",
      tone: "muted",
      color: "var(--color-muted)",
      isPassing: false,
      showTutor: false,
      message: "Bạn chưa hoàn thành bài kiểm tra.",
    };
  }
  let band;
  if (typeof passed === "boolean") {
    if (passed) band = SCORE_BANDS.PASS;
    else if (value >= REVIEW_THRESHOLD) band = SCORE_BANDS.REVIEW;
    else band = SCORE_BANDS.REMEDIATION;
  } else {
    if (value >= passingScore) band = SCORE_BANDS.PASS;
    else if (value >= REVIEW_THRESHOLD) band = SCORE_BANDS.REVIEW;
    else band = SCORE_BANDS.REMEDIATION;
  }
  return {
    band,
    score: value,
    isPassing: band === SCORE_BANDS.PASS,
    ...BAND_INFO[band],
  };
}

// Format a score for display,add a percentage sign
export function formatScore(score) {
  const value = normalizeScore(score);
  if (value === null) return "—";
  const rounded = Math.round(value * 10) / 10;
  return `${String(rounded).replace(".", ",")}%`;
}
