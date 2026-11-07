import CourseArtwork from "./CourseArtwork";
import { Link } from "react-router-dom";
import "./CourseCard.css";

export default function CourseCard({
  course,
  showProgress = false,
  progress = 0,
  enrolled = false,
}) {
  const title = course?.title || course?.name || "Khóa học chưa có tên";
  const instructor =
    course?.instructor_name ||
    course?.instructor?.name ||
    course?.instructor ||
    "LearnCloud";
  const description =
    course?.description || "Khám phá nội dung và bắt đầu hành trình học tập.";
  const image = course?.thumbnail_url || course?.thumbnail || course?.image;
  const courseProgress = Math.min(100, Math.max(0, Number(progress) || 0));

  return (
    <article className={"course-card" + (enrolled ? " course-card--enrolled" : "")}>
      <Link
        to={`/courses/${course?.id}`}
        className="course-card__content"
        aria-label={`Xem khóa học ${title}`}
        style={{ textDecoration: "none" }}
      >
        <div className="course-card__thumbnail">
          {image ? (
            <img src={image} alt={title} loading="lazy" />
          ) : (
            <div className="course-card__placeholder">
              <CourseArtwork title={title} />
              
            </div>
          )}

          {enrolled && <span className="course-card__enrolled">● Đã đăng ký</span>}
          {!enrolled && course?.category && (
            <span className="course-card__category">{course.category}</span>
          )}
        </div>

        <div className="course-card__body">
          <h3 className="course-card__title">{title}</h3>

          <p className="course-card__meta">{course.section_count ?? course.sections?.length ?? "—"} section · {course.lesson_count ?? course.sections?.reduce((count, section) => count + (section.lessons?.length ?? 0), 0) ?? "—"} lesson</p><p className="course-card__description">{description}</p>

          <div className="course-card__instructor">
            <span className="course-card__instructor-avatar">
              {String(typeof instructor === "string" ? instructor : "Giảng viên").trim().split(/\s+/).slice(-2).map(part => part[0]).join("").toUpperCase()}
            </span>
            <span>
              Giảng viên · <strong>{typeof instructor === "string" ? instructor : "Giảng viên"}</strong>
            </span>
          </div>

          {showProgress && (
            <div className="course-card__progress">
              <div className="course-card__progress-info">
                <span>Tiến độ học tập</span>
                <strong>{courseProgress}%</strong>
              </div>

              <div
                className="course-card__progress-track"
                role="progressbar"
                aria-valuenow={courseProgress}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Tiến độ học tập"
              >
                <div
                  className="course-card__progress-fill"
                  style={{ width: `${courseProgress}%` }}
                />
              </div>
            </div>
          )}
        </div>

        <div className="course-card__footer">
          <span className="course-card__footer-label">
            {enrolled ? "Tiếp tục học" : "Xem khóa học"}
          </span>
          <span className="course-card__arrow" aria-hidden="true">
            →
          </span>
        </div>
      </Link>
    </article>
  );
}