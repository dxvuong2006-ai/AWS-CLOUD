export function sectionAccess(course, enrollment, sectionId) {
  const sections = course?.sections ?? [];
  const index = sections.findIndex(section => String(section.id) === String(sectionId));
  if (index < 0) return { allowed: false, missing: true };
  const section = sections[index];
  const allowed = course.status === "PUBLISHED" && !!enrollment &&
    (enrollment.unlocked_section_ids ?? []).map(String).includes(String(section.id));
  return { allowed, section, previous: sections[index - 1] ?? null, enrolled: !!enrollment };
}

export function nextLesson(sections, lessonId) {
  const lessons = (sections ?? []).flatMap(section =>
    (section.lessons ?? []).map(lesson => ({ ...lesson, sectionId: section.id })));
  const index = lessons.findIndex(lesson => String(lesson.id) === String(lessonId));
  return index < 0 ? null : lessons[index + 1] ?? null;
}
