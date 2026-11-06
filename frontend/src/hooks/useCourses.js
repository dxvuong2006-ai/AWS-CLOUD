import { useState, useEffect } from "react";
import { fetchCourses, fetchCourseById } from "../api/courses.api";

export function useCourses() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    fetchCourses()
      .then(value => { if (active) setData(value); })
      .catch(err => { if (active) setError(err); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  return { data, loading, error };
}

export function useCourse(courseId) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    setData(null);
    setLoading(true);
    setError(null);
    fetchCourseById(courseId)
      .then(value => { if (active) setData(value); })
      .catch(err => { if (active) setError(err); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [courseId]);

  return { data, loading, error };
}