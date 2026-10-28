# LearnCloud — API Contract (Bản dự thảo v4)

> **Mục đích:** Thỏa thuận giao tiếp giữa Frontend (React), Backend (FastAPI) và các module nghiệp vụ LearnCloud.
>
> **Trạng thái tài liệu:** `DRAFT — CHƯA CHỐT`. Có thể bổ sung, sửa hoặc loại bỏ API sau khi nhóm đối chiếu UI, code, database và nhu cầu tích hợp AWS.
>
> **Căn cứ:** (1) 24 endpoint MVP gốc và API Contract Draft v3 (22/10/2026); (2) UI Design Specification v2; (3) sơ đồ database LearnCloud mới do nhóm trưởng cung cấp ngày 28/10/2026; (4) báo cáo Codex đọc source frontend/backend ngày 28/10/2026; (5) các thử nghiệm S3/Swagger được người dùng ghi nhận. **Chưa đối chiếu trực tiếp PostgreSQL/schema.sql và OpenAPI đang chạy ở thời điểm soạn v4.**
>
> **Quan trọng:** Có tên API trong tài liệu **không đồng nghĩa đã triển khai**. Không gắn nhãn *Implemented* cho endpoint chưa đối chiếu Swagger và test.

| Thuộc tính | Giá trị |
|---|---|
| Phiên bản | **Draft v4 — 28/10/2026** |
| Local Backend | `http://127.0.0.1:8000` |
| Swagger / OpenAPI | `http://127.0.0.1:8000/docs` và `/openapi.json` |
| Định dạng dữ liệu | REST/JSON; upload file trực tiếp S3 bằng Presigned URL |
| Auth qua dependency theo báo cáo source 28/10 | `X-Demo-User` (chỉ dùng local; **không an toàn để public**) |
| Auth hiện có theo báo cáo source | Có route `POST /auth/register`, `/auth/login`, `GET /auth/me`; **dependency hiện dùng demo, FE chưa có LoginPage hoạt động**. Chưa xác nhận luồng JWT end-to-end |
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
- Query params `search`, `status`, `page`, `limit` trong ví dụ là **đề xuất**, chưa phải tính năng có sẵn. Riêng `GET /sections/{id}/lessons` theo báo cáo code có `skip`, `limit`; phải giữ tương thích trước khi thay sang `page`.
- **Frontend route khác Backend API:** URL trang học `/courses/:courseId/lessons/:lessonId` là route React; nó có thể gọi `GET /courses/{courseId}` và `GET /lessons/{lessonId}` riêng. Không thêm `courseId` vào API Lesson chỉ để giống URL giao diện.
- **Quy ước tên trường đề xuất:** API JSON ưu tiên `snake_case` tương ứng schema; nếu FE hiện dùng `videoUrl`, `keyConcepts`, `progressPercent`, cần chuyển đổi ở `api/`/adapter FE hoặc chốt cách đặt tên thống nhất, không ngầm thay field ở production.

### 1.3. Authentication và authorization

- **Trước khi ghép bản auth mới:** Backend đang được mô tả dùng `X-Demo-User: <user_id>` với user seed. Đây là cơ chế giả lập **không an toàn để triển khai public**.
- **Tình hình 28/10 theo báo cáo đọc source:** Các route `POST /auth/register`, `POST /auth/login`, `GET /auth/me` đã có trong source backend; tuy nhiên dependency dùng ở API nghiệp vụ vẫn nhận `X-Demo-User`; frontend chưa có luồng LoginPage/AuthContext sử dụng được. **Không coi auth end-to-end là hoàn tất.**
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

### 1.6. Tình trạng đối chiếu code — cập nhật theo báo cáo ngày 28/10/2026

