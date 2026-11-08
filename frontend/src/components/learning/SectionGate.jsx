import "../../styles/student.css";
import { Link, useSearchParams } from "react-router-dom";
import { useCourse } from "../../hooks/useCourses";
import { useEnrollments } from "../../hooks/useEnrollments";
import { sectionAccess } from "../../utils/sectionAccess";

export default function SectionGate({ courseId, sectionId, lessonId, children }) {
  const course = useCourse(courseId);
  const enrollments = useEnrollments();
  const [searchParams] = useSearchParams();
  const returnTo = searchParams.get("from") === "progress" ? "/progress" : `/courses/${courseId}`;
  const returnLabel = returnTo === "/progress" ? "Tiến độ" : "lộ trình";
  if (course.loading || enrollments.loading) return <div className="page student-page student-section-gate" role="status">Đang kiểm tra quyền học...</div>;
  const back = <Link to={returnTo}>← Quay lại {returnLabel}</Link>;
  if (course.error || enrollments.error) return <div className="page student-page student-section-gate"><h1>Chưa xác nhận được quyền học</h1><p role="alert">Không tải được lộ trình. Vui lòng thử lại.</p><button onClick={() => window.location.reload()}>Thử lại</button><p>{back}</p></div>;
  const id = sectionId ?? course.data.sections.find(section => section.lessons.some(lesson => String(lesson.id) === String(lessonId)))?.id;
  const enrollment = enrollments.data.find(row => String(row.course.id) === String(courseId));
  const access = sectionAccess(course.data, enrollment, id);
  if (access.missing) return <div className="page student-page student-section-gate"><h1>Không tìm thấy nội dung</h1>{back}</div>;
  if (!access.allowed) return <div className="page student-page student-section-gate"><div className="breadcrumb">{back} / {course.data.title}</div><h1>{access.section.title}</h1><p>{course.data.title}</p><div className="card section-locked-card">
    <span className="student-status-icon warning" aria-hidden="true"><svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8 10V6a4 4 0 0 1 8 0v4" /></svg></span><h2>Section này đang khóa</h2>
    <p>{!access.enrolled ? "Bạn cần đăng ký khóa học trước khi bắt đầu." : access.previous ? `Đạt ít nhất 80% checkpoint của ${access.previous.title} để tiếp tục lộ trình. Quyền truy cập được xác nhận bởi hệ thống.` : "Section chưa được hệ thống cho phép truy cập."}</p>
    <div className="section-gate-actions">
      <Link className="btn-secondary" to={returnTo}>Quay lại {returnLabel}</Link>
      {access.enrolled && access.previous && <Link className="btn-primary" to={"/courses/" + courseId + "/sections/" + access.previous.id + "/checkpoint"}>→ Làm checkpoint · {access.previous.title}</Link>}
    </div>
    <button className="btn-secondary section-gate-refresh" onClick={enrollments.reload}>Kiểm tra lại quyền truy cập</button>
  </div></div>;
  return children ?? <div className="page student-page student-section-gate"><h1>Section đã mở</h1><p>{access.section.title}</p>{access.section.lessons[0] && <p><Link className="btn-primary" to={`/courses/${courseId}/lessons/${access.section.lessons[0].id}`}>Bắt đầu học</Link></p>}{back}</div>;
}
