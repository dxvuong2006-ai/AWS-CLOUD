import { useState, useEffect } from "react";
import { fetchCourses, fetchCourseById, fetchCourseOutline } from "../api/courses.api";

export function useCourses() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchCourses()
      .then(setData)
      .catch(setError)
      .finally(() => setLoading(false));
  }, []);

  return { data, loading, error };
}

function useCourseResource(courseId, fetchResource) {
  const [state, setState] = useState({
    courseId,
    data: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    setState({ courseId, data: null, loading: true, error: null });
    fetchResource(courseId)
      .then((data) => {
        if (!cancelled) setState({ courseId, data, loading: false, error: null });
      })
      .catch((error) => {
        if (!cancelled) setState({ courseId, data: null, loading: false, error });
      });
    return () => {
      cancelled = true;
    };
  }, [courseId, fetchResource]);

  return state.courseId === courseId
    ? state
    : { data: null, loading: true, error: null };
}

export function useCourse(courseId) {
  return useCourseResource(courseId, fetchCourseById);
}

export function useCourseOutline(courseId) {
  return useCourseResource(courseId, fetchCourseOutline);
}
