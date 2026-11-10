# Cấp Local Auth cho Instructor/Admin hiện có

Ngày 10/11/2026. **Chỉ triển khai code và kiểm thử trên PostgreSQL riêng; không kết nối/ghi dữ liệu hoặc chạy migration trên RDS trong công việc này.** Không sửa DATABASE_URL, JWT_SECRET_KEY, LOCAL_AUTH_JWT_SECRET, `.env` hay cấu hình AWS.

## Cơ chế đã triển khai

- Công cụ mới: `backend/scripts/provision_local_auth.py`. Mặc định preview **read-only**; chỉ ghi khi có `--apply`, xác nhận tương tác và DB login được DBA cấp quyền.
- Chọn **user ID chính xác**, đối chiếu đồng thời email, role và Cognito subject đã duyệt. Không tìm/tạo/liên kết user theo email. Từ chối ID sai, email đăng nhập không phân biệt được, tài khoản STUDENT, identity/password đã tồn tại hoặc cấp lần hai.
- Chỉ cập nhật `users.password_hash` bằng Argon2id và thêm identity cho **chính user đó**. Không đổi id/name/email/role/cognito_sub, Course/Section/Lesson, khóa video hoặc ledger. Một transaction, khóa dòng user và kiểm tra lại trước khi ghi.
- Dấu vết gồm `provisioned_at`, `provisioned_by` lấy từ PostgreSQL `session_user`, `provisioning_reference` là mã phê duyệt. Không có API public/admin cho phép tự provisioning. App token có role ADMIN cũng không thay thế quyền DB của operator.
- Local login cho user có Cognito subject chỉ được chấp nhận khi có marker provisioning rõ ràng. Đồng bộ/confirm Cognito không còn xóa mật khẩu local; JWT/authorization guards vẫn đọc role hiện tại từ PostgreSQL.
- **Mailpit không được dùng để verify/reset mật khẩu của tài khoản được provisioning**, kể cả khi tài khoản bị hạ xuống STUDENT hoặc người khác biết OTP hợp lệ. Tài khoản privileged/Cognito chưa provisioning cũng không thể chiếm qua signup/OTP. STUDENT tự đăng ký tiếp tục dùng OTP như trước.

`verified_at` của identity do operator tạo thể hiện enrollment đã được quản trị viên phê duyệt; **không phải bằng chứng người nhận sở hữu email qua Mailpit**. Operator phải xác minh đúng người bằng kênh đáng tin cậy ngoài Mailpit.

## Chuẩn bị do nhóm phê duyệt — chưa thực hiện trên RDS

1. Xác nhận đây là database development/test được phép dùng Local Auth. Gate `APP_ENV=development/test` và `LOCAL_AUTH_ENABLED=true` hiện có được giữ nguyên, không thêm đường bỏ qua production gate.
2. Backup/snapshot, review migrations. Nếu chưa có, operator áp dụng `0007_dual_auth.sql`, rồi **`0008_local_auth_provisioning.sql` trước khi triển khai code mới**. Không replay mọi file `0004`. Migration 0008 chỉ thêm cột/check/registry; không tự enroll user và từ chối version trùng/schema một phần.
3. DBA chuẩn bị một DB login cá nhân, không dùng credential chung của ứng dụng. Ví dụ SQL bên dưới **chỉ là hướng dẫn cho DBA sau phê duyệt**, không được agent thực thi trên RDS. Nếu role/login đã tồn tại phải kiểm tra trước, không tạo lại tùy tiện:

