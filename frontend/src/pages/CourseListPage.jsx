import { useState } from "react";
import { useCourses } from "../hooks/useCourses";

import CourseCard from "../components/courses/CourseCard";

export default function CourseListPage() {
  const { data, loading, error } = useCourses();

  const [query, setQuery] = useState("");

  if (loading) return <div className="page">Đang tải...</div>;
  if (error) return <div className="page">Không tải được danh sách khóa học.</div>;

  const filtered = data.filter((c) =>
    c.title.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="page">
      <h1>Khóa học</h1>
      <input
        placeholder="Tìm khóa học..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {filtered.length === 0 ? (
        <p>Không có khóa học phù hợp.</p>
      ) : (
        <div className="grid">
          {filtered.map((c) => (
            <CourseCard
              key={c.id}
              course={c}
              showProgress={false}
            />
          ))}
        </div>
      )}
    </div>
  );
}