| API/nhóm | Bằng chứng hiện có | Nhận định v4 |
|---|---|---|
| `GET /health`, `GET /courses`, `GET /courses/{id}` | `GET /courses` trả HTTP 200 trong log 28/10; Codex xác nhận các route course trong source | `GET /courses`: **Observed 200**; API còn lại: **route trong source**, cần test trực tiếp |
| N01 `GET /courses/{id}/sections`, N02 `GET /sections/{id}/lessons` | Codex xác nhận có route và frontend đang gọi; `GET /sections/{id}/lessons` hỗ trợ `skip`, `limit` | **Source-confirmed**, chưa test browser với backend thật sau merge |
| `GET /lessons/{id}` | Codex đọc `LessonResponse` hiện gồm `id`, `section_id`, `title`, `position` | **Partial cho trang học video**: chưa có transcript/summary/playback |
| `GET /courses/{id}/progress`, `PUT /lessons/{id}/progress` | Codex thấy `api/progress.py` trống/chưa đăng ký; log thực tế trả 404 cho GET | **Missing route** theo source; không phải lỗi reset DB |
| `POST /lessons/{id}/upload-url` | Đã thử thành công bước lấy Presigned URL và PUT S3 trong trao đổi trước | **Observed previously**; xác nhận upload, video GET và pipeline chưa hoàn chỉnh |
| N07/N08/N12 (`/auth/login`, `/auth/me`, `/auth/register`) | Codex thấy các route tồn tại trong source; `get_current_user` nghiệp vụ vẫn dùng demo, FE LoginPage trống | **Source-confirmed routes, integration incomplete**, ưu tiên sau theo kế hoạch nhóm |
| Các endpoint khác | Chưa kiểm thử/đối chiếu Swagger đầy đủ trên bản merge hiện tại | `TBD / Planned` tùy endpoint; không tự gắn `Implemented` |

**Giới hạn bằng chứng:** Báo cáo Codex đã đọc source nhưng HTTP đến `localhost:8000` và `localhost:5173` timeout trong lượt đó. Không biến `source-confirmed` thành `runtime-tested`. Các bảng ở sơ đồ mới là **thiết kế**, phải so khớp với `database/schema.sql` được pull về trước khi khẳng định DB thật đã có cột.

### 1.7. Thay đổi cấu trúc dữ liệu theo sơ đồ mới (cần đối chiếu `schema.sql`)

| Bảng | Khác biệt chính so với SQL cũ | Tác động API |
|---|---|---|
| `users` | `name` tới 255, `email` tới 320; sơ đồ không thể hiện `password_hash` | Cần quyết định giữ local JWT hay Cognito; **không xóa field phục vụ auth khi chưa thống nhất** |
| `courses` | `learning_objectives JSONB NOT NULL` dạng array, thêm `created_at`, `updated_at` | Schema Create/Patch/Response phải xử lý mảng rỗng `[]`, timestamps |
| `sections` | Thêm `created_at`; hình không ghi UNIQUE `(course_id,position)` | Giữ ràng buộc cũ nếu không có quyết định thay đổi |
| `lessons` | `raw_video_key`, `processed_video_key` kiểu `TEXT`; thêm `duration_seconds`, `error_message`, `retry_count`, `created_at`, `updated_at`; `key_concepts_json` là array bắt buộc | Response Lesson, processing-status và pipeline cần đồng bộ; không lộ object key nội bộ cho student |
| `enrollments` | Cấu trúc gần như giữ nguyên | Không đổi endpoint enroll do thay schema |
| `lesson_progress` | Bảng mới: `student_id`, `lesson_id`, `watched_seconds`, `completed`, `updated_at`; unique student–lesson | Chốt body PUT và response GET Progress |
| `quizzes`, `questions`, `quiz_attempts` | Bảng mới; quiz thuộc section; câu hỏi thuộc quiz; attempt thuộc student/quiz | Chốt quiz payload, scoring, unlock; không đưa `correct_answer` cho student trước khi submit |
| `flashcards` | Bảng mới dùng **`lesson_id`**, `front`, `back`, `position`, `is_approved` | Đề xuất sửa N05 sang `/lessons/{id}/flashcards` |

`lessons.status` theo sơ đồ mới: `DRAFT`, `UPLOADED`, `PROCESSING`, `TRANSCRIBING`, `AI_PROCESSING`, `REVIEW_REQUIRED`, `APPROVED`, `PUBLISHED`, `FAILED`. `duration_seconds >= 0`, `retry_count >= 0`. Một số `NOT NULL` và `DEFAULT` chưa thể khẳng định từ sơ đồ rằng file migration/schema đã cập nhật đủ.

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

> Giữ nguyên mã N01–N12 để đối chiếu lịch sử. **Riêng N05 được đề xuất đổi path** từ `GET /sections/{id}/flashcards` sang `GET /lessons/{id}/flashcards` vì schema mới có `flashcards.lesson_id`. Đây là đề xuất **breaking change trong bản DRAFT**, cần B/C/A duyệt. Auth có route trong source nhưng chưa đồng bộ dependency/frontend.

### 3.1. Nhóm N01–N12 (11 API cũ + đăng ký tài khoản)

