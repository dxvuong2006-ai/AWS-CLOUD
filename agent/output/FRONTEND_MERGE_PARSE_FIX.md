# Frontend merge conflict and Vite parse fix

- **Ngày thực hiện:** 2026-11-07
- **Mục tiêu:** Tìm nguyên nhân lỗi Vite parse trong frontend và sửa các xung đột merge còn sót trong source frontend.

## Tài liệu và source đã kiểm tra

- `frontend/INTEGRATION.md` — các hợp đồng tích hợp frontend, trạng thái API tiến độ/media và kiểm tra xác nhận.
- `docs/ui-doc/ui-spec/SPEC.md` — luồng đăng nhập, điều hướng theo vai trò, khóa học, video và checkpoint.
- Source frontend trong `frontend/src/`, tập trung vào app/router, API adapters, hooks, trang học và player.
- Backend course routes/schema để xác nhận API chi tiết khóa học có sections và lessons.
- `agent/input/` có đặc tả giao diện PDF và báo cáo AWS PDF. Không trích xuất được PDF trong môi trường này do quyền chạy Python bị từ chối; báo cáo AWS không liên quan đến lỗi parse frontend.

## Phân tích và thay đổi

Vite lỗi vì các dấu phân cách merge (`<<<<<<<`, `=======`, `>>>>>>>`) còn nằm trong JSX và JavaScript. Lỗi ban đầu xuất hiện trong `App.jsx` và `api/client.js`; quét toàn bộ `frontend/src` phát hiện conflict còn lại trong các API khóa học/bài học, hooks, component outline/navbar/video, trang course detail/learning và routes.

Đã giải quyết nội dung các conflict frontend theo triển khai tính năng tích hợp, giữ hook tải tài nguyên dùng chung và bổ sung `fetchCourseOutline` để tương thích với hook hiện có. Không sửa backend; conflict của `backend/app/schemas/quiz.py` nằm ngoài phạm vi sửa lỗi Vite.

## Kết quả và bằng chứng xác minh

- Quét `frontend/src` không còn dòng conflict marker.
- Chạy `vite build` từ thư mục `frontend`: **thành công**, 93 modules được transform và bundle production được tạo.
- Vite còn cảnh báo dependency React Router về chỉ thị module-level `use client`; cảnh báo này không làm build thất bại.
- Không chạy test suite; chỉ xác minh build theo yêu cầu sửa lỗi parse.

## Vấn đề chưa giải quyết

- Git vẫn báo các file liên quan là `UU` vì index chưa được cập nhật. `.git` chỉ có quyền đọc trong môi trường này nên không thể dùng `git add` để đánh dấu conflict đã giải quyết. Nội dung frontend trong working tree đã được sửa; thao tác cập nhật index cần chạy trong môi trường có quyền ghi `.git`.
- `backend/app/schemas/quiz.py` vẫn ở trạng thái `UU` trong Git và chưa được xử lý.
- Không xác nhận các API tiến độ/media còn ghi là pending trong `frontend/INTEGRATION.md` hoạt động với backend thực.

## Đề xuất tiếp theo

1. Trong môi trường có quyền ghi Git index, rà soát diff và stage các file frontend đã giải quyết.
2. Xử lý conflict backend `backend/app/schemas/quiz.py` riêng, sau đó chạy các kiểm tra backend/frontend phù hợp.
3. Thực hiện các kịch bản chấp nhận thủ công được liệt kê trong `frontend/INTEGRATION.md` khi các API backend pending sẵn sàng.
