# LearnCloud

LearnCloud là LMS video-first cho phép giảng viên tổ chức khóa học và bài học,
đồng thời hướng tới quy trình xử lý nội dung bằng AI trước khi phát hành. Phiên
bản trong repository này là MVP phát triển local: PostgreSQL chạy bằng Docker,
FastAPI cung cấp REST API và React/Vite cung cấp giao diện học viên.

## Trạng thái hiện tại

Các phần dưới đây đã có mã nguồn và có thể dùng để kiểm tra local:

- danh sách/chi tiết course đã publish;
- tạo, sửa course; tạo section và lesson với quyền instructor;
- xem section/lesson của course đã publish với user demo đã enrollment;
- tạo presigned S3 upload URL khi đã cấu hình AWS;
- module auth/JWT có route; để sử dụng cần áp dụng schema và migration database,
  đồng thời cấu hình `JWT_SECRET_KEY` trong `.env`.

Các mô-đun progress, quiz, AI review, Tutor, analytics và workflow video có
khung mã/schema hoặc được nêu trong roadmap, nhưng **chưa được đăng ký đầy đủ
vào FastAPI để coi là chức năng MVP sẵn sàng**. Không dùng chúng làm tiêu chí
nghiệm thu hoặc demo chính thức cho đến khi contract, router và test được hoàn
thiện.

## Kiến trúc ngắn gọn

```text
React/Vite (localhost:5173)
        │ HTTP/JSON
        ▼
FastAPI (localhost:8000) ─── PostgreSQL trong Docker (localhost:5434)
        │
        └── S3 presigned URL (tùy chọn, chỉ khi kiểm thử upload)
```

Trong local development, các route nghiệp vụ hiện nhận header
`X-Demo-User` để xác định user. Đây là cơ chế demo nội bộ, không phải cơ chế
xác thực đủ điều kiện triển khai công khai.

## Bắt đầu nhanh

1. Chuẩn bị Docker Desktop, Python và Node.js/npm.
2. Sao chép `.env.example` thành `.env`, rồi đặt `DATABASE_URL` theo giá trị
   local ở [hướng dẫn thiết lập](docs/local-setup.md).
3. Khởi động PostgreSQL, nạp schema, migration tương thích và seed theo
   [hướng dẫn local](docs/local-setup.md).
4. Cài/chạy backend và frontend.
5. Mở `http://127.0.0.1:8000/docs` để kiểm tra API hoặc
   `http://localhost:5173` để xem giao diện.

Lệnh, kiểm tra lỗi thường gặp và cách reset dữ liệu có tại
[docs/local-setup.md](docs/local-setup.md).

## Tài liệu

| Tài liệu | Nội dung |
| --- | --- |
| [Roadmap.md](Roadmap.md) | Phạm vi, owner, thứ tự ưu tiên và tiêu chí nghiệm thu MVP. |
| [architecture.md](architecture.md) | Kiến trúc đích, ownership và quy tắc phối hợp. |
| [docs/api-contract.md](docs/api-contract.md) | Contract API; các mục ghi “cần xác nhận” chưa phải cam kết triển khai. |
| [docs/local-setup.md](docs/local-setup.md) | Cài đặt/chạy local và smoke test. |
| [docs/database.md](docs/database.md) | Mô hình dữ liệu và các ràng buộc nghiệp vụ tại database. |
| [database/migrations/README.md](database/migrations/README.md) | Quy ước tạo và áp dụng migration. |
| [docs/demo-script.md](docs/demo-script.md) | Kịch bản demo theo đúng phạm vi hiện đang chạy. |
| [docs/aws-deployment.md](docs/aws-deployment.md) | Tài liệu triển khai AWS; chỉ dùng sau khi có checklist và review bảo mật. |

## Quy ước làm việc

- Làm việc trên nhánh `feature/<thành-viên>-<việc>`; giữ pull request nhỏ và
  có hướng dẫn kiểm tra.
- Khi đổi API hoặc database, cập nhật contract/schema/migration trong cùng PR
  và báo các owner bị ảnh hưởng.
- Không commit `.env`, access key, secret, presigned URL hoặc dữ liệu thật.
- Backend là nơi kiểm tra quyền, enrollment, unlock và chấm điểm; frontend chỉ
  hiển thị kết quả do backend trả về.
- Mọi thay đổi schema sau baseline phải có migration theo
  [quy ước migration](database/migrations/README.md).

## Kiểm tra trước khi bàn giao

- [ ] `docker compose up -d learncloud-db` báo database healthy.
- [ ] Schema và seed nạp thành công vào database sạch.
- [ ] `GET /health` trả `{"status":"ok"}`.
- [ ] FastAPI Swagger mở được tại `/docs`.
- [ ] `npm.cmd run build` chạy thành công trong `frontend/`.
- [ ] Chạy kịch bản ở [docs/demo-script.md](docs/demo-script.md) trên database
  sạch.

## Bảo mật và giới hạn

Không đưa API ra Internet khi route nghiệp vụ còn dựa vào `X-Demo-User`. Trước
khi triển khai công khai, nhóm cần chốt và tích hợp xác thực thực sự, kiểm tra
phân quyền ownership/enrollment/unlock, thêm test tự động và hoàn thiện
checklist triển khai/rollback AWS.
