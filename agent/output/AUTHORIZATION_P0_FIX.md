# LearnCloud — sửa Authentication/Authorization P0

Ngày: 09/11/2026. Căn cứ: `API_CONTRACT_IMPLEMENTATION_AUDIT.md`, các phát hiện Q03, Q26, Q31, Q32. Đã sửa source và xác minh bằng unit/ASGI test với SQLite/mock.

## Chính sách quyền và thay đổi

- **PostgreSQL `users.role` là nguồn role có thẩm quyền duy nhất.** Không tạo/cập nhật role từ `cognito:groups`, kể cả claims từ API Gateway authorizer. Identity mới tự đồng bộ chỉ nhận STUDENT; INSTRUCTOR/ADMIN phải được provision trong DB qua luồng có thẩm quyền. Không tự cấp quyền chỉ vì tài khoản có Cognito group.
- Hạ/cấp role có hiệu lực ở **request tiếp theo sau khi thay đổi DB commit**, kể cả dùng lại cùng JWT còn hạn. Truy vấn identity refresh cả ORM cache. JWT vẫn xác thực danh tính; mất role đặc quyền không đồng nghĩa đăng xuất Cognito hoặc hủy token. Request đã được xác thực và đang chạy không bị hủy hồi tố.
- Không cho JWT sync dùng email để ghi đè một `cognito_sub` khác đã được gán và kế thừa quyền của account đó.
- Flashcard dùng guard chung: phải **INSTRUCTOR và đúng `course.instructor_id`**. PUT/DELETE/POST từ Student, former Instructor hoặc Admin không có quyền Instructor owner bị 403; PUT không thể dùng `is_approved=true` để vượt guard. Owner hợp lệ vẫn sửa/approve/xóa được; Student enrolled vẫn đọc được thẻ approved/published.
- Hạ role Admin cuối trả **409**, trước sửa dữ liệu hoặc gọi Cognito; `role=null` trả **422**. Khi đổi role, khóa tập Admin theo thứ tự ID bằng `SELECT ... FOR UPDATE`, đọc lại target và kiểm lại quyền caller sau khi lấy khóa. Khi còn Admin khác, được phép hạ quyền bình thường. Lỗi đồng bộ role Cognito rollback thay đổi DB.
- Giữ nguyên hàm xác minh Cognito JWT, JWKS URL, đọc authorizer claims và dependencies Bearer; đã đối chiếu AST với HEAD. **Không khôi phục X-Demo-User.**

## File thay đổi

| File | Nội dung |
|---|---|
| `backend/app/services/auth_service.py:97` | Bỏ group → role, mặc định identity mới STUDENT, chặn rebind sub đã gán. |
| `backend/app/repositories/auth_repo.py:21` | Refresh identity từ DB khi đọc theo Cognito sub. |
| `backend/app/api/flashcards.py:37` | Guard role INSTRUCTOR + ownership thống nhất; bỏ Admin bypass. Guard cũng áp dụng đọc draft phía quản lý. |
| `backend/app/api/admin.py:69` | Last-admin guard, row locks, kiểm caller, null-role validation và rollback khi Cognito lỗi. |
| `backend/tests/unit/test_authorization_p0.py` | 39 trường hợp regression, gồm JWT ký RSA thật, ownership, dữ liệu không đổi khi bị từ chối, cache role và last-admin. |

## Kết quả trước/sau

| Phạm vi | Trước sửa | Sau sửa |
|---|---|---|
| **Cùng 43 test**: 36 regression ban đầu + 7 auth cũ | **22 đạt, 21 lỗi** | **43 đạt, 0 lỗi** |
| Nhóm Auth/P0 hiện tại, thêm 3 ca mở rộng | — | **46 đạt, 0 lỗi** |
| Auth/P0 + Review + Tutor/Analytics + Checkpoint + Enrollment | — | **98 đạt, 0 lỗi** |
| Toàn bộ `backend/tests/unit` | Kiểm toán trước: 137 đạt, 75 lỗi | **176 đạt, 75 lỗi**, thêm 6 subtest đạt |

Đối chiếu node ID: **75 lỗi toàn bộ unit suite trùng tập lỗi của kiểm toán trước; không có failure mới**. Các lỗi cũ ở approval/video/processing/quiz ngoài phạm vi sửa này được giữ nguyên. Ba ca mở rộng kiểm tra cache identity cũ, Student đọc Flashcard và Admin tự rời quyền khi còn Admin khác.

Test mới không mock `jwt.decode` hoặc override `get_current_user`: dùng JWT RS256 ký local và chỉ mock lấy JWKS key cùng các thao tác quản trị Cognito. Đã kiểm token hết hạn, sai chữ ký/issuer/client/token_use → 401; X-Demo-User không đăng nhập/nâng quyền; token group cũ không khôi phục role; ghi/xóa trái phép không đổi dữ liệu; last-admin bị từ chối trước mọi call Cognito.

Pytest chạy qua harness offline dựa trên `backend/tests/run_unit_offline.py`, với settings/credentials giả, SQLite RAM, network bị chặn, `PYTHONDONTWRITEBYTECODE=1`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` và `-p no:cacheprovider`. Không dùng unittest discovery để thay cho pytest function tests. `git diff --check` đạt.

## Giới hạn xác minh

Không thay đổi production DB/AWS, schema hoặc migrations; không chạy migrations. PostgreSQL concurrency/row locks thực và Cognito/API Gateway triển khai thật: **UNVERIFIED**. Unit test đã kiểm câu SQL PostgreSQL có khóa `FOR UPDATE` theo thứ tự; không coi SQL compile/SQLite là kiểm thử đồng thời PostgreSQL. Đồng bộ Cognito và DB chưa phải distributed transaction; kết quả API lỗi không được diễn giải là role đã đổi thành công.
