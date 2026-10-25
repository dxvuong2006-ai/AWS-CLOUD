# API Contract

> **Mục đích:** Thỏa thuận giao tiếp giữa Frontend (React), Backend (FastAPI) và các module nghiệp vụ LearnCloud.
>
> **Trạng thái tài liệu:** `DRAFT — CHƯA CHỐT`. Có thể bổ sung, sửa hoặc loại bỏ API sau khi nhóm đối chiếu UI, code, database và nhu cầu tích hợp AWS.
>
> **Căn cứ:** (1) 24 endpoint gốc từ API Contract/MVP 4 tuần v3; (2) UI Design Specification v2 gồm 14 màn hình; (3) kết quả thử nghiệm thực tế với `POST /lessons/{id}/upload-url`.
>
> **Quan trọng:** Có tên API trong tài liệu **không đồng nghĩa đã triển khai**. Không gắn nhãn *Implemented* cho endpoint chưa đối chiếu Swagger và test.

| Thuộc tính | Giá trị |
|---|---|
| Phiên bản | Draft v3 — 22/10/2026 |
| Local Backend | `http://127.0.0.1:8000` |
| Swagger / OpenAPI | `http://127.0.0.1:8000/docs` và `/openapi.json` |
| Định dạng dữ liệu | REST/JSON; upload file trực tiếp S3 bằng Presigned URL |
| Auth trên backend đã kiểm chứng trước patch | `X-Demo-User` (chỉ demo, **không an toàn để public**) |
| Phương án auth đang được chuẩn bị | JWT HS256 + PostgreSQL + Argon2id; **đã tạo bộ code riêng, chưa xác nhận merge vào repo đang chạy** |
| Auth endpoints được bổ sung | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| Hướng AWS lâu dài | Cognito còn là phương án kiến trúc khác, **chưa tích hợp** |

---

## 1. Quy ước chung

### 1.1. Phân loại, mức độ ưu tiên và trạng thái

- **GỐC:** Endpoint thuộc danh sách 24 endpoint API MVP ban đầu; giữ nguyên method, path, chức năng, vai trò, file và phân công theo kế hoạch v3.
- **ĐỀ XUẤT:** Endpoint được suy ra từ thiết kế UI, luồng upload/cloud hoặc nhu cầu backend; **phải được A/B/C/D thông qua** trước khi coi là contract chính thức.
- **CÓ ĐIỀU KIỆN:** Chỉ triển khai nếu chọn phương án nghiệp vụ/kiến trúc tương ứng. Ví dụ: `POST /auth/login` không bắt buộc nếu Cognito quản lý đăng nhập và FE gọi Cognito trực tiếp.
- **P0:** Cần để luồng MVP hoạt động đầy đủ; **P1:** cải thiện trải nghiệm và nghiệp vụ; **P2:** bổ sung khi còn thời gian.
- **Trạng thái triển khai:** `TBD` (chưa đối chiếu code), `Prepared` (đã có code bàn giao nhưng chưa nhập repo), `Implemented` (đã chạy và test trên repo đang dùng), `Partial`, `Planned`, `Deferred`. Các API trong bảng dưới đây **không mặc định là Implemented**.
- **Chủ sở hữu API bổ sung:** `Đề xuất` trong các bảng là phân công gợi ý, **chưa được coi là quyết định nhân sự/tuần**.

### 1.2. REST, định danh và phân trang

- Method, path công khai phải thống nhất. Trong tài liệu, `{id}` là ID của tài nguyên đang nói đến; code có thể dùng `{course_id}`, `{section_id}`, `{lesson_id}`.
- ID hiện tại trong dự án có thể là số nguyên. **Không tự đổi sang UUID** chỉ vì tài liệu kiến trúc v3 từng đề xuất UUID; thay đổi này cần migration và cập nhật contract.
- Dùng ISO 8601 UTC cho trường thời gian nếu endpoint trả timestamp.
- Không tự bổ sung wrapper `data`, `items` hoặc pagination vào API đang dùng nếu chưa thống nhất với FE.
- `GET` không có request body; `POST/PATCH/PUT` nhận JSON (trừ PUT trực tiếp lên S3).
- Query params `search`, `status`, `page`, `limit` trong ví dụ là **đề xuất**, chưa phải tính năng có sẵn.

### 1.3. Authentication và authorization

