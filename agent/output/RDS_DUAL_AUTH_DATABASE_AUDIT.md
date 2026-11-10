# Audit database RDS và lỗi Dual Auth

Mốc thời gian ghi nhận trong audit: **10/11/2026, 14:28, Asia/Saigon (UTC+7)**. Đây là audit read-only; không áp dụng migration, không tạo bảng/user/OTP, không gọi API đăng ký, không thay đổi AWS hoặc RDS.

## 1. Trả lời năm câu hỏi chính

| Câu hỏi | Kết luận và mức xác nhận |
|---|---|
| Backend hiện tại có dùng Amazon RDS thật không? | **Đích database của cấu hình Backend hiện tại là Amazon RDS thật**, đã kết nối SQL thành công qua đúng URL hiệu lực. Tuy nhiên không tìm thấy tiến trình FastAPI/port 8000 ở thời điểm audit, nên không thể xác nhận riêng environment của tiến trình đã phát sinh lỗi trước đó. |
| SSM Tunnel có hoạt động không? | **Có.** `session-manager-plugin.exe` giữ listener `127.0.0.1:15437`, dùng document remote-host forwarding, đích là endpoint RDS. Kết nối PostgreSQL qua cổng này thành công. |
| Backend đang kết nối database nào? | URL hiệu lực trỏ `127.0.0.1:15437`, database **`learncloud`**, username **`learncloud_admin`**. SQL xác nhận server thực tế **`172.31.5.232:5432`**, PostgreSQL **16.9**, schema hiện tại **`public`**. Đây không phải PostgreSQL Docker local tại port 5434. |
| RDS thiếu bảng/migration nào? | Thiếu cả **`local_auth_identities`**, **`local_auth_otps`**, **`local_auth_sessions`**, không có bản ghi **`0007`**. Ngoài phạm vi auth, còn thiếu cấu trúc checkpoint-idempotency và một số trường remediation; registry `0004` xung đột lịch sử. Xem phần 4 để tránh hiểu nhầm rằng cứ thiếu version là phải chạy lại migration. |
| Cần làm gì để đăng ký Student và nhận OTP? | Nhóm xác nhận đúng môi trường RDS được phép dùng local auth, backup/review và phê duyệt, rồi operator áp dụng **chỉ migration `0007_dual_auth.sql`** theo quy trình ở phần 6. Mailpit hiện đã truy cập được; sau migration kiểm tra schema/quyền, khởi động Backend hiện không chạy, rồi nhóm được phép mới kiểm thử đăng ký. Không cần sửa code hoặc đổi DATABASE_URL để chữa lỗi thiếu bảng này. |

**Chưa xác định RDS này được tổ chức phân loại production hay development/test.** `APP_ENV=development` của chương trình trên máy không chứng minh database RDS cũng là môi trường development. Vì vậy audit chỉ đọc; không dùng kết quả này làm phê duyệt ghi dữ liệu vào RDS.

## 2. Cách DATABASE_URL được nạp

Đã đọc trực tiếp:

- `backend/app/config.py`: `PROJECT_ROOT = Path(__file__).resolve().parents[2]`; Settings đọc `.env` ở root repository bằng UTF-8, `extra="ignore"`.
- `backend/app/database.py`: `database_url = settings.DATABASE_URL`; tạo SQLAlchemy engine từ giá trị này. Không ghép lại URL từ DB_HOST/DB_USER, không có nhánh Lambda/SSM lấy mật khẩu trong code hiện tại.
- Root `.env`: có **một** định nghĩa DATABASE_URL đang hoạt động, tại dòng 9.
- `backend/.env`: không có DATABASE_URL được parser trả về; file này cũng không được Settings hiện tại tự nạp.

Đã đối chiếu thứ tự nguồn bằng chính pydantic-settings được cài trên máy:

1. Tham số truyền vào `Settings(...)`.
2. Biến môi trường của process.
3. File `.env`.
4. File secrets, rồi giá trị mặc định.

Source dùng `Settings()` không truyền URL vào constructor. Trong process audit, không có DATABASE_URL kế thừa; cũng không có các biến PGHOST/PGPORT/PGDATABASE/PGUSER/PGSERVICE/PGOPTIONS hay các DB_HOST/DB_NAME/DB_USER/Lambda được kiểm tra. DATABASE_URL ở Windows User/Machine environment cũng không được đặt tại thời điểm đọc registry.