| # | Method + path (đề xuất) | Chức năng | Vai trò | File gợi ý | Ưu tiên | Quyết định cần chốt |
|---:|---|---|---|---|---|---|
| N01 | `GET /courses/{id}/sections` | Liệt kê section theo `position` | Student/Instructor | `api/sections.py` | P0 | **Giữ tương thích FE hiện tại**; course detail cũng có nested outline, tránh gọi trùng không cần thiết |
| N02 | `GET /sections/{id}/lessons` | Liệt kê lesson theo `position` | Student/Instructor | `api/lessons.py` | P0 | **Giữ tương thích FE hiện tại**, hỗ trợ `skip`, `limit` theo source |
| N03 | `GET /instructor/courses` | Khóa học của instructor, gồm DRAFT/PUBLISHED | Instructor | `api/courses.py` | P0 | Phân trang / filter `status` |
| N04 | `GET /students/me/courses` | Khóa học student đã enroll | Student | `api/enrollments.py` | P0 | Có trả tiến độ tóm tắt hay không |
| N05 | **`GET /lessons/{id}/flashcards`** | Lấy flashcards đã duyệt của một lesson | Student | `api/flashcards.py` (mới) | P1 | **ĐỀ XUẤT ĐỔI PATH** theo `flashcards.lesson_id`; nếu cần theo Section tạo API tổng hợp riêng |
| N06 | `POST /lessons/{id}/confirm-upload` | Xác nhận object tồn tại, gắn video với lesson | Instructor | `api/uploads.py` | P0 | Chốt upload session/key và cách kích hoạt pipeline |
| N07 | `POST /auth/login` | Đăng nhập email/password, cấp JWT | Guest | `api/auth.py` | Sau luồng học core | Route có theo source, cần test JWT end-to-end; không cần nếu dùng Cognito |
| N08 | `GET /auth/me` | Lấy user hiện tại và role từ JWT | Authenticated | `api/auth.py` | Sau luồng học core | Route có theo source, kiểm tra Bearer và mapping DB |
| N09 | `GET /admin/users` | Danh sách/tìm kiếm/lọc user | Admin | `api/admin.py` (mới) | P2 | UI Admin có nằm trong MVP 4 tuần không |
| N10 | `PATCH /admin/users/{id}` | Sửa profile, role/trạng thái user | Admin | `api/admin.py` (mới) | P2 | Policy đổi role, audit và đồng bộ Cognito |
| N11 | `GET /admin/monitoring` | Tổng hợp trạng thái job/lỗi/chi phí | Admin | `api/admin.py` (mới) | P2 | Backend đọc được nguồn metrics/billing nào |
| N12 | `POST /auth/register` | Tự đăng ký Student bằng email/password | Guest | `api/auth.py` | Sau luồng học core | Route có theo source; không cho tự đăng ký Instructor/Admin |

**Quy tắc riêng:** Nhóm đã có code route auth theo báo cáo source nhưng chưa kết nối `get_current_user` nghiệp vụ và LoginPage; vì vậy **tạm hoãn tích hợp frontend auth**, không xem đây là cơ chế xác thực production. Chỉ đánh dấu `Implemented` khi kiểm thử JWT với PostgreSQL, protected route, role và frontend; nếu chuyển Cognito thì N07/N12 có thể thay thế.

### 3.2. Các API ứng viên khác (cân nhắc sau khi đối chiếu UI/Swagger)

| Mã | Method + path (đề xuất) | Mục đích | Vai trò | Ưu tiên | Điều kiện / khả năng gộp |
|---|---|---|---|---|---|
| X01 | `GET /lessons/{id}/video-url` | Presigned GET URL phát video S3 private | Student/Instructor | **P0 — đề xuất ưu tiên** | **Nên tách** khỏi lesson metadata; cần nhóm duyệt, kiểm tra entitlement/unlock |
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

**Chưa đưa các ứng viên X01–X12 vào MVP chính thức.** Riêng **X01 là ứng viên P0 ưu tiên để sửa trang học video**, chưa có bằng chứng endpoint đã triển khai. Khi nhóm chốt thì chuyển sang danh sách đã duyệt và cập nhật OpenAPI.

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

**`POST /courses`** (GỐC): Instructor tạo bản nháp (`DRAFT`) mặc định. Trường `status` do client truyền **không mặc nhiên cho phép tạo PUBLISHED**. Theo schema mới `learning_objectives` phải là một JSON array (cho phép `[]` nếu nghiệp vụ đồng ý). Ví dụ request đề xuất:

```json
{
  "title": "Lập trình Python",
  "description": "Lập trình Python cơ bản",
  "learning_objectives": ["Biết cú pháp Python", "Viết được chương trình nhỏ"]
}
```

