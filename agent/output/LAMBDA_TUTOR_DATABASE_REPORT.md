# Báo cáo kết nối Lambda và Tutor

- Ngày: 2026-11-09.
- Đã kiểm tra: handler, review repository, model Flashcard, Tutor service/API/schema và unit test.
- Lambda trả payload mặc định; AI_PROCESSOR_WRITE_DB=true kích hoạt ghi DB và yêu cầu instructor_id. Ghi lesson, quiz, flashcard trong transaction và rollback khi lỗi.
- Tutor có endpoint /tutor/remediations; chỉ xử lý câu sai đã nộp thuộc học viên và bài đã publish.
- Fallback Tutor dùng heuristic bám câu hỏi gốc; MockAIAdapter chưa hỗ trợ Tutor trực tiếp.
- Unit test: 196 passed, 6 subtests passed. Test DB dùng SQLite, AWS dùng mock.
- Chưa xác minh AWS Lambda/PostgreSQL thật. instructor_id trong event phải đến từ nguồn nội bộ đáng tin cậy.