Giá trị `settings.DATABASE_URL` và `engine.url` đều khớp root `.env`, sau khi che mật khẩu:

| Thành phần | Giá trị |
|---|---|
| Driver | `postgresql+psycopg2` |
| Host kết nối của ứng dụng | `127.0.0.1` |
| Port kết nối của ứng dụng | `15437` |
| Database | `learncloud` |
| Username | `learncloud_admin` |
| TLS option | `sslmode=require` |

Không xuất URL đầy đủ, mật khẩu, JWT_SECRET_KEY hoặc LOCAL_AUTH_JWT_SECRET. Chỉ kiểm tra secret local có được cấu hình hay không, không đọc giá trị ra báo cáo.

**Giới hạn:** môi trường process audit không phải bằng chứng tuyệt đối về environment của một Uvicorn khác đã đóng, một shell khác, hoặc deployment Lambda/AWS từ xa. Pydantic vẫn cho phép process env ghi đè `.env` khi Backend được khởi động từ môi trường khác. Không kiểm tra/deploy/chỉnh environment của ứng dụng trên AWS.

## 3. Xác nhận bằng kết nối thực tế

### 3.1. Tunnel

Quan sát process và listener, không in raw command line vì Session Manager có thể chứa session token:

- `aws.exe`: PID **31040**.
- `session-manager-plugin.exe`: PID **30740**, parent PID **31040**.
- Listener `127.0.0.1:15437` thuộc PID **30740**.
- Process parameters có document **`AWS-StartPortForwardingSessionToRemoteHost`**, local port **15437**, remote port **5432**.
- Endpoint đích trích từ metadata process: **`learncloud-db.cjswky2qyz14.ap-southeast-1.rds.amazonaws.com`**.

Không mở/đóng/restart tunnel, không gọi AWS CLI/API để kiểm tra account/instance. Sự tồn tại listener được kiểm chứng thêm bằng kết nối SQL tới server remote qua tunnel; không chỉ suy ra từ dòng `127.0.0.1` trong `.env`.

### 3.2. PostgreSQL

Tạo connection audit riêng từ settings hiện tại, với `default_transaction_read_only=on`, connect timeout 5 giây, statement timeout 8 giây và lock timeout 2 giây. Các connection đều rollback/đóng sau khi đọc.

Truy vấn danh tính tương đương:

```sql
SELECT current_database(), current_user,
       inet_server_addr(), inet_server_port(), current_schema(),
       current_setting('search_path'),
       current_setting('transaction_read_only'),
       current_setting('default_transaction_read_only'),
       current_setting('server_version');
```

| Kết quả trực tiếp | Giá trị |
|---|---|
| `current_database()` | `learncloud` |
| `current_user` | `learncloud_admin` |
| `inet_server_addr()` | `172.31.5.232` — kiểu inet trả `/32` |
| `inet_server_port()` | `5432` |
| `current_schema()` | `public` |
| `search_path` | `"$user", public` |
| `transaction_read_only` | `on` |
| `default_transaction_read_only` | `on` **trong connection audit**, không phải khẳng định cấu hình toàn RDS |
| Server version | `16.9` |
| TLS thực tế | `TLSv1.3`, cipher `TLS_AES_256_GCM_SHA384` |

Có các role hệ thống `rdsadmin`, `rds_superuser`, `rds_iam`. Kết hợp endpoint `.rds.amazonaws.com`, process SSM, địa chỉ remote và role RDS, đây là xác nhận thực tế đích kết nối RDS, không phải suy luận chỉ từ `.env`.

`sslmode=require` và phiên TLS xác nhận đường kết nối được mã hóa; audit không nâng kết luận này thành kiểm chứng hostname/certificate kiểu `verify-full`, và không thay đổi TLS configuration.

### 3.3. Backend và Mailpit đang chạy

- Không có listener port **8000** tại thời điểm audit.
- Không tìm thấy process Python/Uvicorn/FastAPI của workspace; process Python nhìn thấy là pgAdmin, không phải Backend LearnCloud.
- Danh sách container đang chạy có `learncloud-db` tại **5434** và `aws-cloud-mailpit-1` tại **1025/8025**; không thấy container LearnCloud FastAPI.
- RDS có các connection khác với application_name trống/pgAdmin. Không có đủ bằng chứng để gán chúng cho Backend đã báo lỗi; không đọc query text hoặc dữ liệu user của các connection này.
- Mailpit image hiện chạy: **`axllent/mailpit:v1.27.10`**.
- SMTP `localhost:1025`: kết nối và lệnh **NOOP trả 250**. Không gửi email.
- Web UI `http://localhost:8025/`: **HTTP 200**, nhận diện nội dung Mailpit. Không đọc danh sách/nội dung email.