Response thành công thường `201 Created`, chứa `id`, `instructor_id`, `status: "DRAFT"` và các metadata có trong schema.

**`GET /courses/{id}`** (GỐC): Course detail/outline. **Báo cáo Codex 28/10 xác nhận response schema trong source có `sections[].lessons[]`**; đồng thời N01/N02 đang hoạt động theo route và được frontend gọi. V4 **giữ cả hai lựa chọn để không phá tương thích**, nhưng FE nên chọn một nguồn outline cho từng màn hình và tránh request dư. Chỉ lộ thông tin theo quyền/publish; cần đối chiếu response runtime trước khi khóa cấu trúc.

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

**`GET /courses/{id}/sections`** (N01): Theo đề xuất trả mảng trực tiếp (không tự bọc `data`):

```json
[{"id":1,"course_id":1,"title":"Giới thiệu","position":1}]
```

**`GET /sections/{id}/lessons`** (N02): Trả danh sách bài học theo `position`; theo báo cáo source hỗ trợ query `skip`, `limit`. Ví dụ **đề xuất (phải kiểm tra schema response thật)**:

```json
[{"id":3,"section_id":1,"title":"Tổng quan Cloud","position":1,"status":"PUBLISHED","duration_seconds":600}]
```

**`GET /lessons/{id}`** (GỐC): **Giữ method/path**, nhưng cần mở rộng `LessonResponse` để trang học dùng được. Theo báo cáo source 28/10, endpoint hiện chỉ có `id`, `section_id`, `title`, `position`. **V4 đề xuất P0 bổ sung response dưới đây; không coi là đã implement:**

```json
{
  "id": 3,
  "section_id": 1,
  "title": "Tổng quan Cloud",
  "position": 1,
  "status": "PUBLISHED",
  "duration_seconds": 600,
  "summary": "Giới thiệu mô hình điện toán đám mây.",
  "transcript": {
    "segments": [
      {"start": 0.0, "end": 12.5, "text": "Chào mừng đến với khóa học."}
    ]
  },
  "key_concepts": ["Cloud Computing", "IaaS"]
}
```

**Quy tắc schema/authorization đề xuất:**

- `transcript` có thể là `null` khi nội dung chưa được duyệt/chưa được tạo; FE phải xử lý `transcript?.segments ?? []`, không gọi `.reduce()` trên `undefined`. `summary` có thể `null`; `key_concepts` trả mảng, mặc định `[]` nếu đã đủ quyền nhưng chưa có dữ liệu AI. **Cấu trúc `segments` phải đối chiếu định dạng thực tế từ Transcribe/AI trước khi chốt.**
- Trường trong DB là `transcript_json` và `key_concepts_json`; mapping sang tên API `transcript` và `key_concepts` là **đề xuất**, không mặc định ORM/Pydantic đã map.
- Student chỉ nhận transcript/summary/concepts **đã approve/publish và được unlock**; Instructor sở hữu Lesson có thể xem bản nháp qua API AI Review. Không trả nội dung nháp cho student.
- Không trả `raw_video_key`, `processed_video_key` hay S3 credentials vào response dành cho student. Playback tách sang X01. Nếu không có video hợp lệ, FE hiển thị trạng thái “Chưa có video”, không coi response là URL có thể phát.
- URL frontend `/courses/:courseId/lessons/:lessonId` **không** buộc phải có API `GET /courses/{courseId}/lessons/{lessonId}`. FE dùng `courseId` lấy outline/breadcrumb, `lessonId` lấy nội dung; có thể kiểm tra `lesson.section_id` thuộc course trong dữ liệu outline để tránh hiển thị sai ngữ cảnh (phân quyền vẫn ở backend).

**`PATCH /sections/{id}`, `PATCH /lessons/{id}`** (X05/X07): Nếu triển khai phải xử lý xung đột vị trí và ownership. Với schema mới, Lesson update cần tránh cho client sửa trực tiếp các trường trạng thái pipeline/khóa S3 không được phép.

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

**`GET /lessons/{id}/processing-status`** (GỐC): Đề xuất đồng bộ đúng enum trong sơ đồ mới: `DRAFT`, `UPLOADED`, `PROCESSING`, `TRANSCRIBING`, `AI_PROCESSING`, `REVIEW_REQUIRED`, `APPROVED`, `PUBLISHED`, `FAILED`. Ví dụ **chưa triển khai**:

```json
{
  "lesson_id": 3,
  "status": "FAILED",
  "retry_count": 1,
  "error_message": "Transcription failed",
  "updated_at": "2026-10-28T07:00:00Z"
}
```

