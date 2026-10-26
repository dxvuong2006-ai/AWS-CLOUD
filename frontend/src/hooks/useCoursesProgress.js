import { useState, useEffect } from "react";
import { fetchCourseProgress } from "../api/progress.api";

// Trả về object { [courseId]: phần trăm tiến độ cả khóa }
export function useCoursesProgress(courses) {
  const [percents, setPercents] = useState({});

  useEffect(() => {
    if (!courses || courses.length === 0) return;
    let cancelled = false;

    Promise.allSettled(courses.map((c) => fetchCourseProgress(c.id))).then(
      (results) => {
        if (cancelled) return;
        const next = {};
        results.forEach((r, i) => {
          if (r.status === "fulfilled") {
            next[courses[i].id] = r.value.overall_percent;
          }
        });
        setPercents(next);
      }
    );

    return () => {
      cancelled = true;
    };
  }, [courses]);

  return percents;
}