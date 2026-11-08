# Kết quả đồng bộ hợp đồng review

- Ngày: 2026-11-08.
- Nhánh: feature/c-week4-tutor-analytics.
- Đã đối chiếu: review API/service, lesson/course service, tests lesson approval/video processing/review.
- Duyệt lại PUBLISHED là idempotent sau khi kiểm tra ownership; revision nếu có vẫn được kiểm tra.
- /approve và alias review-draft/approvals dùng chung approve_lesson, xác minh nội dung và video S3 trước khi duyệt lần đầu.
- Publish khóa học yêu cầu video đã xử lý; lỗi thiếu video là 409 PROCESSED_VIDEO_REQUIRED.
- Assertion mâu thuẫn được sửa theo ủy quyền của người dùng; fixture alias bổ sung video và mock S3.
- Xác minh: 219 passed, 16 skipped, 26 subtests passed, 0 failed. Test tích hợp PostgreSQL yêu cầu môi trường riêng; không xác nhận AWS hoặc PostgreSQL production.
- File local, database, script khởi động và cache không thuộc commit.
