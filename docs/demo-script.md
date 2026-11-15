# Kịch bản demo local

Thời lượng 3–5 phút. Kịch bản minh họa ứng dụng và API local, không phụ thuộc AWS và không khẳng định các chức năng production chưa được xác minh đang hoạt động.

## Chuẩn bị

Làm theo [hướng dẫn thiết lập local](local-setup.md), cấu hình database/auth local rồi khởi động backend và frontend. Chỉ dùng dữ liệu local có thể bỏ. Không trình chiếu secret, access token hoặc presigned URL.

## Trình tự demo

1. Mở `http://127.0.0.1:8000/health` và cho thấy API local phản hồi. Kết quả này chỉ xác nhận tiến trình backend local.
2. Mở `http://127.0.0.1:8000/docs` để cho thấy OpenAPI runtime của FastAPI là API reference hiện tại.
3. Mở `http://localhost:5173` và đi qua luồng phù hợp với cấu hình local. Nói rõ frontend đang kết nối backend local hay chạy ở mock mode.
4. Nếu đã chuẩn bị thao tác có lưu database, chỉ dùng tài khoản test/seed local có thể bỏ và trình bày một luồng đã được kiểm thử. Không nói rằng SQLite/offline test chứng minh tích hợp AWS hoặc PostgreSQL concurrency gate đã pass.
5. Kết thúc bằng cách nêu rõ bằng chứng hiện có: source và offline test; các suite có PostgreSQL gate và trạng thái triển khai AWS hiện tại vẫn chưa xác minh, như ghi trong [yêu cầu](requirements.md) và [báo cáo regression](operations/backend-regression-report.md).

## Dừng và dọn môi trường

Dừng Uvicorn/Vite bằng `Ctrl+C`. Nếu đã khởi động dịch vụ local, dừng bằng `docker compose stop`. Giữ lại Compose volume trừ khi chủ sở hữu dữ liệu chủ động chọn xóa dữ liệu local.
