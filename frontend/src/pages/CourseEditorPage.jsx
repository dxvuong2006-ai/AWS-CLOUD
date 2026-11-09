import "../styles/management.css";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import courses from "../mocks/courses.mock.json";

export default function CourseEditorPage() {
  const { courseId } = useParams();
  const source = courses.find(course => String(course.id) === String(courseId));
  const [title, setTitle] = useState(source?.title ?? "");
  const [description, setDescription] = useState(source?.description ?? "");
  const [saved, setSaved] = useState(false);
  return <div className="page management-page">
    <div className="breadcrumb"><Link to="/instructor/courses">Khóa học</Link> / {source ? "Chỉnh sửa" : "Tạo mới"}</div>
    <div className="page-head"><div><h1>{source ? "Chỉnh sửa khóa học" : "Tạo khóa học"}</h1></div></div>
    {saved && <p role="status" className="status-chip success">Đã lưu bản nháp trong phiên giao diện demo.</p>}
    <form className="management-form management-card" onSubmit={event=>{event.preventDefault();setSaved(true);}}>
      <label>Tên khóa học<input value={title} onChange={e=>setTitle(e.target.value)} required /></label>
      <label>Mô tả<textarea value={description} onChange={e=>setDescription(e.target.value)} required /></label>
      {source && <label>Cấu trúc<section className="management-card">{source.sections.map(section=><div className="review-row" key={section.id}><strong>{section.title}</strong>{section.lessons.map(lesson=><div key={lesson.id}>• {lesson.title}</div>)}</div>)}</section></label>}
      <div className="management-actions"><button className="btn-primary" type="submit">Lưu bản nháp</button><Link className="btn-secondary" to="/instructor/courses">Hủy</Link></div>
    </form>
  </div>;
}
