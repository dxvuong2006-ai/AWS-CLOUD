import { Link } from "react-router-dom";
import { useCourse } from "../../hooks/useCourses";
import { useEnrollments } from "../../hooks/useEnrollments";
import { sectionAccess } from "../../utils/sectionAccess";

export default function SectionGate({ courseId, sectionId, lessonId, children }) {
  const course = useCourse(courseId);
  const enrollments = useEnrollments();
  if (course.loading || enrollments.loading) return <div className="page" role="status">Đang kiểm tra quyền học...</div>;
  const back = <Link to={`/courses/${courseId}`}>← Quay lại lộ trình</Link>;
  if (course.error || enrollments.error) return <div className="page"><h1>Chưa xác nhận được quyền học</h1><p role="alert">Không tải được lộ trình. Vui lòng thử lại.</p><button onClick={() => window.location.reload()}>Thử lại</button><p>{back}</p></div>;
  const id = sectionId ?? course.data.sections.find(section => section.lessons.some(lesson => String(lesson.id) === String(lessonId)))?.id;
  const enrollment = enrollments.data.find(row => String(row.course.id) === String(courseId));
  const access = sectionAccess(course.data, enrollment, id);
  if (access.missing) return <div className="page"><h1>Không tìm thấy nội dung</h1>{back}</div>;
  if (!access.allowed) return <div className="page"><div className="breadcrumb">{back} / {course.data.title}</div><h1>{access.section.title}</h1><p>{course.data.title}</p><div className="card" style={{ maxWidth: 640, margin: "clamp(32px, 12vh, 140px) auto", padding: 40, textAlign: "center" }}>
    <span aria-hidden="true" style={{ fontSize: 32, display: "inline-flex", alignItems: "center", justifyContent: "center", borderRadius: "50%", background: "#fff4df", width: 70, height: 70 }}>🔒</span><h2>Section này đang khóa</h2>
    <p>{!access.enrolled ? "Bạn cần đăng ký khóa học trước khi bắt đầu." : access.previous ? `Đạt ít nhất 80% checkpoint của ${access.previous.title} để tiếp tục lộ trình. Quyền truy cập được xác nhận bởi hệ thống.` : "Section chưa được hệ thống cho phép truy cập."}</p>
    {access.enrolled && access.previous && <p><Link className="btn-primary" to={`/courses/${courseId}/sections/${access.previous.id}/checkpoint`}>Làm checkpoint · {access.previous.title}</Link></p>}
    <p>{back}</p><button className="btn-secondary" onClick={enrollments.reload}>Kiểm tra lại quyền truy cập</button>
  </div></div>;
  return children ?? <div className="page"><h1>Section đã mở</h1><p>{access.section.title}</p>{access.section.lessons[0] && <p><Link className="btn-primary" to={`/courses/${courseId}/lessons/${access.section.lessons[0].id}`}>Bắt đầu học</Link></p>}{back}</div>;
}
