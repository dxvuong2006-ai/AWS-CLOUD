import "./CourseCard.css";

export default function CourseCard({
  course,
  onClick,
  showProgress = false,
  progress = 0,
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

  const handleClick = () => {
    if (onClick) {
      onClick(course);
    }
  };

  return (
    <article className="course-card">
      <button
        type="button"
        className="course-card__content"
        onClick={handleClick}
        aria-label={`Xem khóa học ${title}`}
      >
        <div className="course-card__thumbnail">
          {image ? (
            <img src={image} alt={title} loading="lazy" />
          ) : (
            <div className="course-card__placeholder">
              <span>LC</span>
              <p>LearnCloud</p>
            </div>
          )}

          {course?.category && (
            <span className="course-card__category">{course.category}</span>
          )}
        </div>

        <div className="course-card__body">
          <h3 className="course-card__title">{title}</h3>

          <p className="course-card__description">{description}</p>

          <div className="course-card__instructor">
            <span className="course-card__instructor-avatar">
              {String(instructor).charAt(0).toUpperCase()}
            </span>
            <span>
              {typeof instructor === "string" ? instructor : "Giảng viên"}
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
            Xem chi tiết khóa học
          </span>
          <span className="course-card__arrow" aria-hidden="true">
            →
          </span>
        </div>
      </button>
    </article>
  );
}
