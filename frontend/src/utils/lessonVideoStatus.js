const labels = {
  NOT_UPLOADED: "Chưa có video",
  UPLOAD_PENDING: "Chờ upload / Xác nhận video",
  UPLOADED: "Đã upload RAW / Chờ xử lý",
  PROCESSING: "Đang xử lý",
  READY: "Video sẵn sàng",
  FAILED: "Xử lý thất bại",
  UNKNOWN: "Chưa xác định trạng thái video",
};

export function lessonVideoPresentation(lesson) {
  // Only the backend read model determines availability. Missing fields/URLs
  // must never turn a draft or in-flight lesson into "no video".
  const state = Object.hasOwn(labels, lesson?.video_status) ? lesson.video_status : "UNKNOWN";
  const workflow = lesson?.status;
  const suffix = state === "READY"
    ? workflow === "REVIEW_REQUIRED" ? " · Chờ duyệt" : workflow === "PUBLISHED" ? " · Đã publish" : ""
    : state === "PROCESSING"
      ? workflow === "TRANSCRIBING" ? " · Tạo transcript" : workflow === "AI_PROCESSING" ? " · Tạo học liệu AI" : ""
      : "";
  return {
    state,
    label: labels[state] + suffix,
    tone: state === "FAILED" ? "error" : state === "READY" ? "success" : "neutral",
    action: workflow === "REVIEW_REQUIRED" ? "review" : workflow === "PUBLISHED" ? null
      : state === "NOT_UPLOADED" ? "upload" : "status",
  };
}

export function shouldWatchVideoStatus(course) {
  // A successful S3 PUT can precede the backend event that leaves DRAFT.
  // Watch empty/unknown snapshots as well, so they cannot stay stale forever.
  return course?.sections?.some(section => section.lessons?.some(lesson =>
    !["READY", "FAILED"].includes(lesson.video_status))) ?? false;
}