Backend xác minh instructor ownership trước khi trả thông tin lỗi pipeline; không lộ internal exception hoặc AWS credentials.

**`POST /lessons/{id}/retry`** (GỐC): Chỉ cho retry trạng thái `FAILED` và khi user đủ quyền. Không tạo nhiều job đồng thời; log số lần thử và nguyên nhân.

**`GET /lessons/{id}/video-url`** (X01) — **ĐỀ XUẤT P0**, chọn phương án tách playback khỏi lesson detail để dễ refresh URL hết hạn.

Response `200 OK` tham khảo (URL giả minh họa):

```json
{
  "lesson_id": 3,
  "video_url": "https://example.com/short-lived-presigned-get-url",
  "expires_in": 900,
  "content_type": "video/mp4"
}
```

- Backend cấp Presigned **GET** của object đã xử lý/cho phép phát (`processed_video_key` nếu có); nếu cho phép dùng raw video để test local, phải kiểm tra ownership/entitlement và quy định rõ đây là ngoại lệ phát triển.
- Student phải enroll, lesson đã publish/unlock; Instructor chỉ xem lesson mình sở hữu. Không tạo S3 public URL. `404` nếu không có playable object, `403` nếu thiếu quyền (hoặc `404` để không tiết lộ tài nguyên theo policy), `409` nếu chưa sẵn sàng tùy contract nhóm chốt.
- URL có hạn; frontend làm mới bằng endpoint này khi cần, không lưu dài hạn/persist hoặc ghi log URL. Nếu chuyển sang CloudFront/HLS, phải cập nhật `video_url`/`content_type` hoặc một playback schema khác theo phiên bản contract.

**Kiểm tra upload:** Giới hạn đề xuất hiện dùng là **500 MiB** khi xin URL dựa trên `file_size` client gửi; kiểm tra thực tế phải dùng `HeadObject.ContentLength` tại `confirm-upload`, kết hợp phiên upload/key hợp lệ. Việc upload object qua CLI không tự tạo bản ghi Lesson hay cập nhật `status`.

### 4.5. AI Content Review

- `GET /lessons/{id}/ai-content` (GỐC): Instructor lấy bản nháp transcript có timestamp, summary, concepts, quiz; không trả dữ liệu nháp cho student.
- `PATCH /lessons/{id}/ai-content` (GỐC): Sửa các trường review được cho phép; mọi field phải theo schema do C chốt.
- `POST /lessons/{id}/approve` (GỐC): Chỉ approve khi nội dung đạt kiểm tra. **Chưa thống nhất** approve có tự publish lesson hay không; cần quyết định trước khi FE tích hợp.

### 4.6. Enrollment và progress

- `POST /courses/{id}/enroll` (GỐC): Student enroll course đã PUBLISHED. Backend lấy student ID từ auth, không nhận `student_id` tự chọn. Đăng ký trùng: thống nhất `409` hoặc idempotent `200`.
- `GET /students/me/courses` (N04): Chỉ enrollment của student hiện tại, có thể kèm `progress_percent` nếu BE/B đồng ý.
**`PUT /lessons/{id}/progress`** (GỐC): Theo schema mới `lesson_progress(student_id, lesson_id, watched_seconds, completed, updated_at)`, đề xuất body (**cần B và backend owner chốt**):

```json
{"watched_seconds": 120, "completed": false}
```

Response `200 OK` ví dụ đề xuất:

```json
{"lesson_id": 3, "watched_seconds": 120, "completed": false, "updated_at": "2026-10-28T07:00:00Z"}
```

- Lấy `student_id` từ auth (không nhận từ body); chỉ ghi tiến độ cho lesson đã được phép học; unique `(student_id, lesson_id)` → upsert.
- **Phải chốt ý nghĩa** `watched_seconds` là số giây đã xem tích lũy (không nhất thiết liền mạch) hay vị trí phát cuối cùng. Frontend hiện gửi `progress_percent` và `last_position_seconds`, **không tương thích** với 2 trường DB trên. Nếu muốn resume chính xác cần thêm `last_position_seconds` vào schema, không giả vờ coi nó bằng `watched_seconds`.
- Cần chốt việc client được tự đặt `completed`, có kiểm tra duration/ngưỡng hoàn thành hay không; không tin hoàn toàn dữ liệu tự khai của client để mở khóa bài thi.

