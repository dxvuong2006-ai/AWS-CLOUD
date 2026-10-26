import { useState, useEffect } from "react";
import { fetchLesson } from "../api/lessons.api";

export function useLesson(lessonId) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchLesson(lessonId)
      .then(setData)
      .catch(setError)
      .finally(() => setLoading(false));
  }, [lessonId]);

  return { data, loading, error };
}