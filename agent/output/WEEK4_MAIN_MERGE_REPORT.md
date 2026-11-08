# Báo cáo đồng bộ nhánh Tuần 4

- Ngày: 2026-11-08.
- Mục tiêu: gộp origin/main vào feature/c-week4-tutor-analytics và kiểm thử.
- Nguồn: trạng thái Git, xung đột tutor_service.py, migration README và bộ pytest.
- Xử lý: giữ ngữ cảnh Tutor nhiều bài nhưng chỉ dùng lesson PUBLISHED; chuyển migration Tutor từ 0004 sang 0006 vì main dùng 0004 và 0005; loại đăng ký router review trùng.
- Kiểm thử: pytest backend/tests/ ai_pipeline/tests/ với cấu hình offline S3_BUCKET=learncloud-videos-mentorcloud: 196 passed, 23 failed, 16 skipped, 26 subtests passed.
- Vấn đề: test_lesson_approval không khởi tạo được do review_service thiếu S3StorageAdapter; test video URL và publish còn không khớp hành vi hiện tại. Các lỗi cần xử lý trước khi push.
- Tiếp theo: đối chiếu hợp đồng duyệt/publish và test với chủ sở hữu main; thử migration PostgreSQL trong môi trường phù hợp.