**`GET /courses/{id}/progress`** (GỐC): Backend tính tiến độ của student hiện tại dựa trên lessons thuộc course và bảng `lesson_progress`; kiểm tra enrollment. Ví dụ **đề xuất**:

```json
{
  "course_id": 1,
  "completed_lessons": 2,
  "total_lessons": 5,
  "progress_percent": 40.0,
  "lessons": [
    {"lesson_id": 1, "watched_seconds": 560, "completed": true},
    {"lesson_id": 2, "watched_seconds": 320, "completed": true}
  ]
}
```

Phải chốt cách đếm Lesson chưa publish, cách xử lý course chưa có Lesson (`total_lessons=0`) và quyền Instructor xem tiến độ nào. Theo báo cáo 28/10, frontend **đã gọi GET** nhưng backend chưa đăng ký route và log nhận `404`; **không gắn nhãn Implemented**.

### 4.7. Flashcard, Quiz, Unlock

**`GET /lessons/{id}/flashcards`** (N05) — **ĐỀ XUẤT ĐỔI PATH TRONG DRAFT V4** vì sơ đồ DB mới gắn `flashcards.lesson_id`, không phải `section_id`. Trả flashcards **đã duyệt** và thuộc lesson được quyền xem. Ví dụ đề xuất:

```json
{
  "lesson_id": 3,
  "flashcards": [
    {"id": 11, "front": "IaaS là gì?", "back": "Hạ tầng dưới dạng dịch vụ", "position": 1}
  ]
}
```

**Tương thích với Contract v3:** Endpoint `/sections/{id}/flashcards` trước đây mới là **đề xuất, chưa có bằng chứng implement**. Không âm thầm đổi route nếu FE/C đã dùng; nếu UI cần xem flashcards theo Section, tạo endpoint tổng hợp hoặc giữ alias có chủ đích sau khi nhóm duyệt. `is_approved=false` không trả cho Student.

**`GET /sections/{id}/quiz`** (GỐC): Schema mới `quizzes.section_id UNIQUE` (tối đa 1 quiz/section), `passing_score` mặc định 80 theo sơ đồ; chỉ checkpoint được approve/được mở; **không trả `correct_answer`** trước khi submit.

**`POST /quizzes/{id}/attempts`** (GỐC): Student gửi lựa chọn, backend tự chấm và lưu attempt. Ví dụ request **đề xuất**:

```json
{"answers": [{"question_id": 1, "selected_option_id": 2}]}
```

Response cần chốt `score`, `passed`, `attempt_number`, unlock section tiếp theo. **`passing_score` trong DB mặc định 80 nhưng có thể thay đổi theo quiz** (CHECK 0–100); backend lấy ngưỡng từ quiz thay vì hardcode `80` trong toàn bộ logic.

**`GET /students/me/quiz-history`** (GỐC): Lấy các attempt của student hiện tại.

**`GET /quizzes/attempts/{id}`** (X04): ĐỀ XUẤT nếu trang kết quả cần chi tiết khái niệm/câu sai; cần quyết định thời điểm được thấy đáp án đúng theo nghiệp vụ.

### 4.8. Tutor, Instructor Analytics

- `POST /tutor/sessions` (GỐC): Tạo phiên ôn tập từ attempt chưa đạt của chính student.
- `POST /tutor/sessions/{id}/messages` (GỐC): Student gửi câu hỏi cho Tutor trong session mình sở hữu. Ví dụ request đề xuất: `{"message":"Giải thích lại IaaS"}`.
- `GET /instructor/courses/{id}/analytics` (GỐC): Instructor sở hữu course xem enrollment/progress/pass-fail; định nghĩa chỉ số thực với C.
- `GET /instructor/dashboard` (X02), `GET /instructor/courses/{id}/students` (X03): Chỉ tạo nếu API analytics/course có sẵn không đủ dữ liệu UI.

### 4.9. Authentication — N07, N08, N12 (HOÃN TÍCH HỢP FRONTEND, SOURCE CÓ ROUTE)