Frontend `.env` hiện có `VITE_USE_MOCK=false`, `VITE_USE_AUTH_MOCK=true`, API `http://localhost:8000`. Backend settings mới nạp có `APP_ENV=development`, `LOCAL_AUTH_ENABLED=true`, SMTP `localhost:1025`, secret local có được đặt. Chưa gửi OTP end-to-end trong audit vì request đăng ký sẽ ghi dữ liệu RDS.

## 4. Đối chiếu schema và migration

### 4.1. Dual Auth 0007

Đã đọc `pg_class`, `pg_namespace`, `information_schema.columns`, `pg_constraint`, `pg_indexes`; không đọc nội dung users/password_hash/OTP/session.

| Đối tượng cần có | Schema thực tế |
|---|---|
| `public.local_auth_identities` | **Không tồn tại** |
| `public.local_auth_otps` | **Không tồn tại** |
| `public.local_auth_sessions` | **Không tồn tại** |
| Các bảng `local_auth_%` ở schema khác | Không tìm thấy |
| `public.schema_migrations`, version `0007` | Registry có, **version 0007 không có** |
| `users.id` integer PK | Có |
| `users.cognito_sub` nullable + UNIQUE | Có |
| `users.email` UNIQUE | Có |
| `users.password_hash` nullable VARCHAR(255) | Có |
| `users.role` CHECK STUDENT/INSTRUCTOR/ADMIN | Có |

Schema users hiện có đáp ứng các prerequisite trực tiếp của 0007. Role audit có CONNECT, public USAGE/CREATE, REFERENCES trên users, SELECT/INSERT trên registry theo privilege checks. Đây là kiểm tra quyền, **không phải phê duyệt sử dụng quyền ghi**; quyền SELECT/INSERT/UPDATE cần được operator kiểm tra lại trên các bảng mới sau migration.

File cần review: `database/migrations/0007_dual_auth.sql`.

SHA-256 tại thời điểm audit:

```text
33281F2915D27B86A057A7E1A9F25486FE3F9D802F133B274179A64D40761169
```

File có BEGIN/COMMIT, thêm ba bảng, foreign key tới users, index session và ghi version 0007 trong cùng transaction. Không sửa/backfill users, không chuyển provider/role, không gửi email. Các tên bảng trong file không schema-qualified, vì vậy operator phải cố định `search_path=public` khi áp dụng.

### 4.2. Registry hiện có

Các ngày bên dưới là timestamp UTC được PostgreSQL trả về:

| Version | Description thực tế | Applied at |
|---|---|---|
| `0001` | Create LearnCloud core schema | 2026-10-28 07:48:06.266922+00 |
| `0002` | Add flashcards, approval state, role and tutor-session integrity checks | 2026-10-28 07:48:06.271201+00 |
| `0004` | Allow APPROVED Lesson status for explicit review before course publishing | 2026-10-30 09:35:39.728368+00 |
| `0005` | Add video upload intents and pipeline ledger with upload/lesson integrity | 2026-10-31 09:46:16.072167+00 |
| `0006` | Course cover and resumable remediation workflow | 2026-11-09 10:18:58.910483+00 |

Không có `0003` hoặc `0007`. **Không có record 0003 không đủ chứng minh thiếu DDL 0003:** các trường tương ứng đã tồn tại, gồm password_hash, timestamps courses/sections/lessons, duration_seconds, retry_count, error_message. Không đề nghị tự ghi bổ sung registry hoặc chạy lại file này.

Đối chiếu thêm:

- `0006`: `courses.cover_image` và `tutor_sessions.workflow_state` đều có.
- `0005`: `video_uploads`, `video_pipeline_runs` có. Chưa audit toàn bộ constraint của pipeline.
- `V1__add_password_hash_to_users.sql`: password_hash đã có, không cần tạo lại chỉ vì tên migration khác.
- `V2__allow_approved_lesson_status.sql`: CHECK hiện tại có APPROVED.
- `V3__add_tutor_remediation_fields.sql`: **chưa có** `tutor_sessions.practice_questions`, `tutor_sessions.remediation_completed` trong schema được kiểm tra.

