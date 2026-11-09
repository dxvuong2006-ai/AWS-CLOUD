export function filterCourses(courses, query, enrollmentFilter, enrolledIds) {
  const search = query.trim().toLocaleLowerCase("vi");
  return courses.filter(course => {
    const matchesSearch = String(course.title ?? "").toLocaleLowerCase("vi").includes(search);
    const enrolled = enrolledIds.has(String(course.id));
    return matchesSearch && (enrollmentFilter === "all" ||
      (enrollmentFilter === "enrolled" ? enrolled : !enrolled));
  });
}