**Phạm vi bản thử nghiệm:** JWT HS256 + PostgreSQL + Argon2id được mô tả theo patch auth. Báo cáo source 28/10 cho biết `api/auth.py` có route, nhưng dependency của API nghiệp vụ vẫn dùng demo, LoginPage/AuthContext chưa triển khai. **Status: `Source-confirmed routes / Integration incomplete`**, không khẳng định auth đã được tích hợp và test end-to-end. Nhóm thống nhất **để auth frontend làm sau**, không đưa vào điều kiện hoàn thành trang Course/Video hiện tại.

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
- **Migration/Auth:** Nếu chọn JWT nội bộ, `users.password_hash VARCHAR(255) NULL` là cần thiết (schema cũ có; sơ đồ mới không thể hiện); xác minh có cột trước khi chạy migration. User seed có `password_hash=NULL` không thể login cho tới khi đặt mật khẩu bằng công cụ tin cậy.
- **Tương thích `cognito_sub`:** Patch auth cũ từng tạo `cognito_sub="local:<uuid>"` vì giả định `NOT NULL`; **sơ đồ mới chỉ thể hiện `UNIQUE`, không ghi `NOT NULL`**. Phải đối chiếu `schema.sql` thực tế; không thêm định danh giả hoặc thay ràng buộc chỉ dựa trên bản contract cũ.
- **Cấu hình:** `.env` cần `JWT_SECRET_KEY` đủ mạnh và `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`; không commit secret. Chỉ chạy qua HTTPS khi đưa lên môi trường công khai.
- **Chưa triển khai trong patch:** refresh token, endpoint revoke/logout server-side, reset password, email verification, MFA, Cognito. Nếu logout ở frontend bằng cách xóa token, token đã phát hành vẫn còn hiệu lực đến khi hết hạn.
- **Tăng cường trước khi public:** rate limiting cho login/register, chính sách mật khẩu, bảo vệ chống brute force, quản lý secret/rotation và audit. Tùy ngân sách, có thể chọn Cognito thay cho auth tự quản lý.

#### Điều kiện để đổi trạng thái từ `Source-confirmed routes / Integration incomplete` sang `Implemented`

1. Rà soát code auth đang tồn tại trong repo, không ghi đè `main.py`, router và cấu hình hiện tại.
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
| D01 | Theo source, Course Detail đã nested `sections[].lessons[]`; FE vẫn dùng N01/N02. Chọn nguồn outline mặc định nào? | Tránh request dư, giữ tương thích N01/N02 |
| D02 | Student xem course chưa enroll tới mức nào? | Quy tắc 401/403 và course detail |
| D03 | **Đề xuất X01** tách `GET /lessons/{id}/video-url` để cấp Presigned GET; nhóm duyệt? | S3 private, VideoPlayer, refresh URL |
| D04 | `confirm-upload` lưu phiên upload bằng bảng mới hay trạng thái khác? | N06, migration DB, trigger pipeline |
| D05 | Pipeline kích hoạt từ S3 EventBridge hay xác nhận upload? | Tránh xử lý trùng/job orphan |
| D06 | Sơ đồ mới gắn flashcard với `lesson_id`; chấp nhận đổi N05 sang `/lessons/{id}/flashcards`? | Breaking change của đề xuất cũ, frontend/C |
| D07 | Chốt áp dụng patch JWT local hay chuyển Cognito; thời điểm bỏ `X-Demo-User`? | N07/N08/N12, migration, FE token, tất cả API có bảo vệ |
| D08 | Admin UI 2 màn hình có nằm trong MVP 4 tuần không? | N09–N11 / phân công |
| D09 | Đồng bộ 9 giá trị `lessons.status` theo sơ đồ mới; `APPROVED` có tự `PUBLISHED` không? | Workflow, LessonResponse, review |
| D10 | Ai chịu trách nhiệm các endpoint **mới**, triển khai tuần nào? | Lộ trình A/B/C/D |
| D11 | Progress `watched_seconds` ≠ `last_position_seconds`; quiz `correct_answer` dạng text, options_json array. Chốt payload nào? | Tránh FE/BE lỗi 422 và lỗi resume/unlock |
| D12 | N02 đang có `skip`,`limit`; có đổi phân trang hay không? Course/Admin có cần filter/search? | Query params và kết quả trả về |
| D13 | `GET /lessons/{id}` dùng `transcript` segments chuẩn hóa hay dữ liệu AWS Transcribe gốc? Null được phép ở trạng thái nào? | LessonResponse, TranscriptPanel, AI adapter |
| D14 | `progress_percent` được tính từ số Lesson hoàn thành hay thời lượng video; `completed` do ai xác nhận? | Progress, unlock, CourseCard |
| D15 | `users.password_hash` có trong schema.sql mới không; khi nào thay demo bằng JWT? | Migration, frontend auth (làm sau) |

---

## 6. Đối chiếu với UI và lộ trình