### 4.3. Xung đột version 0004

Repository có bốn file khác nghiệp vụ cùng ghi version `0004`:

1. `0004_add_lesson_approved_status.sql`.
2. `0004_remove_approved_lesson_status.sql`.
3. `0004_cognito_auth_cutover.sql`.
4. `0004_checkpoint_attempt_idempotency.sql`.

Registry chỉ có một primary key theo version. Nhiều file dùng `ON CONFLICT DO NOTHING`, nên một record `0004` không chứng minh cả bốn thay đổi đã được áp dụng.

Kết quả thực tế:

- Record `0004` đang mô tả **thêm APPROVED**; `ck_lessons_status` validated và vẫn cho phép APPROVED. Không có bằng chứng schema đang ở trạng thái của file remove-APPROVED.
- password_hash đã nullable, phù hợp hiệu ứng của Cognito cutover; không thể xác định lịch sử thực thi file chỉ từ thuộc tính này.
- Thiếu `quiz_attempts.request_id`, `quiz_attempts.request_hash`, bảng `checkpoint_remediation` và index `uq_quiz_attempts_request`: **cấu trúc checkpoint-idempotency chưa có**.
- File `0005_video_pipeline_ledger.sql` hiện tại yêu cầu record 0004 remove-APPROVED và CHECK không còn APPROVED. RDS có record 0005 nhưng **không đáp ứng guard đó tại thời điểm audit**. Có sự lệch giữa source migration hiện tại và lịch sử/schema; chưa xác định nguyên nhân là phiên bản file cũ hay thay đổi về sau.

Đây là các vấn đề cần review riêng, không phải lý do để replay 0004/0005. Đặc biệt file remove-APPROVED có UPDATE lessons; audit không chạy file này. Migration 0007 chỉ phụ thuộc trực tiếp users/registry; không yêu cầu sửa checkpoint hoặc trạng thái lesson để chữa lỗi đăng ký hiện tại.

## 5. Nguyên nhân chính xác của HTTP 500

Đã tái hiện **chỉ bằng truy vấn đọc**, không gửi lại API đăng ký:

```sql
SELECT 1 FROM local_auth_otps LIMIT 0;
```

Kết quả: SQLAlchemy **ProgrammingError**, psycopg2 **UndefinedTable**, SQLSTATE **42P01**. Connection được rollback/đóng ngay sau lỗi.

Đối chiếu source:

1. `POST /auth/local/register` gọi `local_auth_service.register`.
2. Service kiểm tra email, tạo User trong transaction và `db.flush()`; chưa COMMIT.
3. `db.add(LocalIdentity(...))` chỉ xếp metadata vào session; SessionLocal đặt `autoflush=False`.
4. `_issue_otp` chạy SELECT trên `local_auth_otps` để kiểm cooldown/mã cũ. Đây là lần dùng bảng local-auth được truy vấn trước khi metadata identity được flush, nên lỗi nêu **otps**, dù thực tế cả ba bảng đều thiếu.
5. Lỗi UndefinedTable không phải IntegrityError/LocalAuthError/InvalidToken được các lớp này xử lý. Nó đi tới generic exception handler và trở thành HTTP 500.
6. SMTP và COMMIT ở sau câu SELECT này, nên chưa tới bước gửi email. Session đóng khi request kết thúc sẽ rollback transaction chưa commit; không thể kết luận có user đã commit chỉ dựa vào ID/sequence từng được cấp trong request lỗi.

**Nguyên nhân là schema RDS chưa có migration 0007, không phải công tắc auth, JWT secret, SMTP hay PostgreSQL local.** Không sửa code để chữa hoặc che lỗi thiếu migration. Không xác nhận lại request HTTP đang chạy vì không có FastAPI trên 8000 và gọi register sẽ có nguy cơ ghi dữ liệu.

## 6. Quy trình khắc phục đề xuất — chỉ để nhóm review/phê duyệt

**Không có lệnh thay đổi nào dưới đây được thực thi trong audit.** Không tự tạo bảng rời rạc hoặc copy SQL CREATE TABLE vào RDS. Nhóm phải quyết định đúng môi trường, backup và phê duyệt trước khi operator thực hiện.