```sql
CREATE ROLE learncloud_local_auth_provisioner NOLOGIN;
CREATE ROLE learncloud_operator_alice LOGIN INHERIT
    NOSUPERUSER NOCREATEDB NOCREATEROLE;
-- Trong psql, DBA đặt password qua prompt ẩn:
-- \password learncloud_operator_alice
GRANT learncloud_local_auth_provisioner TO learncloud_operator_alice;
GRANT CONNECT ON DATABASE learncloud TO learncloud_local_auth_provisioner;
GRANT USAGE ON SCHEMA public TO learncloud_local_auth_provisioner;
GRANT SELECT ON public.users, public.local_auth_identities,
    public.schema_migrations TO learncloud_local_auth_provisioner;
GRANT UPDATE(password_hash) ON public.users TO learncloud_local_auth_provisioner;
GRANT INSERT ON public.local_auth_identities TO learncloud_local_auth_provisioner;
```

Không cấp group này cho DB login của Frontend/Backend thông thường. CLI xác minh membership phía PostgreSQL và yêu cầu login trực tiếp, không dùng SET ROLE để giả danh operator. Với DBA/superuser có quyền hệ thống sẵn có, phải áp dụng cùng quy trình phê duyệt nội bộ. Thu hồi membership/quyền tạm khi hoàn tất theo chính sách nhóm.

## Provisioning một lần trên Windows

Quản trị viên được ủy quyền lấy user ID và các thuộc tính từ danh sách đã kiểm chứng; tạo ticket ghi rõ người nhận và cách xác minh danh tính. Tại root repository, ví dụ **thay mọi placeholder bằng giá trị đã duyệt**:

```powershell
$provisionArgs = @(
  '--user-id', '<USER_ID>',
  '--expected-email', '<EMAIL_HIEN_TAI>',
  '--expected-role', 'INSTRUCTOR',
  '--expected-cognito-sub', '<SUB_HIEN_TAI_HOAC_NONE>',
  '--operator-db-user', 'learncloud_operator_alice',
  '--approval-reference', '<MA_TICKET>'
)
.\.venv\Scripts\python.exe backend/scripts/provision_local_auth.py @provisionArgs

# Chỉ sau khi preview đúng người/đúng database và đã được phê duyệt:
.\.venv\Scripts\python.exe backend/scripts/provision_local_auth.py @provisionArgs --apply
```

Dùng `ADMIN` cho tài khoản Admin; dùng chính xác `NONE` nếu cognito_sub là SQL NULL. Email/role/subject là điều kiện đối chiếu, không phải giá trị mới để ghi đè.

CLI giữ host/port/database/TLS từ DATABASE_URL hiện có, chỉ dùng credential operator riêng **trong connection tạm**, không ghi lại URL hoặc sửa biến môi trường. Nó hỏi password DB bằng prompt ẩn, hiển thị preview không có secret, rồi yêu cầu nhập đúng `PROVISION <USER_ID>` và nhập mật khẩu local hai lần, 12–128 ký tự. Không nhận password qua CLI arguments, env hoặc stdin pipe; không echo/log password/hash.

Giảng viên có thể nhập mật khẩu của mình trên terminal quản trị đáng tin cậy. Nếu operator cấp mật khẩu ban đầu, chuyển riêng bằng kênh bí mật đã xác minh người nhận; người nhận đăng nhập rồi đổi tại Profile bằng mật khẩu hiện tại. **Không gửi mật khẩu hay link cấp quyền qua Mailpit.** Hai mật khẩu Cognito/local độc lập. Quên mật khẩu local của tài khoản provisioned cần quy trình phục hồi được phê duyệt riêng; công cụ một lần này cố ý không ghi đè credential đã có.

## Đăng nhập và kiểm tra không đổi dữ liệu

- Giữ Frontend `VITE_USE_MOCK=false`, chọn `VITE_USE_AUTH_MOCK=true`, restart Frontend nếu đổi chế độ. Backend đã bật local và có migrations 0007/0008; không cần Cognito ID để đăng nhập local.
- Đăng nhập bằng email hiện có/mật khẩu local. `GET /auth/me` phải trả **đúng ID và role đang có trong users**. Instructor kiểm tra `GET /courses/instructor/me`, giao diện khóa học và các Section/Lesson cũ; Admin kiểm tra `/admin/users` bằng guard Admin. Admin không tự có quyền của Instructor chỉ vì đăng nhập local.
- Trước/sau provisioning, người được phép có thể so sánh read-only các ID/FK và khóa video. Ví dụ psql với biến `reviewed_user_id` đã được đặt đúng:

