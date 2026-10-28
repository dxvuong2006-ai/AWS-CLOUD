import { useState, useEffect, useCallback, useRef } from "react";
import { fetchCourseProgress, saveLessonProgress } from "../api/progress.api";

export function useLessonProgress(courseId, lessonId, { enabled = true } = {}) {
  const [courseProgress, setCourseProgress] = useState(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState(null);
  const [saveError, setSaveError] = useState(null);
  const bestPercent = useRef(0);

  const reload = useCallback(
    () => enabled
      ? fetchCourseProgress(courseId).then(setCourseProgress)
      : Promise.resolve(null),
    [courseId, enabled]
  );

  useEffect(() => {
    if (!enabled) {
      setCourseProgress(null);
      setLoading(false);
      setError(null);
      setSaveError(null);
      return;
    }
    setLoading(true);
    setError(null);
    reload()
      .catch(setError)
      .finally(() => setLoading(false));
  }, [reload, enabled]);

  const current = courseProgress?.lessons?.find((l) => l.lesson_id === lessonId);

  // Nhớ phần trăm cao nhất đã xem để không bị giảm khi tua lùi
  useEffect(() => {
    bestPercent.current = current?.progress_percent ?? 0;
  }, [current?.progress_percent, lessonId]);

  const save = useCallback(
    async (positionSeconds, durationSeconds) => {
      if (!enabled || !durationSeconds) return;
      const percent = Math.min(100, Math.round((positionSeconds / durationSeconds) * 100));
      bestPercent.current = Math.max(bestPercent.current, percent);
      try {
        await saveLessonProgress(lessonId, {
          progressPercent: bestPercent.current,
          lastPositionSeconds: Math.floor(positionSeconds),
        });
        setSaveError(null);
        await reload();
      } catch (err) {
        setSaveError(err);
      }
    },
    [lessonId, reload, enabled]
  );

  return {
    courseProgress,
    lastPosition: current?.last_position_seconds ?? 0,
    loading,
    error,
    saveError,
    save,
  };
}
