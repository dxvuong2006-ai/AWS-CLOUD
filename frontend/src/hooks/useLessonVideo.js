import { useCallback, useEffect, useRef, useState } from "react";
import { fetchLessonVideoUrl, USE_MOCK } from "../api/lessons.api";

export function useLessonVideo(lessonId, { enabled = true } = {}) {
  const sessionRef = useRef(null);
  const [state, setState] = useState({ lessonId, data: null, loading: false, error: null });

  useEffect(() => {
    const session = { active: true, pending: null, expiresAt: 0 };
    sessionRef.current = session;
    setState({ lessonId, data: null, loading: enabled && !USE_MOCK, error: null });
    session.fetch = () => {
      if (session.pending) return session.pending;
      const requestedAt = Date.now();
      setState((previous) => ({ ...previous, loading: true, error: null }));
      session.pending = fetchLessonVideoUrl(lessonId)
        .then((data) => {
          if (!session.active) return null;
          session.expiresAt = requestedAt + data.expires_in * 1000;
          setState({ lessonId, data, loading: false, error: null });
          return data;
        })
        .catch((error) => {
          if (session.active) setState((previous) => ({ ...previous, loading: false, error }));
          return null;
        })
        .finally(() => { session.pending = null; });
      return session.pending;
    };
    if (enabled && !USE_MOCK) session.fetch();
    return () => { session.active = false; };
  }, [lessonId, enabled]);

  const refresh = useCallback((force = false) => {
    const session = sessionRef.current;
    if (USE_MOCK || !enabled || !session?.active) return Promise.resolve(null);
    if (!force && Date.now() < session.expiresAt - 30000) return Promise.resolve(null);
    return session.fetch();
  }, [enabled]);

  return {
    ...(state.lessonId === lessonId
      ? { ...state, loading: state.loading || (enabled && !USE_MOCK && !state.data && !state.error) }
      : { data: null, loading: true, error: null }),
    refresh,
  };
}
