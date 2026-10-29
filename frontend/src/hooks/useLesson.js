import { useState, useEffect } from "react";
import { fetchLesson } from "../api/lessons.api";

export function useLesson(lessonId) {
  const [state, setState] = useState({ lessonId, data: null, loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    setState({ lessonId, data: null, loading: true, error: null });
    fetchLesson(lessonId)
      .then((data) => {
        if (!cancelled) setState({ lessonId, data, loading: false, error: null });
      })
      .catch((error) => {
        if (!cancelled) setState({ lessonId, data: null, loading: false, error });
      });
    return () => { cancelled = true; };
  }, [lessonId]);

  return state.lessonId === lessonId
    ? state
    : { data: null, loading: true, error: null };
}
