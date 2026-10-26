import { useState, useEffect } from "react";
import { fetchCourseProgress } from "../api/progress.api";

// Tiến độ của MỘT khóa (dùng cho trang chi tiết)
export function useCourseProgress(courseId) {
  const [data, setData] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetchCourseProgress(courseId)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch(() => {
        if (!cancelled) setData(null); // lỗi thì không hiện dấu tích, không đoán
      });
    return () => {
      cancelled = true;
    };
  }, [courseId]);

  return data;
}