- **Trước khi ghép bản auth mới:** Backend đang được mô tả dùng `X-Demo-User: <user_id>` với user seed. Đây là cơ chế giả lập **không an toàn để triển khai public**.
- **Phương án đang chuẩn bị tích hợp:** Backend tự quản lý `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, dùng PostgreSQL + Argon2id + access token JWT HS256. Bộ code đã được chuẩn bị riêng, nhưng **chưa có xác nhận chạy trên repo PostgreSQL hiện tại**, vì vậy chưa đánh dấu `Implemented`.
- **Sau khi tích hợp JWT:** Các endpoint bảo vệ dùng `Authorization: Bearer <access_token>`; `X-Demo-User` **phải bị loại bỏ hoàn toàn khỏi đường xác thực**, không cho phép fallback/giả mạo ID.
- **Đăng ký tài khoản khác với enroll khóa học:** `/auth/register` tạo tài khoản **STUDENT**, trong khi `/courses/{id}/enroll` đưa Student vào một course cụ thể.
- Backend tự kiểm tra `role`, ownership của instructor, trạng thái course/lesson, enrollment và unlock. Frontend ẩn nút **không thay thế** authorization.
- Student chỉ truy cập nội dung đã publish và section/lesson được phép. Instructor chỉ sửa course/lesson mình sở hữu. Admin chỉ được dùng API quản trị theo policy đã thống nhất.
- **Cognito chưa được sử dụng** trong patch JWT tự quản; nếu chuyển sang Cognito cần thiết kế lại luồng auth, mapping danh tính và cân nhắc bỏ endpoint login/register nội bộ. Không coi hai hệ thống này là đồng thời đang chạy.

### 1.4. HTTP status và lỗi

| Mã | Ý nghĩa / khi sử dụng |
|---|---|
| `200 OK` | Thành công, trả dữ liệu |
| `201 Created` | Tạo tài nguyên thành công |
| `204 No Content` | Thành công, không trả body |
| `400 Bad Request` | Input không hợp lệ theo quy tắc nghiệp vụ |
| `401 Unauthorized` | Chưa xác thực / token sai |
| `403 Forbidden` | Không đủ quyền, chưa enroll, chưa unlock |
| `404 Not Found` | Không có tài nguyên hoặc cố tình không tiết lộ tài nguyên không sở hữu |
| `409 Conflict` | Trùng dữ liệu, sai trạng thái publish/upload/processing |
| `413 Content Too Large` | File vượt giới hạn (nếu áp dụng server-side) |
| `422 Unprocessable Entity` | Validation theo mặc định của FastAPI/Pydantic |
| `429 Too Many Requests` | Rate limit (nếu cấu hình) |
| `500 Internal Server Error` | Lỗi backend chưa xử lý |
| `502/503` | Lỗi phụ thuộc AWS/DB bên ngoài (tùy endpoint) |

Ví dụ lỗi đơn giản (`detail` có thể là chuỗi hoặc danh sách lỗi validation theo FastAPI):

```json
{"detail": "Lesson not found or not owned by instructor"}
```

### 1.5. Quy ước AWS/S3

- Backend cấp URL tạm thời; trình duyệt gửi video bằng `PUT` trực tiếp lên Amazon S3. **Không gửi nguyên video qua Lambda/FastAPI**.
- `upload_url` là thông tin nhạy cảm tạm thời: **không commit, không công khai, không đưa nguyên URL vào log**.
- S3 bucket private, Block Public Access; backend cấp quyền xem video dựa trên enrollment/unlock.
- Ưu tiên AWS Signature Version 4. `file_size` do client khai báo ở bước xin URL **chưa đảm bảo giới hạn dữ liệu upload thực tế**.
- Bước xác nhận upload phải kiểm tra object bằng S3 `HeadObject`, quyền sở hữu và object key đã được cấp; tránh xác nhận object tùy ý.

### 1.6. Tình trạng đối chiếu code tại thời điểm soạn Draft v3

| API/nhóm | Ghi nhận hiện có | Trạng thái tài liệu |
|---|---|---|
| `GET /health`, `GET /courses`, `GET /courses/{id}` | Từng chạy local/được frontend gọi trong cuộc trao đổi | `Observed previously` — kiểm tra lại bản repo mới trước khi chốt |
| `POST /lessons/{id}/upload-url` | Người dùng đã thử Presigned PUT và S3 thành công | `Observed previously` — chưa mặc định quy trình confirm hoàn thiện |
| N01 `GET /courses/{id}/sections`, N02 `GET /sections/{id}/lessons` | Người dùng cho biết đã thử tích hợp frontend và thấy giao diện; sau đó discard **các thay đổi frontend** | `Reported working` — kiểm tra Swagger/backend hiện tại và PR để chốt |
| N07, N08, N12 (`/auth/login`, `/auth/me`, `/auth/register`) | Có bộ code/migration/test bàn giao riêng; chưa có xác nhận đã nhập repo và test PostgreSQL | **`Prepared`** |
| Các endpoint còn lại | Chưa kiểm tra trực tiếp Swagger và code phiên bản hiện tại trong đợt soạn này | `TBD / Planned` theo owner |

Lưu ý: `Observed previously` và `Reported working` là mô tả mức độ bằng chứng, **không thay cho trạng thái `Implemented`** của nhóm sau khi CI/test và review PR.

---

## 2. Danh sách 24 endpoint MVP gốc (GIỮ NGUYÊN)

> Bảng này **giữ nguyên nội dung, method, path, role, file và người/tuần của kế hoạch v3**. `Trạng thái code` của từng endpoint chưa được rà soát trong đợt cập nhật này.

| # | Method + path | Chức năng | Vai trò | File | Người · Tuần |
|---:|---|---|---|---|---|
| 1 | `GET /health` | Kiểm tra backend | All | `api/health.py` | A · T1 |
| 2 | `GET /courses` | Danh sách course đã publish | Student | `api/courses.py` | D · T1 |
| 3 | `POST /courses` | Tạo course | Instructor | `api/courses.py` | D · T2 |
| 4 | `GET /courses/{id}` | Chi tiết/outline course | Student/Instructor | `api/courses.py` | D · T1 |
| 5 | `PATCH /courses/{id}` | Sửa metadata | Instructor | `api/courses.py` | D · T2 |
| 6 | `POST /courses/{id}/publish` | Publish course | Instructor | `api/courses.py` | D · T3 |
| 7 | `POST /courses/{id}/sections` | Tạo section | Instructor | `api/sections.py` | D · T2 |
| 8 | `POST /sections/{id}/lessons` | Tạo lesson | Instructor | `api/lessons.py` | D · T2 |
| 9 | `GET /lessons/{id}` | Lấy lesson có kiểm tra quyền/unlock | Student/Instructor | `api/lessons.py` | D · T2 |
| 10 | `POST /lessons/{id}/upload-url` | Cấp Presigned URL | Instructor | `api/uploads.py` | D · T2 |
| 11 | `GET /lessons/{id}/processing-status` | Xem pipeline status | Instructor | `api/lessons.py` | D · T3 |
| 12 | `POST /lessons/{id}/retry` | Retry job lỗi | Instructor/Admin | `api/lessons.py` | D · T3 |
| 13 | `GET /lessons/{id}/ai-content` | Lấy transcript/summary/concepts/quiz nháp | Instructor | `api/review.py` | C · T3 |
| 14 | `PATCH /lessons/{id}/ai-content` | Sửa nội dung AI | Instructor | `api/review.py` | C · T3 |
| 15 | `POST /lessons/{id}/approve` | Approve trước publish | Instructor | `api/review.py` | C · T3 |
| 16 | `POST /courses/{id}/enroll` | Đăng ký course | Student | `api/enrollments.py` | D · T2 |
| 17 | `PUT /lessons/{id}/progress` | Lưu tiến độ học | Student | `api/progress.py` | B · T2 |
| 18 | `GET /courses/{id}/progress` | Xem tiến độ | Student | `api/progress.py` | B · T2 |
| 19 | `GET /sections/{id}/quiz` | Lấy checkpoint đã duyệt và được mở | Student | `api/quizzes.py` | C · T2 |
| 20 | `POST /quizzes/{id}/attempts` | Nộp bài, backend chấm và lưu | Student | `api/quizzes.py` | C · T2 |
| 21 | `GET /students/me/quiz-history` | Lịch sử điểm | Student | `api/quizzes.py` | C · T2 |
| 22 | `POST /tutor/sessions` | Tạo remediation từ attempt chưa đạt | Student | `api/tutor.py` | C · T4 |
| 23 | `POST /tutor/sessions/{id}/messages` | Gửi câu hỏi tiếp theo | Student | `api/tutor.py` | C · T4 |
| 24 | `GET /instructor/courses/{id}/analytics` | Progress/pass-fail cơ bản | Instructor | `api/analytics.py` | C · T4 |

---

## 3. API bổ sung và backlog (DRAFT — CHƯA KHÓA)

> Các mã N01–N11 được giữ ổn định so với Draft v2. Bổ sung **N12 = `POST /auth/register`** (trước đây là ứng viên X13). Ba API auth N07/N08/N12 có **code chuẩn bị trong patch JWT**, nhưng chưa được xác nhận đã tích hợp vào backend đang chạy. Những API còn lại vẫn là đề xuất/ứng viên theo nhu cầu.

### 3.1. Nhóm N01–N12 (11 API cũ + đăng ký tài khoản)

| # | Method + path (đề xuất) | Chức năng | Vai trò | File gợi ý | Ưu tiên | Quyết định cần chốt |
|---:|---|---|---|---|---|---|
| N01 | `GET /courses/{id}/sections` | Liệt kê section theo `position` | Student/Instructor | `api/sections.py` | P0 | Bỏ nếu `GET /courses/{id}` đã trả đủ outline |
| N02 | `GET /sections/{id}/lessons` | Liệt kê lesson theo `position` | Student/Instructor | `api/lessons.py` | P0 | Bỏ nếu outline đã lồng đủ lessons |
| N03 | `GET /instructor/courses` | Khóa học của instructor, gồm DRAFT/PUBLISHED | Instructor | `api/courses.py` | P0 | Phân trang / filter `status` |
| N04 | `GET /students/me/courses` | Khóa học student đã enroll | Student | `api/enrollments.py` | P0 | Có trả tiến độ tóm tắt hay không |
| N05 | `GET /sections/{id}/flashcards` | Lấy flashcards được duyệt, được quyền học | Student | `api/flashcards.py` (mới) | P1 | Phạm vi flashcard; bảng DB/AI output chưa chốt |
| N06 | `POST /lessons/{id}/confirm-upload` | Xác nhận object tồn tại, gắn video với lesson | Instructor | `api/uploads.py` | P0 | Chốt upload session/key và cách kích hoạt pipeline |
| N07 | `POST /auth/login` | Đăng nhập email/password, cấp JWT | Guest | `api/auth.py` (mới) | P0 nếu chọn JWT | **Prepared**; không cần nếu chuyển Cognito login trực tiếp |
| N08 | `GET /auth/me` | Lấy user hiện tại và role từ JWT | Authenticated | `api/auth.py` (mới) | P0 nếu chọn JWT | **Prepared**; Bearer required |
| N09 | `GET /admin/users` | Danh sách/tìm kiếm/lọc user | Admin | `api/admin.py` (mới) | P2 | UI Admin có nằm trong MVP 4 tuần không |
| N10 | `PATCH /admin/users/{id}` | Sửa profile, role/trạng thái user | Admin | `api/admin.py` (mới) | P2 | Policy đổi role, audit và đồng bộ Cognito |
| N11 | `GET /admin/monitoring` | Tổng hợp trạng thái job/lỗi/chi phí | Admin | `api/admin.py` (mới) | P2 | Backend đọc được nguồn metrics/billing nào |
| N12 | `POST /auth/register` | Tự đăng ký Student bằng email/password | Guest | `api/auth.py` (mới) | P0 nếu chọn self-signup | **Prepared**; không cho tự đăng ký Instructor/Admin |

**Quy tắc riêng:** Nhóm đã chọn thử **phương án JWT tự quản lý** cho N07/N08/N12 và đã có code bàn giao. Đây là thay đổi đề xuất so với MVP v3 vốn chỉ dùng `X-Demo-User`. Chỉ cập nhật trạng thái `Implemented` và thông báo B sửa frontend **sau khi patch được merge, migration chạy, ba API xuất hiện trong Swagger và test PostgreSQL pass**. Nếu chuyển Cognito thì N07/N12 có thể bị thay thế.

### 3.2. Các API ứng viên khác (cân nhắc sau khi đối chiếu UI/Swagger)

| Mã | Method + path (đề xuất) | Mục đích | Vai trò | Ưu tiên | Điều kiện / khả năng gộp |
|---|---|---|---|---|---|
| X01 | `GET /lessons/{id}/video-url` | Presigned GET URL phát video S3 private | Student/Instructor | P0 | Không cần API riêng nếu `GET /lessons/{id}` đã trả URL có kiểm soát quyền |
| X02 | `GET /instructor/dashboard` | KPI và việc cần xử lý của instructor | Instructor | P1 | Có thể gộp từ analytics và course list |
| X03 | `GET /instructor/courses/{id}/students` | Danh sách học viên và tiến độ | Instructor | P1 | Có thể trả trong analytics nếu dữ liệu nhỏ |
| X04 | `GET /quizzes/attempts/{id}` | Chi tiết một lần làm, câu sai/điểm | Student | P1 | Chỉ cho chủ attempt xem |
| X05 | `PATCH /sections/{id}` | Sửa title/position section | Instructor | P1 | Quy tắc đảo thứ tự UNIQUE position |
| X06 | `DELETE /sections/{id}` | Xóa section | Instructor | P1 | Xác nhận cascading và bài đã có học viên |
| X07 | `PATCH /lessons/{id}` | Sửa title/position lesson | Instructor | P1 | Không phá trạng thái đã publish |
| X08 | `DELETE /lessons/{id}` | Xóa lesson | Instructor | P1 | Quy tắc xóa S3 object/job đang xử lý |
| X09 | `GET /admin/jobs` | Liệt kê execution/job | Admin | P2 | Có thể gộp vào `/admin/monitoring` |
| X10 | `POST /admin/jobs/{id}/retry` | Retry execution lỗi | Admin | P2 | Có thể tái sử dụng `POST /lessons/{id}/retry` |
| X11 | `POST /auth/forgot-password` | Quên mật khẩu | All | Có điều kiện | Chỉ nếu auth tự triển khai hoặc proxy auth provider |
| X12 | `POST /auth/logout` | Đăng xuất / revoke | Authenticated | Có điều kiện | Phụ thuộc session/JWT/Cognito |

**Chưa đưa các ứng viên X01–X12 vào MVP chính thức.** Khi chọn triển khai, chuyển chúng sang 3.1 hoặc danh sách đã chốt, rồi cập nhật bảng phân công và OpenAPI.

---

## 4. Hợp đồng request/response theo nhóm chức năng

**Quy tắc đọc:** Những ví dụ không có ghi chú “đã quan sát thực tế” là **đề xuất** để FE/BE thảo luận, không phải lời xác nhận rằng backend đang hỗ trợ.

### 4.1. Health

**`GET /health`** (GỐC)

Ví dụ **đã quan sát ở FastAPI local**:

```json
{"status": "ok"}
```

### 4.2. Course — danh mục, quản lý, publish

**`GET /courses`** (GỐC): Trả course PUBLISHED cho Student; nếu cho guest xem catalog thì nhóm cần sửa vai trò trong bảng gốc sau khi thống nhất. Cần chốt filter/search/pagination. Không trả DRAFT cho user không có quyền.

**`POST /courses`** (GỐC): Instructor tạo bản nháp (`DRAFT`) mặc định. Trường `status` do client truyền **không mặc nhiên cho phép tạo PUBLISHED**. Ví dụ request đề xuất:

```json
{
  "title": "Lập trình Python",
  "description": "Lập trình Python cơ bản",
  "learning_objectives": ["Biết cú pháp Python", "Viết được chương trình nhỏ"]
}
```

Response thành công thường `201 Created`, chứa `id`, `instructor_id`, `status: "DRAFT"` và các metadata có trong schema.

**`GET /courses/{id}`** (GỐC): Course detail/outline. **Cần quyết định** response có `sections[].lessons[]` không. Nếu đã có, cân nhắc không tạo N01/N02. Chỉ lộ nội dung theo quyền và trạng thái publish.

**`PATCH /courses/{id}`** (GỐC): Sửa metadata; chỉ chủ course được sửa; chưa mặc định cho sửa `status` bằng endpoint này.

**`POST /courses/{id}/publish`** (GỐC): Lệnh publish. Backend xác minh course thuộc instructor và thỏa tiêu chí xuất bản (ví dụ nội dung được duyệt, không có lesson bắt buộc đang lỗi); thiếu điều kiện trả `409`. Chưa quyết định body trả về là course mới hay trạng thái tối giản.

**`GET /instructor/courses`** (N03): Filter theo chính instructor đã xác thực; không lấy user ID của instructor từ frontend.

**`GET /students/me/courses`** (N04): Danh sách enrollment của student hiện tại, chỉ trả dữ liệu của chính user.

### 4.3. Section / Lesson / Outline

**`POST /courses/{id}/sections`** (GỐC) — Body đề xuất:

```json
{"title": "Giới thiệu", "position": 1}
```

**`POST /sections/{id}/lessons`** (GỐC) — Body đề xuất:

```json
{"title": "Tổng quan Cloud", "position": 1}
```

**`GET /courses/{id}/sections`** (N01): Đề xuất trả mảng `[{"id":1,"course_id":1,"title":"Giới thiệu","position":1}]`, sắp xếp tăng theo `position`, không lộ section chưa publish trái quyền.

**`GET /sections/{id}/lessons`** (N02): Đề xuất trả `[{"id":1,"section_id":1,"title":"Tổng quan Cloud","position":1,"status":"PUBLISHED"}]`; FE dùng để hiển thị danh sách lesson và trạng thái unlock phù hợp. Với student, nên ẩn nội dung nhạy cảm của lesson chưa duyệt.

**`GET /lessons/{id}`** (GỐC): Backend kiểm tra enrollment/unlock, instructor ownership; có thể chứa `summary`, transcript, concept và URL xem video **chỉ khi các nội dung đã duyệt/được phép xem**. Chưa chốt liệu URL nằm trong response hay ở X01.

**`PATCH /sections/{id}`, `PATCH /lessons/{id}`** (X05/X07): Nếu triển khai phải xử lý xung đột vị trí và ownership.

### 4.4. S3 Upload và xử lý video

**`POST /lessons/{id}/upload-url`** (GỐC) — Ví dụ **khớp với code đã chạy và kiểm thử trong LearnCloud**:

Request:

```json
{
  "filename": "demo.mp4",
  "content_type": "video/mp4",
  "file_size": 1048576
}
```

Response minh họa **chỉ biểu diễn cấu trúc, không phải URL có thật**:

```json
{
  "upload_url": "<presigned-put-url>",
  "object_key": "lessons/1/raw/<random-id>.mp4",
  "expires_in": 900,
  "method": "PUT",
  "content_type": "video/mp4"
}
```

Sau đó client gửi `PUT <upload_url>` tới S3 với `Content-Type` khớp chữ ký. CORS bucket cần cho phép origin frontend. **Không upload video bằng POST tới FastAPI**.

**`POST /lessons/{id}/confirm-upload`** (N06) — ĐỀ XUẤT:

```json
{"object_key": "lessons/1/raw/<random-id>.mp4"}
```

Response đề xuất:

```json
{
  "lesson_id": 1,
  "object_key": "lessons/1/raw/<random-id>.mp4",
  "status": "UPLOADED",
  "size_bytes": 1048576
}
```

Quy tắc bắt buộc nếu xây API này:

1. Instructor đã được xác thực và sở hữu lesson.
2. `object_key` thuộc lesson **và** thuộc phiên upload đã được cấp hợp lệ (không chỉ kiểm tra prefix).
3. S3 `HeadObject` xác minh tồn tại/size/content-type metadata; metadata **không chứng minh** file MP4 có nội dung hợp lệ.
4. Cập nhật `lessons.raw_video_key`, trạng thái và thông tin job trong transaction phù hợp.
5. Phải thống nhất nguồn kích hoạt workflow: **S3 event** hoặc **confirm-upload**, và tránh trigger trùng khi cả hai tồn tại; thiết kế idempotency cho sự kiện giao hàng lặp.
6. Lỗi khi object chưa tồn tại/trạng thái sai/không thuộc lesson trả `404/409/403` theo chính sách đã chốt.

**`GET /lessons/{id}/processing-status`** (GỐC): Cần thống nhất enum trong DB; dự kiến các bước `UPLOADED`, `PROCESSING`, `TRANSCRIBING`, `AI_PROCESSING`, `REVIEW_REQUIRED`, `PUBLISHED`, `FAILED` (theo tài liệu kiến trúc). Có thể trả `current_step`, `last_error`, `updated_at` nếu có dữ liệu.

**`POST /lessons/{id}/retry`** (GỐC): Chỉ cho retry trạng thái `FAILED` và khi user đủ quyền. Không tạo nhiều job đồng thời; log số lần thử và nguyên nhân.

**`GET /lessons/{id}/video-url`** (X01): ĐỀ XUẤT nếu tách riêng — cấp Presigned GET URL sau khi kiểm tra enrollment, unlock, publish; không trả S3 public URL. Nếu phát HLS qua CloudFront sau này, contract có thể đổi sang playback manifest URL.

### 4.5. AI Content Review

- `GET /lessons/{id}/ai-content` (GỐC): Instructor lấy bản nháp transcript có timestamp, summary, concepts, quiz; không trả dữ liệu nháp cho student.
- `PATCH /lessons/{id}/ai-content` (GỐC): Sửa các trường review được cho phép; mọi field phải theo schema do C chốt.
- `POST /lessons/{id}/approve` (GỐC): Chỉ approve khi nội dung đạt kiểm tra. **Chưa thống nhất** approve có tự publish lesson hay không; cần quyết định trước khi FE tích hợp.

### 4.6. Enrollment và progress

- `POST /courses/{id}/enroll` (GỐC): Student enroll course đã PUBLISHED. Backend lấy student ID từ auth, không nhận `student_id` tự chọn. Đăng ký trùng: thống nhất `409` hoặc idempotent `200`.
- `GET /students/me/courses` (N04): Chỉ enrollment của student hiện tại, có thể kèm `progress_percent` nếu BE/B đồng ý.
- `PUT /lessons/{id}/progress` (GỐC): Theo mô hình dữ liệu v3, ưu tiên `watched_seconds`, `completed`; **request cụ thể phải chốt với B**. Ví dụ đề xuất:

```json
{"watched_seconds": 120, "completed": false}
```

- `GET /courses/{id}/progress` (GỐC): Chỉ trả tiến độ của student hiện tại. Backend kiểm tra enrollment.

### 4.7. Flashcard, Quiz, Unlock

**`GET /sections/{id}/flashcards`** (N05): ĐỀ XUẤT; chỉ trả nội dung đã approve và được phép truy cập. Cần xác định flashcard gắn `section_id` hay `lesson_id`, bổ sung model/migration hoặc xác định nguồn JSONB trước khi chốt API. Response ví dụ:

```json
{
  "section_id": 1,
  "flashcards": [
    {"id": 11, "front": "IaaS là gì?", "back": "Hạ tầng dưới dạng dịch vụ"}
  ]
}
```

**`GET /sections/{id}/quiz`** (GỐC): Chỉ checkpoint được approve, được mở; **không trả `correct_answer`** trước khi submit.

**`POST /quizzes/{id}/attempts`** (GỐC): Student gửi lựa chọn, backend tự chấm và lưu attempt. Ví dụ request **đề xuất**:

```json
{"answers": [{"question_id": 1, "selected_option_id": 2}]}
```

Response cần chốt `score`, `passed`, `attempt_number`, unlock section tiếp theo. Ngưỡng đạt theo kế hoạch: `>= 80%`.

**`GET /students/me/quiz-history`** (GỐC): Lấy các attempt của student hiện tại.

**`GET /quizzes/attempts/{id}`** (X04): ĐỀ XUẤT nếu trang kết quả cần chi tiết khái niệm/câu sai; cần quyết định thời điểm được thấy đáp án đúng theo nghiệp vụ.

### 4.8. Tutor, Instructor Analytics

- `POST /tutor/sessions` (GỐC): Tạo phiên ôn tập từ attempt chưa đạt của chính student.
- `POST /tutor/sessions/{id}/messages` (GỐC): Student gửi câu hỏi cho Tutor trong session mình sở hữu. Ví dụ request đề xuất: `{"message":"Giải thích lại IaaS"}`.
- `GET /instructor/courses/{id}/analytics` (GỐC): Instructor sở hữu course xem enrollment/progress/pass-fail; định nghĩa chỉ số thực với C.
- `GET /instructor/dashboard` (X02), `GET /instructor/courses/{id}/students` (X03): Chỉ tạo nếu API analytics/course có sẵn không đủ dữ liệu UI.

### 4.9. Authentication — N07, N08, N12 (PATCH JWT ĐÃ CHUẨN BỊ, CHƯA XÁC NHẬN TÍCH HỢP)

**Phạm vi bản thử nghiệm:** Tài khoản được quản lý trong PostgreSQL; mật khẩu lưu `password_hash` bằng **Argon2id**; access token dùng **JWT ký HS256**, không phải Cognito. Thư mục bàn giao gồm `api/auth.py`, `schemas/auth.py`, `services/auth_service.py`, `repositories/auth_repo.py`, migration và test. **Status: `Prepared`, không phải `Implemented`.**

#### N12 — `POST /auth/register`

- **Role gọi:** Guest/All; không cần access token.
- **Ý nghĩa:** Tạo tài khoản học viên mới, không phải đăng ký vào khóa học.
- **Content-Type:** `application/json`.
- **Request (schema patch):** `name` từ 1–100 ký tự sau khi trim; `email` đúng định dạng; `password` 8–128 ký tự. Payload không chấp nhận trường lạ (`extra="forbid"`).

```json
{
  "name": "Nguyen Van A",
  "email": "student@example.com",
  "password": "StrongPassword123"
}
```

- **Response `201 Created`** (minh họa cấu trúc, không phải dữ liệu DB thực):

```json
{
  "id": 4,
  "name": "Nguyen Van A",
  "email": "student@example.com",
  "role": "STUDENT",
  "created_at": "2026-10-22T04:00:00Z"
}
```

- **Lỗi chính:** `409` email đã tồn tại; `422` body không hợp lệ.
- **Quy tắc:** `role` luôn là `STUDENT` do server gán. Không nhận role từ client; email được chuẩn hóa về chữ thường. Instructor/Admin phải do thao tác tin cậy của người quản trị cấp quyền. **Không trả password/hash** trong JSON.

#### N07 — `POST /auth/login`

- **Role gọi:** Guest/All; không cần access token.
- **Request (schema patch):**

```json
{
  "email": "student@example.com",
  "password": "StrongPassword123"
}
```

- **Response `200 OK`** (ví dụ minh họa):

```json
{
  "access_token": "<jwt-access-token>",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": 4,
    "name": "Nguyen Van A",
    "email": "student@example.com",
    "role": "STUDENT",
    "created_at": "2026-10-22T04:00:00Z"
  }
}
```

- **Lỗi chính:** `401` email/mật khẩu sai (thông báo chung, không tiết lộ email tồn tại), `422` body sai định dạng.
- **JWT dự kiến theo patch:** HS256; claims `sub` (user ID), `iss=learncloud`, `aud=learncloud-api`, `iat`, `exp`; thời hạn mặc định **60 phút** qua cấu hình. Không đưa password/hash/role do client tự khai báo vào token.

#### N08 — `GET /auth/me`

- **Role gọi:** User đã đăng nhập.
- **Header bắt buộc:** `Authorization: Bearer <access_token>`.
- **Response `200 OK`:** Cùng cấu trúc `UserResponse` như trường `user` của login (không chứa password, password_hash hoặc token).
- **Lỗi chính:** `401` thiếu, sai hoặc hết hạn token.
- **Quy tắc:** Backend kiểm tra chữ ký, issuer, audience, các claims bắt buộc; lấy user từ PostgreSQL theo `sub` và kiểm tra role thực tế từ DB.

#### Tương thích dự án và bảo mật

- **Chuyển đổi có ảnh hưởng toàn hệ thống:** Sau khi thay `dependencies.get_current_user`, các API bảo vệ cũ cũng phải nhận Bearer JWT; không tiếp tục chấp nhận `X-Demo-User` làm fallback. Thành viên B phải chỉnh `frontend/src/api/client.js` / `AuthContext`.
- **Migration bắt buộc:** thêm `users.password_hash VARCHAR(255) NULL`. Giữ dữ liệu user seed hiện có; user seed có `password_hash=NULL` không thể login đến khi người có quyền đặt mật khẩu bằng script CLI tin cậy.
- **Tương thích cột cũ:** Patch hiện tạo `cognito_sub="local:<uuid>"` cho tài khoản local vì schema hiện vẫn có `cognito_sub NOT NULL`. Đây là định danh local tạm thời, **không phải Cognito sub thật**; cần migration/schema thống nhất về sau.
- **Cấu hình:** `.env` cần `JWT_SECRET_KEY` đủ mạnh và `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`; không commit secret. Chỉ chạy qua HTTPS khi đưa lên môi trường công khai.
- **Chưa triển khai trong patch:** refresh token, endpoint revoke/logout server-side, reset password, email verification, MFA, Cognito. Nếu logout ở frontend bằng cách xóa token, token đã phát hành vẫn còn hiệu lực đến khi hết hạn.
- **Tăng cường trước khi public:** rate limiting cho login/register, chính sách mật khẩu, bảo vệ chống brute force, quản lý secret/rotation và audit. Tùy ngân sách, có thể chọn Cognito thay cho auth tự quản lý.

#### Điều kiện để đổi status từ `Prepared` sang `Implemented`

1. Ghép code vào repo đang dùng mà không ghi đè `main.py`, router và cấu hình hiện tại.
2. Chạy migration `password_hash` trên PostgreSQL Docker và cài thư viện JWT/Argon2/email-validator.
3. Test Swagger: register `201`, trùng email `409`, login `200`, sai password `401`, `/me` `200`/`401`.
4. Test phân quyền Student không thể `POST /courses` (`403`), Instructor seed đăng nhập hợp lệ; kiểm tra `X-Demo-User` không bypass JWT.
5. FE/B xác nhận header Bearer sau khi backend thay auth; cập nhật tài liệu và PR.

### 4.10. Admin và Monitoring (ĐỀ XUẤT, phạm vi UI mở rộng)

- `GET /admin/users` (N09): Admin liệt kê, tìm kiếm, lọc role/status; dữ liệu phải được giới hạn và phân trang.
- `PATCH /admin/users/{id}` (N10): Quyền sửa role/status phải tách khỏi profile thông thường; cân nhắc audit log và đồng bộ identity provider.
- `GET /admin/monitoring` (N11): Tổng hợp job trạng thái/lỗi và cảnh báo. AWS Billing/CloudWatch có quyền truy cập riêng; không mặc định backend hiện tại đọc được số liệu chi phí.
- `GET /admin/jobs` (X09) và `POST /admin/jobs/{id}/retry` (X10): Chỉ bổ sung nếu monitoring tổng hợp/lesson retry không đủ.

---

## 5. Các quyết định cần nhóm chốt trước khi code thêm

| Mã | Câu hỏi / quyết định | Ảnh hưởng |
|---|---|---|
| D01 | `GET /courses/{id}` đã bao gồm outline sections/lessons hay chưa? | Tránh trùng N01/N02 |
| D02 | Student xem course chưa enroll tới mức nào? | Quy tắc 401/403 và course detail |
| D03 | Video playback URL lấy riêng hay nằm trong lesson detail? | X01 / bảo mật S3 |
| D04 | `confirm-upload` lưu phiên upload bằng bảng mới hay trạng thái khác? | N06, migration DB, trigger pipeline |
| D05 | Pipeline kích hoạt từ S3 EventBridge hay xác nhận upload? | Tránh xử lý trùng/job orphan |
| D06 | Flashcard gắn lesson hay section, lưu ở đâu? | N05, AI schema, database |
| D07 | Chốt áp dụng patch JWT local hay chuyển Cognito; thời điểm bỏ `X-Demo-User`? | N07/N08/N12, migration, FE token, tất cả API có bảo vệ |
| D08 | Admin UI 2 màn hình có nằm trong MVP 4 tuần không? | N09–N11 / phân công |
| D09 | Status/enum publish và approve là gì? | Nghiệp vụ lesson/course |
| D10 | Ai chịu trách nhiệm các endpoint **mới**, triển khai tuần nào? | Lộ trình A/B/C/D |
| D11 | Request/response quiz/progress có trùng schema code hiện tại không? | Tránh FE/BE lỗi 422 |
| D12 | Có cần phân trang, tìm kiếm, lọc cho Course/Admin? | Query params và kết quả trả về |

---

## 6. Đối chiếu với UI và lộ trình

| Nhu cầu UI / Cloud | Endpoint | Căn cứ | Ghi chú |
|---|---|---|---|
| Instructor xem course DRAFT/PUBLISHED | N03 | UI v2 trang 6 | Không thể dùng catalog chỉ PUBLISHED |
| Form course + outline | API course gốc + N01/N02 | UI v2 trang 7 | Kiểm tra outline hiện tại trước |
| Upload video và trạng thái | API upload gốc + N06 + status gốc | UI v2 trang 8; AWS tuần 2–3 | Workflow chạy không đồng bộ |
| Student xem video, transcript | Lesson gốc + X01 tùy chọn | UI v2 trang 12 | Chỉ nội dung approved/unlocked |
| Student flashcard | N05 | UI v2 trang 13 | Cần bổ sung nguồn dữ liệu |
| Student các course đã enroll | N04 | UI v2 trang 11–15 | Theo danh tính hiện tại |
| Login, đăng ký, role redirect | N12 + N07 + N08 (JWT patch `Prepared`) | UI v2 trang 4 có Login; Register là mở rộng | FE gửi Bearer JWT sau khi backend tích hợp; chưa dùng Cognito |
| Admin users/monitoring | N09–N11 | UI v2 trang 16–17 | Phạm vi vượt contract MVP 4 tuần hiện tại |
| AWS workflow monitoring/retry | Status/retry gốc; X09/X10 tùy chọn | Kiến trúc v3 tuần 3–4 | CloudWatch/Step Functions |

---

## 7. Quy trình thay đổi contract

1. FE/BE nêu nhu cầu bổ sung endpoint hoặc field qua issue/PR.
2. Đối chiếu **UI v2**, **kiến trúc v3**, **Swagger `/openapi.json`**, database schema và API hiện có để tránh trùng.
3. Tạo proposal nêu method/path, người dùng, request/response, quyền, lỗi, thay đổi schema, tác động FE/Cloud và ưu tiên.
4. A + module owner (B/C/D) duyệt, phân công và cập nhật phần contract **đã chốt**; proposal chưa duyệt vẫn ở phần 3.
5. Người phụ trách code, viết test và đối chiếu response thực với contract.
6. Chỉ ghi `Implemented` sau khi có bằng chứng chạy/test. Nếu đổi endpoint/response FE đang dùng, cập nhật contract **trước** khi merge và thông báo nhóm.
7. Nếu API không còn cần, ghi `Deferred/Rejected` cùng lý do thay vì âm thầm xóa lịch sử.

**Mẫu ghi nhận thay đổi:**

| Ngày | API / field | Thay đổi | Người đề xuất | Trạng thái | PR/Issue |
|---|---|---|---|---|---|
| 2026-10-22 | Contract Draft v2 | Giữ 24 API gốc, đề xuất thêm 11 API và danh sách tùy chọn | Dự thảo để nhóm xem xét | Draft | Chưa có |
| 2026-10-22 | Contract Draft v3 | Bổ sung N12 register; cập nhật N07/N08 theo patch JWT; giữ 24 API gốc, 12 API N và 12 API X; thêm checklist migration/test | Bản chỉnh sửa để nhóm review | Draft | Patch auth đã bàn giao, chưa xác nhận merge |

---

## 8. Checklist rà soát và chốt API cho giai đoạn tiếp theo

- [ ] Đối chiếu **24 API gốc** với Swagger; đánh dấu từng endpoint: Implemented / Partial / Planned.
- [ ] Chốt N01/N02 sau khi kiểm tra `GET /courses/{id}`.
- [ ] Chốt N03/N04 và dữ liệu phục vụ màn hình course của Instructor/Student.
- [ ] Chốt N06 (`confirm-upload`) và chiến lược chống event trùng.
- [ ] Chốt playback S3 private (lesson detail hay X01).
- [ ] Quyết định có làm Flashcard (N05) và lưu cấu trúc dữ liệu thế nào.
- [ ] Chốt JWT local hay Cognito; rà N07/N08/N12 và chọn thời điểm thay `X-Demo-User`.
- [ ] Nếu chọn JWT: ghép patch an toàn, chạy migration `password_hash`, đặt `JWT_SECRET_KEY`, test Swagger/register/login/me trên PostgreSQL.
- [ ] Kiểm thử vai trò STUDENT/INSTRUCTOR và loại bỏ khả năng bypass bằng `X-Demo-User`; phối hợp B gửi Bearer token.
- [ ] Xác nhận các API Admin là phạm vi MVP hay backlog.
- [ ] Chốt request/response của Progress, Quiz, AI Review, Tutor và trạng thái workflow.
- [ ] Xác nhận mã lỗi, chính sách quyền, không để bypass bằng gọi API trực tiếp.
- [ ] Gán người/tuần cho API mới sau khi nhóm duyệt.
- [ ] Tạo/cập nhật OpenAPI và test theo contract trước khi FE tích hợp.

**Ghi chú cuối:** Đây là **bản dự thảo có thể tiếp tục bổ sung**. Tên đường dẫn, vai trò và schemas của các API *đề xuất* không trở thành yêu cầu chính thức trước khi cả nhóm thống nhất. Khi triển khai xong từng chức năng, cập nhật lại trạng thái và ví dụ theo JSON thực tế.
