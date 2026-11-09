import { MOCK_COMPLETION_PERCENT } from "../config/learning";
import { requireMockEnrollment } from "../mocks/enrollment.mock";
import { mockStorageKey } from "./session";
import { request, ApiError } from "./client";
import courses from "../mocks/courses.mock.json";
import { normalizeProgress } from "./normalizers";
import {
  mergeWatchedRanges,
  getWatchedSeconds,
} from "../utils/watchedRanges";


const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

// Tách khỏi dữ liệu cũ tính theo vị trí video.
const STORE_KEY = "learncloud.mock.progress.v2";

function readStore() {
  const raw = localStorage.getItem(mockStorageKey(STORE_KEY));
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
        completed: percent >= MOCK_COMPLETION_PERCENT,
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
    completion_threshold_percent: MOCK_COMPLETION_PERCENT,
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
  { lastPositionSeconds, durationSeconds, watchedRanges, courseId, sessionId, sequence, requestId }
) {
  if (!USE_MOCK) {
    // Never send duration, a percentage or a client-side completed flag.
    return request(`/lessons/${encodeURIComponent(lessonId)}/progress`, {
      method: "PUT", timeoutMs: 15000, keepalive: true,
      body: { last_position_seconds: lastPositionSeconds, watched_ranges: watchedRanges,
        playback_session_id: sessionId, sequence, request_id: requestId },
    });
  }
  const course = requireMockEnrollment(courseId);
  const section = course.sections.find(s => s.lessons.some(l => String(l.id) === String(lessonId)));
  if (!section) throw new ApiError(404, "Bài học không thuộc khóa học.");
  requireMockEnrollment(courseId, section.id);

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
    updated_at: Date.now(),
    duration_seconds: durationSeconds,
    last_position_seconds: Math.floor(
      Math.max(0, Math.min(lastPositionSeconds, durationSeconds))
    ),
    watched_ranges: mergedRanges,
  };

  store[lessonId] = saved;

  // Nếu lưu thất bại, để lỗi truyền lên giao diện.
  localStorage.setItem(mockStorageKey(STORE_KEY), JSON.stringify(store));

  return saved;
}
export async function startViewingSession(lessonId, courseId) {
  if (USE_MOCK) {
    requireMockEnrollment(courseId);
    return { id: crypto.randomUUID() };
  }
  const data = await request(`/lessons/${encodeURIComponent(lessonId)}/viewing-sessions`, { method: "POST", timeoutMs: 15000 });
  if (!data?.id) throw new ApiError(502, "Không tạo được phiên xem video.");
  return data;
}