```sql
SELECT u.id, u.email, u.role, u.cognito_sub,
       c.id AS course_id, c.instructor_id,
       s.id AS section_id, l.id AS lesson_id,
       l.raw_video_key, l.processed_video_key
FROM users u
LEFT JOIN courses c ON c.instructor_id=u.id
LEFT JOIN sections s ON s.course_id=c.id
LEFT JOIN lessons l ON l.section_id=s.id
WHERE u.id = :reviewed_user_id
ORDER BY c.id,s.id,l.id;
```

- Chuyển `VITE_USE_AUTH_MOCK=false` và restart Frontend để dùng Cognito như cũ. Local/Cognito phải trả cùng user ID; Cognito login không xóa mật khẩu local, token cũ không khôi phục role đã thu hồi.
- Nếu migration chưa COMMIT thì rollback transaction. Sau provisioning không xóa user hoặc tạo user thay thế để rollback: dừng luồng local và lập thao tác thu hồi identity/session riêng được phê duyệt, giữ dữ liệu nghiệp vụ. Khi lỗi kết nối lúc COMMIT, kiểm tra trạng thái trước khi retry; CLI từ chối cấp lần hai.

## Kiểm thử và file thay đổi

Kết quả: **96 pass / 15 skip** ở bộ auth/P0 offline (15 ca PostgreSQL được chạy riêng); **64 pass / 1 skip** trên PostgreSQL/Mailpit riêng (chỉ skip ca kiểm tra SQLite fail-closed đã pass offline); **52 test Frontend pass**. Migration 0008 áp dụng thành công trên test DB, từ chối replay và không tự provision identity cũ. `git diff --check` pass; fingerprint các file cấu hình/`.env` được bảo vệ không đổi.

Test dùng `127.0.0.1:55439/learncloud_auth_test` với guard URL riêng; không lấy DATABASE_URL trong `.env` làm target. PostgreSQL test dùng ACL operator tối thiểu thật và CLI connection riêng; password authentication tới RDS chưa được kiểm chứng. JWT Cognito dùng RSA ký thật với JWKS fixture, không gọi AWS. Chưa chạy provisioning/login trên RDS hoặc Cognito AWS thật; chưa test UI giảng viên mới bằng browser trong lần thay đổi này.

Chạy bộ offline: `.\.venv\Scripts\python.exe backend/tests/run_auth_offline.py`. Các test DB chỉ bật qua `LEARNCLOUD_RUN_AUTH_DB_TESTS=1` và URL test riêng đã chuẩn bị schema/role/ACL; tuyệt đối không dùng RDS làm target test. Dịch vụ PostgreSQL/Mailpit tạm phục vụ kiểm thử được dừng sau khi hoàn tất.

Các test bao gồm: Instructor/Admin có/không cognito_sub, cùng user ID/role, snapshot toàn bộ Course/Section/Lesson/VideoUpload/VideoPipelineRun trước/sau, đúng hai DML provisioning, preview không ghi, ID/subject/email/role sai, login không được cấp quyền, SET ROLE, xác nhận CLI sai, cấp lần hai, mật khẩu được đổi bằng credential hiện tại, Mailpit takeover bị chặn và Cognito không xóa hash.

File sửa: `backend/app/models/local_auth.py`, `backend/app/services/local_auth_service.py`, `backend/app/services/auth_service.py`, `backend/tests/unit/test_dual_auth.py`, `backend/tests/run_auth_offline.py`. File thêm: `backend/app/services/local_auth_provisioning.py`, `backend/scripts/provision_local_auth.py`, `database/migrations/0008_local_auth_provisioning.sql`, `backend/tests/unit/test_local_auth_provisioning.py` và báo cáo này. Không sửa Frontend hoặc cấu hình/secret.
