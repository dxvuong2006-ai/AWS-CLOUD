# Báo cáo Nova Micro và Lambda

- Ngày: 2026-11-09.
- Mục tiêu: chuyển test sang Converse, hoàn thiện flashcards và payload Lambda.
- Đã kiểm tra adapter, schemas, review service và test backend.
- Nova dùng Converse; mock được cập nhật trong test_review_service.py.
- Lambda nhận transcript text hoặc S3, tạo review_content, flashcards và trạng thái dự kiến REVIEW_REQUIRED.
- Key takeaway được sinh riêng; fallback thêm tiền tố nhận diện.
- Test: 192 passed, 6 subtests passed; py_compile đạt.
- Giới hạn: Lambda trả payload và chưa ghi DB. State machine vẫn cần ARN và tích hợp thực tế; chưa chạy AWS/PostgreSQL thật.
