import { request, ApiError } from "./client";
import courses from "../mocks/courses.mock.json";
import { normalizeProgress } from "./normalizers";
import {
  mergeWatchedRanges,
  getWatchedSeconds,
} from "../utils/watchedRanges";

const COMPLETE_AT_PERCENT = 10;
const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

// Tách khỏi dữ liệu cũ tính theo vị trí video.
const STORE_KEY = "learncloud.mock.progress.v2";

function readStore() {
  const raw = localStorage.getItem(STORE_KEY);
  return raw ? JSON.parse(raw) : {};
}

function buildCourseProgress(courseId) {
  const course = courses.find((c) => String(c.id) === String(courseId));

  if (!course) {
    throw new ApiError(404, "Không tìm thấy khóa học.");
  }

  const store = readStore();

  const lessons = (course.sections ?? [])
    .flatMap((section) => section.lessons ?? [])
    .map((lesson) => {
      const saved = store[lesson.id] ?? {};
      const duration = saved.duration_seconds ?? 0;
      const ranges = mergeWatchedRanges(
        saved.watched_ranges ?? [],
        duration
      );

      const watchedSeconds = getWatchedSeconds(ranges);
      const percent = duration > 0
        ? Math.min(100, (watchedSeconds / duration) * 100)
        : 0;

      return {
        lesson_id: String(lesson.id),
        // Làm tròn xuống để 94,9% không hiển thị thành 95%.
        progress_percent: Math.floor(percent),
        completed: percent >= COMPLETE_AT_PERCENT,
        last_position_seconds: saved.last_position_seconds ?? 0,
        watched_seconds: watchedSeconds,
        watched_ranges: ranges,
      };
    });

  const total = lessons.reduce(
    (sum, lesson) => sum + lesson.progress_percent,
    0
  );

  return {
    course_id: String(courseId),
    overall_percent: lessons.length
      ? Math.floor(total / lessons.length)
      : 0,
    lessons,
  };
}

export async function fetchCourseProgress(courseId) {
  if (USE_MOCK) {
    return buildCourseProgress(courseId);
  }

  return normalizeProgress(await request(`/courses/${courseId}/progress`));
}

export async function saveLessonProgress(
  lessonId,
  { lastPositionSeconds, durationSeconds, watchedRanges }
) {
  if (!USE_MOCK) {
    // Chưa có contract/backend nhận khoảng xem.
    // Không âm thầm quay về cách tính bằng vị trí video.
    throw new ApiError(
      501,
      "Backend chưa hỗ trợ lưu các khoảng video đã xem."
    );
  }

  if (
    !Number.isFinite(durationSeconds) ||
    durationSeconds <= 0 ||
    !Number.isFinite(lastPositionSeconds)
  ) {
    throw new ApiError(400, "Thông tin thời lượng video không hợp lệ.");
  }

  const store = readStore();
  const previous = store[lessonId] ?? {};

  const mergedRanges = mergeWatchedRanges(
    [
      ...(previous.watched_ranges ?? []),
      ...(watchedRanges ?? []),
    ],
    durationSeconds
  );

  const saved = {
    duration_seconds: durationSeconds,
    last_position_seconds: Math.floor(
      Math.max(0, Math.min(lastPositionSeconds, durationSeconds))
    ),
    watched_ranges: mergedRanges,
  };

  store[lessonId] = saved;

  // Nếu lưu thất bại, để lỗi truyền lên giao diện.
  localStorage.setItem(STORE_KEY, JSON.stringify(store));

  return saved;
}