### 6.1. Điều kiện trước migration

1. Chủ sở hữu xác nhận endpoint/database và môi trường được phép. Nếu đây là production, không dùng local authentication development/test trên đích này; việc cho phép schema bổ sung và chọn môi trường thử phải được review riêng.
2. Tạm dừng các request đăng ký/reset local trong maintenance window đã thống nhất; không thay Cognito guards. Kiểm tra lại tunnel còn sống và danh tính SQL như phần 3.
3. Review file/hash 0007 với nhánh code triển khai. Không dùng wildcard hoặc “chạy tất cả migrations”. Không sửa version 0004 hoặc registry để ép migration pass.
4. Xác nhận `public.users`, PK integer, nullable password_hash, `public.schema_migrations` tồn tại và user triển khai có quyền cần thiết.
5. Kiểm tra lại **cả ba bảng và version 0007 đều chưa có**. Nếu có schema một phần, version trùng hoặc bảng khác cấu trúc: dừng và phân tích, không trông cậy `IF NOT EXISTS`/`ON CONFLICT DO NOTHING` sẽ tự sửa đúng.
6. Cố định search_path public, đặt lock/statement timeout và đánh giá blocking transaction. Foreign key DDL có thể giữ lock trên users; chọn thời gian phù hợp dữ liệu đang hoạt động.
7. Chuẩn bị bản backup đã kiểm tra khả năng restore trên môi trường tách biệt.

Preflight read-only có thể chạy lại bằng SQL client được nhóm cấp quyền:

```sql
BEGIN READ ONLY;
SELECT current_database(), current_user, inet_server_addr(), inet_server_port();
SELECT current_schema(), current_setting('search_path'),
       current_setting('transaction_read_only');
SELECT to_regclass('public.users'), to_regclass('public.schema_migrations'),
       to_regclass('public.local_auth_identities'),
       to_regclass('public.local_auth_otps'),
       to_regclass('public.local_auth_sessions');
SELECT version, description FROM public.schema_migrations
WHERE version IN ('0003','0004','0005','0006','0007') ORDER BY version;
ROLLBACK;
```

### 6.2. Backup đề xuất

- AWS owner tạo **manual RDS snapshot** trước thay đổi, đợi trạng thái available và ghi lại mốc backup. Đây là tác vụ AWS thay đổi trạng thái, **không được agent thực hiện** trong công việc này. Có thể dùng snapshot mới có sẵn nếu đáp ứng chính sách/mốc phục hồi của nhóm.
- DBA có thể chuẩn bị thêm logical backup `pg_dump` định dạng custom và schema/grants trước thay đổi; lưu ở nơi kiểm soát truy cập/mã hóa. Audit không dump dữ liệu hoặc tạo file backup chứa thông tin người dùng.
- Xác nhận retention, cửa sổ PITR nếu có, RPO/RTO và thực hành restore trên instance/DB cách ly. Restore snapshot tạo **DB instance mới**, không ghi đè trực tiếp instance hiện tại; chuyển endpoint/ứng dụng là bước riêng cần phê duyệt. [AWS: restore từ snapshot](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_RestoreFromSnapshot.html)

### 6.3. Operator áp dụng đúng một file sau phê duyệt

Ví dụ Windows PowerShell, tại repository root, cho operator đã được giao nhiệm vụ; **không phải yêu cầu chạy ngay**:

```powershell
Get-FileHash database/migrations/0007_dual_auth.sql -Algorithm SHA256

& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' `
  --dbname="host=127.0.0.1 port=15437 dbname=learncloud user=learncloud_admin sslmode=require connect_timeout=5 options='-c search_path=public -c lock_timeout=5s -c statement_timeout=60s'" `
  --no-psqlrc --password --set=ON_ERROR_STOP=1 `
  --file=database/migrations/0007_dual_auth.sql

