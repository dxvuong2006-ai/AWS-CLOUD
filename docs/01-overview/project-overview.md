# Tổng quan dự án

Tài liệu này trình bày bài toán, mục tiêu, phạm vi MVP, người dùng và nhóm thực hiện LearnCloud.

## Bài toán

Giảng viên thường phải tự tạo transcript, tóm tắt và câu hỏi sau khi quay video; chi phí này tăng nhanh khi có nhiều lesson. Học viên khó tìm lại đoạn kiến thức trong video dài và khó biết nên ôn phần nào sau khi làm sai. Giảng viên cũng cần theo dõi enrollment, tiến độ và tỷ lệ đạt mà không biến AI thành nguồn nội dung không kiểm soát.

LearnCloud giải quyết bằng một quy trình có human-in-the-loop: video được xử lý bất đồng bộ, nội dung AI là bản nháp, giảng viên duyệt/sửa rồi mới publish. Việc chấm điểm, quyền truy cập và mở khóa được quyết định ở backend thay vì tin giao diện.

## Mục tiêu MVP

1. Giảm công soạn học liệu từ video nhưng giữ giảng viên chịu trách nhiệm chất lượng.
2. Tạo lộ trình course → section → lesson có checkpoint và gate mở khóa rõ ràng.
3. Cho học viên xem video cùng transcript, summary, flashcard và ôn đúng phần làm sai.
4. Cho giảng viên xem học viên, tiến độ và kết quả; cho người vận hành theo dõi job/log.
5. Tách adapter local/AWS để phát triển nghiệp vụ mà không coi mock là bằng chứng AI production.

## Vai trò

| Vai trò | Nhu cầu | Khả năng có trong source |
|---|---|---|
| Instructor | Tổ chức khóa học, upload video, duyệt học liệu, theo dõi kết quả | Trang course/editor/upload/review/report; API course, section, lesson, upload, review, analytics |
| Student | Học có thứ tự, xem lại nhanh, tự kiểm tra và ôn sai | Catalog/enrollment, lesson content/video URL, progress, flashcard, checkpoint, remediation và Tutor |
| Admin | Quản lý tài khoản và quan sát vận hành cơ bản | API/UI user lifecycle và monitoring jobs; Cognito/CloudWatch thực tế chưa xác minh hiện hành |

## Phạm vi chức năng

Tám module M1–M8 là cách chia **chức năng**, không phải tám microservice độc lập:

- M1 Authentication; M2 Course & Student Management; M3 Video Storage & Upload; M4 AI Content Pipeline.
- M5 Content Review & Publishing; M6 Learning, Flashcard & Checkpoint; M7 AI Tutor Remediation; M8 Analytics & Monitoring.

Xem ranh giới chi tiết tại [kiến trúc chức năng](../02-architecture/functional-architecture.md). K1–K6 là cách ánh xạ các module lên AWS, được mô tả riêng tại [kiến trúc AWS](../02-architecture/aws-architecture.md).

## Ngoài phạm vi và không nên suy diễn

- Enrollment là ghi danh học, **không phải thanh toán**.
- Không có payment/subscription, livestream, marketplace, mobile app native, DRM hay chống tải xuống đầy đủ.
- Ngưỡng checkpoint 50/80 là luật cố định, chưa phải adaptive learning.
- AI Tutor là hỗ trợ có ngữ cảnh theo bài sai; không phải chatbot đa dụng hay RAG quy mô lớn.
- Pipeline sinh nội dung từ video (M4) và AI Tutor (M7) là hai use case khác nhau.



