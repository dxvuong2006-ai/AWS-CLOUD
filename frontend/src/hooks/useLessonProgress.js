import { useState, useEffect, useCallback, useRef } from "react";
import {
  fetchCourseProgress,
  saveLessonProgress,
} from "../api/progress.api";

export function useLessonProgress(courseId, lessonId) {
  const [courseProgress, setCourseProgress] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saveError, setSaveError] = useState(null);

  const generation = useRef(0);
  const saveSequence = useRef(0);

  useEffect(() => {
    const currentGeneration = ++generation.current;
    let cancelled = false;

    setLoading(true);
    setError(null);
    setSaveError(null);
    setCourseProgress(null);

    fetchCourseProgress(courseId)
      .then((data) => {
        if (!cancelled) setCourseProgress(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;

      if (generation.current === currentGeneration) {
        generation.current += 1;
      }
    };
  }, [courseId, lessonId]);

  const save = useCallback(
    async (positionSeconds, durationSeconds, watchedRanges) => {
      const currentGeneration = generation.current;
      const sequence = ++saveSequence.current;

      const isCurrent = () =>
        generation.current === currentGeneration &&
        saveSequence.current === sequence;

      try {
        await saveLessonProgress(lessonId, {
          lastPositionSeconds: positionSeconds,
          durationSeconds,
          watchedRanges,
        });

        const data = await fetchCourseProgress(courseId);

        if (isCurrent()) {
          setCourseProgress(data);
          setSaveError(null);
        }
      } catch (err) {
        if (isCurrent()) setSaveError(err);
      }
    },
    [courseId, lessonId]
  );

  const current = courseProgress?.lessons.find(
    (lesson) => String(lesson.lesson_id) === String(lessonId)
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