if ($LASTEXITCODE -ne 0) { throw 'Migration failed; review the error and transaction state before retrying.' }
```

`--password` nhập password qua prompt; không đặt password trong command line/history. Điều chỉnh đường dẫn psql nếu nhóm dùng bản khác. Không sửa DATABASE_URL hoặc JWT/AWS settings. File đã có BEGIN/COMMIT; không bọc bằng transaction ngoài hoặc `--single-transaction`. Nếu thao tác interactive và có lỗi trong transaction, operator ROLLBACK; với psql ON_ERROR_STOP thoát trước COMMIT, connection đóng sẽ rollback transaction chưa commit. Không tự retry khi lock timeout hoặc lỗi cấu trúc.

### 6.4. Điều kiện sau migration

- Ba bảng nằm đúng schema public, đủ cột và kiểu, PK/FK/check/index đúng file; không chỉ kiểm tên bảng.
- `schema_migrations` có **0007** với description `Opt-in development/test local auth, hashed email OTP and revocable sessions`.
- Runtime DB role có SELECT/INSERT/UPDATE/DELETE phù hợp trên bảng local mới; default privilege hoặc migration-owner khác user ứng dụng có thể cần DBA review GRANT riêng. Không tự cấp quyền trong audit.
- users/roles/Cognito identities không bị migration sửa. Không tạo tài khoản giả để “xác nhận schema”.
- Sau khi đúng môi trường development/test được phép ghi dữ liệu, khởi động FastAPI bằng cấu hình hiện có; xác minh `/health`, Frontend vẫn `VITE_USE_MOCK=false`, `VITE_USE_AUTH_MOCK=true`.
- Mailpit giữ SMTP `localhost:1025`, UI `http://localhost:8025`; nếu Backend ở máy/container khác, nhóm phải kiểm tra khả năng tiếp cận SMTP từ chính runtime đó. Audit hiện xác nhận SMTP từ Windows host.
- Chỉ sau phê duyệt test ghi: nhóm đăng ký Student bằng email mới, kỳ vọng HTTP 201 và verification_required, đọc OTP trong Mailpit, verify, login và thử resend theo cooldown. Không đưa OTP vào log/report/API response. Cognito vẫn dùng email verification riêng.

### 6.5. Rollback

- **Trước COMMIT:** lỗi DDL/registry trong transaction thì ROLLBACK, không giữ schema một phần do file này tạo trong transaction thất bại.
- **Sau COMMIT, chưa dùng local auth:** ưu tiên rollback ứng dụng hoặc tạm dừng local auth theo kế hoạch của nhóm, giữ các bảng bổ sung. Không cần khôi phục cả RDS chỉ vì code chưa bật tính năng.
- **Sau khi đã có tài khoản/OTP/session:** không DROP bảng hoặc xóa version 0007 tự động; có thể mất dữ liệu/khả năng đăng nhập và làm schema lệch. Mọi down migration cần bản sao dữ liệu, kiểm tra dependency, được phê duyệt riêng. Không đưa lệnh DROP/DELETE vào kế hoạch chạy tự động.
- Nếu bắt buộc restore: restore snapshot/PITR sang instance cách ly, xác minh rồi nhóm quyết định chuyển lưu lượng. Có thể mất các ghi hợp lệ sau mốc backup nếu chuyển ngược; cần kế hoạch hòa giải dữ liệu và phê duyệt cấu hình endpoint. Audit không thực hiện các bước đó.

## 7. Phạm vi và các việc không thực hiện

Chỉ tạo file báo cáo này. Không chỉnh source, migration cũ, file `.env`, DATABASE_URL, JWT_SECRET_KEY, LOCAL_AUTH_JWT_SECRET hoặc cấu hình AWS. Không start/stop/restart Backend, Docker hoặc SSM Tunnel. Không chạy migration/DDL/DML, không đọc dữ liệu tài khoản/OTP, không tạo snapshot, không dump/restore database, không gửi email và không tạo tài khoản thử trên RDS.

Đã xác nhận trực tiếp: settings/engine của process audit, SSM process/listener, kết nối RDS/TLS/schema/registry bằng transaction read-only, SQLSTATE 42P01, trạng thái SMTP/UI Mailpit. Chưa xác nhận: environment riêng của Backend đã phát sinh lỗi, phân loại production của RDS, trạng thái backup/PITR AWS, quyền/grants trên bảng chưa tồn tại, hoặc đăng ký/nhận OTP thành công sau migration.

Tham khảo chính thức cho quy trình do nhóm thực hiện: [AWS SSM remote-host port forwarding](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-sessions-start.html#sessions-remote-port-forwarding), [RDS manual snapshot](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_CreateSnapshot.html), [RDS restore snapshot](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_RestoreFromSnapshot.html).