| Nhu cầu UI / Cloud | Endpoint | Căn cứ | Ghi chú |
|---|---|---|---|
| Instructor xem course DRAFT/PUBLISHED | N03 | UI v2 trang 6 | Không thể dùng catalog chỉ PUBLISHED |
| Form course + outline | API course gốc + N01/N02 | UI v2 trang 7 | Course Detail nested outline theo source; giữ N01/N02 để không phá FE |
| Upload video và trạng thái | API upload gốc + N06 + status gốc | UI v2 trang 8; AWS tuần 2–3 | Workflow chạy không đồng bộ |
| Student xem video, transcript | Lesson gốc + **X01 đề xuất P0** | UI v2 trang 12 | Cần mở rộng LessonResponse, normalise transcript, video-url private |
| Student flashcard | N05 đề xuất đổi `/lessons/{id}/flashcards` | UI v2 trang 13 | Sơ đồ mới có `flashcards.lesson_id` |
| Student các course đã enroll | N04 | UI v2 trang 11–15 | Theo danh tính hiện tại |
| Login, đăng ký, role redirect | N12 + N07 + N08 (route theo source, **chưa tích hợp**) | UI v2 trang 4 có Login; Register là mở rộng | **Để sau theo kế hoạch nhóm**, không dùng demo auth khi public |
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
| **2026-10-28** | **Contract Draft v4** | Giữ 24 API gốc; **đề xuất** LessonResponse + X01; sửa N05 theo lesson_id; bổ sung Progress schema/response, video statuses, bảng schema mới; cập nhật audit trạng thái theo Codex | Dự thảo để nhóm A/B/C/D review | **Draft — chưa chốt** | Chưa có PR |

---

## 8. Checklist rà soát và chốt API cho giai đoạn tiếp theo

- [ ] Đối chiếu **24 API gốc** với Swagger; đánh dấu từng endpoint: Implemented / Partial / Planned.
- [ ] Giữ N01/N02 hoạt động; chọn nguồn outline mặc định ở FE sau khi kiểm tra `GET /courses/{id}` và tránh gọi trùng.
- [ ] Chốt N03/N04 và dữ liệu phục vụ màn hình course của Instructor/Student.
- [ ] Chốt N06 (`confirm-upload`) và chiến lược chống event trùng.
- [ ] Chốt X01 `GET /lessons/{id}/video-url` (đề xuất P0) và cách làm mới Presigned GET URL.
- [ ] Chốt mở rộng `GET /lessons/{id}`: `status`, `duration_seconds`, `summary`, `transcript`, `key_concepts`, nullability và quyền xem.
- [ ] Duyệt thay đổi N05 từ Section Flashcards sang Lesson Flashcards (`flashcards.lesson_id`); tránh breaking change không thông báo.
- [ ] **Để sau theo tiến độ frontend:** chốt JWT local hay Cognito; rà N07/N08/N12 và chọn thời điểm thay `X-Demo-User`.
- [ ] Nếu chọn JWT: ghép patch an toàn, chạy migration `password_hash`, đặt `JWT_SECRET_KEY`, test Swagger/register/login/me trên PostgreSQL.
- [ ] Kiểm thử vai trò STUDENT/INSTRUCTOR và loại bỏ khả năng bypass bằng `X-Demo-User`; phối hợp B gửi Bearer token.
- [ ] Xác nhận các API Admin là phạm vi MVP hay backlog.
- [ ] Chốt Progress theo `lesson_progress`: `watched_seconds` và `completed`, cách tính `progress_percent`, có cần `last_position_seconds` để resume; B phối hợp BE implement 2 route còn thiếu.
- [ ] Chốt request/response của Quiz, AI Review, Tutor và trạng thái workflow theo schema mới.
- [ ] Đối chiếu schema.sql mới với sơ đồ: `users.password_hash`, unique section position, flashcard lesson_id, defaults timestamps, JSONB NOT NULL.
- [ ] Xác nhận mã lỗi, chính sách quyền, không để bypass bằng gọi API trực tiếp.
- [ ] Gán người/tuần cho API mới sau khi nhóm duyệt.
- [ ] Tạo/cập nhật OpenAPI và test theo contract trước khi FE tích hợp.

**Ghi chú cuối:** Đây là **bản dự thảo có thể tiếp tục bổ sung**. Tên đường dẫn, vai trò và schemas của các API *đề xuất* không trở thành yêu cầu chính thức trước khi cả nhóm thống nhất. Các ví dụ JSON v4 chỉ là hợp đồng **đề xuất**, không xác nhận API đang trả như vậy. Sau khi nhóm duyệt, đồng bộ `database/schema.sql` → Pydantic/OpenAPI → frontend API client → test tích hợp rồi mới ghi `Implemented`.
