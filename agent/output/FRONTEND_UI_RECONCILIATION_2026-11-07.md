# LearnCloud - Đối chiếu giao diện và hoàn thiện Frontend

- **Ngày thực hiện:** 07/11/2026
- **Mục tiêu:** Đối chiếu source frontend với UI Design Spec/UI Flow v4, thay thế các route placeholder còn lại và khớp luồng điều hướng theo role.

## 1. Tài liệu và source đã kiểm tra

- `agent/input/LearnCloud_UI_Design_Spec_v3.pdf`
- `docs/ui-doc/ui-spec/SPEC.md`
- `docs/ui-doc/ui-spec/screens/` và các màn hình luồng UI
- `frontend/src/routes/AppRoutes.jsx`
- Các trang học viên, giảng viên và quản trị trong `frontend/src/pages/`
- Mock data và API client trong `frontend/src/mocks/` và `frontend/src/api/`
- `agent/output/PROJECT_PROGRESS_ASSESSMENT_2026-11-07.md`

## 2. Công việc đã thực hiện

### Routing và phân quyền

- Đã thay các route placeholder bằng trang thực cho:
  - Tiến độ học viên.
  - Tổng quan, khóa học và tạo/chỉnh sửa khóa học của giảng viên.
  - Hàng đợi review và review lesson AI.
  - Báo cáo học viên.
  - Quản trị tài khoản, vai trò và giám sát hệ thống.
- Thêm route cho tạo/chỉnh sửa khóa học, chi tiết lesson review, chi tiết học viên và tài khoản quản trị.
- Chuẩn hóa role `TEACHER` thành `INSTRUCTOR` trong logic landing page và kiểm tra quyền.

### Giao diện hoàn thiện

- Thêm trang tiến độ với tiến độ khóa học, lịch sử lesson và trạng thái hoàn thành.
- Thêm dashboard giảng viên, danh sách khóa học và form tạo/chỉnh sửa khóa học.
- Thêm hàng đợi học liệu AI, review tóm tắt/khái niệm/transcript và hành động duyệt trong phiên demo.
- Thêm danh sách học viên, trang chi tiết học viên và dữ liệu báo cáo demo.
- Thêm quản trị tài khoản, tạo/sửa tài khoản, vai trò và trang giám sát job.
- Thêm stylesheet chung cho khu vực quản trị/giảng viên theo bảng màu LearnCloud.

### Video demo

- Đổi toàn bộ URL video mock từ các file không tồn tại sang `/cloud.mp4`, file media có trong `frontend/public/`.

## 3. Bằng chứng kiểm thử

- `npm.cmd run build`: pass, Vite build thành công.
- `npm.cmd test`: pass, 41/41 unit test.
- `npm.cmd run test:browser`: pass, smoke duyệt đăng ký, xác minh, đăng nhập, đăng ký khóa học, lộ trình, video, checkpoint, hồ sơ, recovery và phân quyền role.

## 4. Kết quả

- Không còn route frontend hiển thị “Chức năng đang được xây dựng” trong các luồng student/instructor/admin đã khai báo.
- Frontend build và các luồng smoke hiện có bằng chứng pass.
- Các màn mới thuộc khu vực giảng viên/quản trị dùng dữ liệu demo/local UI hoặc mock; chưa được coi là nghiệp vụ production.

## 5. Vấn đề chưa giải quyết

- Backend chưa có API production cho email verification/recovery/profile, progress/media thực sự, analytics giảng viên và admin account/role.
- Các trang giảng viên/quản trị mới vẫn cần nối API thật thay mock/static data.
- Pipeline AI/video, migration DB và AWS inventory vẫn cần xác minh theo báo cáo tiến độ hiện có.
- Không thay đổi resource AWS, database production hoặc credentials trong nhiệm vụ này.

## 6. Công việc tiếp theo

1. Đối chiếu từng route mới với API contract và thay dữ liệu demo bằng backend thật.
2. Hoàn thiện backend progress và media theo hợp đồng đã ghi trong `frontend/INTEGRATION.md`.
3. Kết nối review lesson, course management, analytics và admin APIs.
4. Thực hiện smoke/build trên môi trường AWS sau khi Cognito/API Gateway/database được cấu hình xác nhận.
