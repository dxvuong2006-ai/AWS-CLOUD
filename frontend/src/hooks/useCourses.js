import { useState, useEffect } from "react";
import { fetchCourses, fetchCourseById } from "../api/courses.api";

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

export function useCourse(courseId) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchCourseById(courseId)
      .then(setData)
      .catch(setError)
      .finally(() => setLoading(false));
  }, [courseId]);

  return { data, loading, error };
}