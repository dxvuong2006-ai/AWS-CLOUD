# Kiểm toán triển khai LearnCloud API Contract v6

Ngày kiểm toán: **09/11/2026 (Asia/Saigon)**. Source HEAD: `df9ff3e1bb9d89cc09d9c828a5f56cecb810dfca`. Phạm vi là workspace local; không suy ra phiên bản đang deploy.

## 1. Kết luận và số liệu có thể kiểm chứng

- Bảng đầu Contract v6 có **60** API FastAPI mục tiêu, tính mỗi cặp **method + path đúng tham số** một lần.
- Source đang đăng ký **73 operation entries**, tương ứng **68 cặp method/path duy nhất**, trên **56 path OpenAPI**. Con số 56 path này **không phải** 56 màn hình.
- **44/60 endpoint contract tồn tại** trong runtime lẫn OpenAPI. **16/60 chưa có exact path**, gồm 2 MISSING và 14 PROPOSED/DECISION. Có **24 operation ngoài bảng contract**.
- Phân loại chặt theo bằng chứng: **DONE 1; PARTIAL 43; MISSING 2; PROPOSED 14; BLOCKED 0**.
- Chỉ `GET /health` đạt toàn bộ yêu cầu hẹp của nó. **1/60 = 1,67%** là tỷ lệ API đã khép đủ tiêu chí kiểm chứng, **không phải** 98,33% code chưa viết. Phần lớn nghiệp vụ có code nhưng còn lỗi, test thiếu/lỗi, lệch contract hoặc tích hợp chưa được xác minh.
- Test repository, lượt cuối: **165 passed, 75 failed, 16 skipped**, thêm **26 subtests passed** được tách riêng, không cộng hai lần. Backend unit: **137 passed / 75 failed**; AI pipeline: **28 passed**; PostgreSQL integration: **16 skipped**.
- **32 kịch bản kiểm toán bổ sung** chạy in-memory: **8 đạt yêu cầu hẹp, 24 tái hiện vi phạm**. Đây là các kịch bản được chọn theo rủi ro, **không dùng 8/32 để tính chất lượng toàn hệ thống**.
- Các lỗi ưu tiên: role vừa bị hạ có thể bị group token cũ phục hồi; Flashcard PUT thiếu role guard; lesson/video/flashcards chưa enforce unlock; PATCH summary xóa flashcards; approve/publish thiếu processed-video guard; progress FE trả 422 và mất trạng thái; Tutor legacy không mở checkpoint retry.

## 2. Nguồn đối chiếu, phạm vi và quy tắc phân loại

### 2.1. Tài liệu đúng phiên bản, không giả định tên file

Không có file tên `LEARNCLOUD_API_CONTRACT_V6.md` trong cây tài liệu tìm thấy. File **`docs/api-contract.md`** mở đầu bằng **“LearnCloud — API Contract v6 (đối chiếu 56 màn hình)”**, Draft v6 ngày 09/11/2026, 839 dòng; toàn bộ nội dung đã được đọc, đặc biệt bảng 60 API tại dòng 41–102. Đây là nguồn contract dùng cho báo cáo, không tự tạo/đổi tên contract.

Không thấy `screens.zip` trong repository đã kiểm kê. Có đủ **`docs/ui-doc/ui-spec/screens/01.png` … `56.png`** và `docs/ui-doc/ui-spec/SPEC.md`. Mapping 56 màn hình dựa trên bảng screen/API v6 dòng 112–169 và hành vi điều hướng trong SPEC. Đây là **kiểm toán khả năng Backend phục vụ UI**, không phải browser E2E hay kiểm tra pixel; wiring UI thực tế ngoài những API adapters được đọc là **UNVERIFIED**.

Đã đọc routers, dependencies, schemas, services, repositories, models, SQL bootstrap và toàn bộ migrations liên quan. Đọc thêm adapters S3/AI/MediaConvert, test fixtures, integration guards và frontend API adapters để phân biệt API thực, proxy AWS, mock và lệch payload. Báo cáo cũ trong `agent/output` chỉ là ngữ cảnh, không dùng làm bằng chứng DONE.

### 2.2. An toàn kiểm thử và giới hạn

- Chỉ thay đổi file báo cáo này. Không sửa API/source/test/contract/migrations, không chạy migration/seed, không gọi AWS CLI, không deploy.
- `DATABASE_URL=sqlite:///:memory:` hoặc engine `sqlite://` dùng `StaticPool`; các fixture tự tạo dữ liệu giả, không truy cập DB dự án. Kịch bản bổ sung bật SQLite `PRAGMA foreign_keys=ON`.
- Dùng credentials/user pool/client **giả**, vô hiệu AWS metadata/profile/config và bỏ `AWS_LAMBDA_FUNCTION_NAME` trong process test để không vào nhánh SSM/RDS.
- Chặn `socket.connect/connect_ex/sendto/getaddrinfo/create_connection`; chỉ cho phép socketpair nội bộ của asyncio trên Windows, không cho HTTP/DB network. API chạy bằng ASGI/TestClient. S3/Bedrock/Cognito được mock khi cần.
- Không kết nối/đọc/ghi **RDS production**. Không kiểm chứng SQL triggers, row locks, isolation, migrations, AWS authorizer/session revoke, S3 object thực hoặc Bedrock output trên môi trường thật: ghi **UNVERIFIED**.
- SQLite test pass và PostgreSQL DDL compile chỉ chứng minh phần tương ứng; không thay cho PostgreSQL integration. Một test thất bại do setup lỗi cũng không tự chứng minh business logic sai.

### 2.3. Ý nghĩa trạng thái trong báo cáo

| Trạng thái | Điều kiện |
|---|---|
| DONE | Có exact endpoint và đủ bằng chứng request/response, nghiệp vụ, guard, persistence nếu có và test đạt; không có gap đã biết trong phạm vi contract. |
| PARTIAL | Có endpoint nhưng còn gap cụ thể hoặc một tiêu chí bắt buộc chưa có bằng chứng; phần chưa kiểm được ghi UNVERIFIED. |
| MISSING | Exact endpoint không có, và contract coi nó là route đã có/cần có. Phải giải thích nếu bị bỏ chủ ý vì Cognito. |
| PROPOSED | Path/schema còn đề xuất hoặc DECISION và chưa có exact route. Nếu đã có code, đánh giá PARTIAL/DONE thay vì giữ nhãn PROPOSED cũ. |
| BLOCKED | Chứng minh được không thể hoàn thiện vì module/DB/AWS chưa sẵn sàng. Không dùng nhãn này chỉ vì chưa được kiểm production. |

`UNVERIFIED` là **mức bằng chứng**, không phải trạng thái thứ sáu. BLOCKED=0 không có nghĩa không có blocker phát hành: migration conflict và dependency readiness được nêu riêng; chưa có bằng chứng cho phép kết luận AWS/RDS đang chạy đã thiếu cấu hình nào. Chuẩn DONE ở đây bảo thủ; chức năng persistence chưa được xác minh PostgreSQL/contract đầy đủ không được nâng DONE vì vài mock assertions đạt.

Các JSON ghi rõ **ĐỀ XUẤT** trong v6 chưa phải schema đóng băng. Khác tên field được ghi là **schema drift cần chốt**, không tự gọi mọi khác biệt là lỗi breaking. Ngược lại, payload frontend hiện có bị 422 (Q27), mất dữ liệu (Q23), bypass guard và sai ngưỡng 2/3 là lỗi đã tái hiện.

## 3. Runtime FastAPI và OpenAPI

Import ứng dụng `app.main:app` qua môi trường dependencies hiện có, với settings offline trước import; gọi trực tiếp **GET /openapi.json → 200** và **GET /docs → 200**. OpenAPI không dùng proxy từ môi trường deploy. Toàn bộ **68** cặp method/path công khai trong `app.routes` khớp tập operations ở OpenAPI; không có endpoint contract đang tồn tại bị `include_in_schema=False`.

Router Tutor được include tại `backend/app/main.py:59`; prefix thực là đường dẫn khai báo đầy đủ trong `backend/app/api/tutor.py:22/31/40`. Ba POST Tutor đều có trong OpenAPI; vấn đề của chúng là logic/workflow, không phải thiếu Swagger registration.

### 3.1. Năm cặp route bị trùng, schema và handler không đồng nhất

`screen_workflows.router` được include đầu tiên (`backend/app/main.py:55`); HTTP matching chọn handler đầu. Khi OpenAPI hợp nhất cùng method/path, definition từ handler sau ghi đè operation. So sánh `operationId` xác nhận:

| Method/path | Handler thực được chọn đầu (dòng decorator) | Handler xuất hiện trong OpenAPI (dòng decorator) |
|---|---|---|
| `GET /instructor/dashboard` | `app.api.screen_workflows.dashboard` (33) | `app.api.analytics.get_instructor_dashboard` (18) |
| `GET /instructor/review-queue` | `app.api.screen_workflows.queue` (37) | `app.api.review.list_review_queue` (24) |
| `GET /instructor/students` | `app.api.screen_workflows.students` (41) | `app.api.analytics.list_instructor_students` (88) |
| `GET /instructor/students/{student_id}` | `app.api.screen_workflows.student` (45) | `app.api.analytics.get_instructor_student` (131) |
| `GET /lessons/{lesson_id}/content` | `app.api.screen_workflows.content` (81) | `app.api.lessons.get_lesson_content` (134) |

Hậu quả: dashboard khác số lesson/shape; queue runtime không có PUBLISHED và không trả processing_status giống bản review; student detail runtime có lỗi KeyError; transcript content runtime đọc dict/segments, bản sau chỉ đọc list. Chỉ so tập path sẽ **không phát hiện** khác handler này. Đây là **5 route trùng khác nhau**, không phải 7 review alias trùng như snapshot v6 cũ. Các 7 review aliases hiện mỗi method/path chỉ đăng ký một lần.

### 3.2. Snapshot trong contract đã cũ ở những điểm chính

`docs/api-contract.md:23/181–221/785` mô tả 42 registrations/35 unique, X-Demo-User mặc định user 1, progress rỗng, thiếu admin/instructor lists và số test cũ. Source hiện tại đã thay đổi:

- JWT Cognito/JWKS và Bearer đã có, demo header không chọn identity (Q01/Q02).
- Login local/proxy đã bỏ, Frontend dùng Cognito SDK.
- Progress, Admin users, Instructor list/detail/dashboard/review queue đã có.
- Flashcards đã có model, generation/review và lesson CRUD; **remembered state theo learner** vẫn thiếu.
- Checkpoint mới đã có enrollment/publication/lesson-completion/remediation guards và idempotency.
- Có workflow remediation mới phục vụ UI, **khác** bộ Tutor contract cũ.

Không tái sử dụng trạng thái cũ trong contract làm kết quả kiểm toán.

## 4. Ma trận toàn bộ 60 API trong bảng đầu Contract v6

Bằng chứng `app/...` và `tests/...` dưới đây đều thuộc `backend/`. Mọi `Qxx` dẫn đến mục 8; `contract:N` là dòng trong `docs/api-contract.md`. Các path được so **đúng method và tên tham số**, không tự tính alias khác là endpoint đã có.

| STT | Method | Path | Module | Trạng thái audit | Vấn đề còn thiếu / điều đã xác minh | Bằng chứng file/dòng |
|---:|---|---|---|---|---|---|
| 1 | GET | `/health` | System | **DONE** | Health tĩnh đúng contract; HTTP 200 và {status: ok}; không hứa probe DB/AWS. | `backend/app/main.py:70`; `Q30`; contract:43; runtime/OpenAPI: có |
| 2 | POST | `/auth/register` | Auth | **PARTIAL** | Đã chuyển sang proxy Cognito sign_up, không còn local Argon2/JWT như snapshot v6. Public schema chặn role injection; signup/OTP/DB đồng bộ và AWS thật UNVERIFIED. | `backend/app/api/auth.py:30`; `backend/app/services/auth_service.py:237`; `backend/app/schemas/auth.py:7`; contract:44; runtime/OpenAPI: có |
| 3 | POST | `/auth/login` | Auth | **MISSING** | Không có FastAPI route, đã chủ ý bỏ login proxy; React signInWithCognito xử lý đăng nhập. Đây là lệch tài liệu, không phải yêu cầu tạo lại API local. | `backend/app/api/auth.py:19`; `backend/tests/unit/test_auth_integration.py:87`; `frontend/src/api/cognito.js:73`; contract:45; runtime/OpenAPI: không |
| 4 | GET | `/auth/me` | Auth | **PARTIAL** | JWT RS256/exp/issuer/client/token_use và từ chối X-Demo-User đã xác minh; nhưng token nhóm cũ có thể khôi phục role vừa hạ trong DB. Response name, không có full_name/email_verified/status đề xuất. | `backend/app/dependencies.py:22`; `backend/app/services/auth_service.py:179`; `backend/app/schemas/auth.py:23`; `Q01–Q03`; contract:46; runtime/OpenAPI: có |
| 5 | PATCH | `/users/me` | Profile | **PROPOSED** | Path chưa có; đã có PATCH /auth/me nhận name. Cần chốt alias/version và đồng bộ Cognito name, không tạo API trùng theo suy đoán. | `backend/app/api/auth.py:79`; `docs/api-contract.md:237`; contract:47; runtime/OpenAPI: không |
| 6 | GET | `/courses` | Course | **PARTIAL** | Catalog chỉ PUBLISHED; không có q/page/limit/filter ở chữ ký route. Chưa có test chức năng catalog/SQL và lọc theo UI đủ điều kiện nghiệm thu: UNVERIFIED. | `backend/app/api/courses.py:49`; `backend/app/repositories/courses_repo.py:55`; contract:48; runtime/OpenAPI: có |
| 7 | GET | `/courses/{course_id}` | Course | **PARTIAL** | Course published nhưng outline trả cả tiêu đề/id/position/duration của lesson DRAFT; không phải lộ transcript qua response này. Q04 tái hiện. | `backend/app/services/course_service.py:29`; `backend/app/repositories/lessons_repo.py:39`; `backend/app/schemas/course.py:44`; `Q04`; contract:49; runtime/OpenAPI: có |
| 8 | POST | `/courses` | Course | **PARTIAL** | Có gán owner từ identity và DRAFT server-side, cover base64 được validate; thiếu test CRUD/persistence/role-negative riêng, title chỉ min_length và chưa trim. PostgreSQL UNVERIFIED. | `backend/app/api/courses.py:32`; `backend/app/services/course_service.py:11`; `backend/app/schemas/course.py:27`; contract:50; runtime/OpenAPI: có |
| 9 | PATCH | `/courses/{course_id}` | Course | **PARTIAL** | Owner query và whitelist metadata có; không nhận publish trực tiếp. Thiếu test HTTP/SQL update, rollback/duplicate/blank title; PostgreSQL UNVERIFIED. | `backend/app/services/course_service.py:52`; `backend/app/repositories/courses_repo.py:94`; contract:51; runtime/OpenAPI: có |
| 10 | POST | `/courses/{course_id}/publish` | Course | **PARTIAL** | Có khóa row/owner và kiểm lesson PUBLISHED + nội dung; thiếu kiểm processed video/quiz approval. Q25 publish thành công khi video key NULL; các test publish cũ chưa xanh. | `backend/app/services/course_service.py:87`; `backend/app/services/review_service.py:36`; `Q25`; contract:52; runtime/OpenAPI: có |
| 11 | POST | `/courses/{course_id}/unpublish` | Course | **PROPOSED** | DECISION chưa khóa trong v6; không có route. Phải chốt enrollment/progress/video replacement trước khi triển khai; không tính như API chắc chắn bị bỏ sót. | `docs/api-contract.md:332`; `docs/api-contract.md:737`; contract:53; runtime/OpenAPI: không |
| 12 | GET | `/instructor/courses` | Course | **PARTIAL** | Đã có, lọc theo owner và gồm DRAFT. Response list/raw detail khác mẫu items của v6; chưa có search/filter/page và kiểm thử riêng của read model: UNVERIFIED. | `backend/app/api/screen_workflows.py:25`; `backend/app/services/screen_workflows.py:30`; contract:54; runtime/OpenAPI: có |
| 13 | GET | `/instructor/courses/{course_id}` | Course | **PARTIAL** | Đã có owner-only 404 và cấu trúc draft. Thiếu publish-readiness/missing-items, DTO response cụ thể và kiểm thử own/other owner: UNVERIFIED. | `backend/app/api/screen_workflows.py:29`; `backend/app/services/screen_workflows.py:14`; contract:55; runtime/OpenAPI: có |
| 14 | GET | `/students/me/courses` | Course | **PARTIAL** | Đã có, không còn MISSING. Hai test hiện có chỉ kiểm role và mock service shape; tính tiến độ/completion/resume thật chưa được test bao phủ, phụ thuộc progress lỗi. | `backend/app/api/enrollments.py:13`; `backend/app/services/enrollment_service.py:27`; `backend/tests/unit/test_enrollment_list.py:18`; `Q18–Q21`; contract:56; runtime/OpenAPI: có |
| 15 | POST | `/courses/{course_id}/sections` | Section | **PARTIAL** | Có JWT Instructor, owner, title trim, unique position và map 409. Chưa có test chức năng create/duplicate/rollback trên source này: UNVERIFIED PostgreSQL. | `backend/app/api/sections.py:13`; `backend/app/services/section_service.py:19`; `backend/app/repositories/sections_repo.py:10`; contract:57; runtime/OpenAPI: có |
| 16 | GET | `/courses/{course_id}/sections` | Section | **PARTIAL** | Có identity, hạn role, owner xem draft/nonowner chỉ published. Chỉ là outline; cần khóa rõ outline vs quyền học/enrollment trong contract và test negative; chưa kiểm chứng riêng. | `backend/app/api/sections.py:45`; `backend/app/services/section_service.py:35`; contract:58; runtime/OpenAPI: có |
| 17 | POST | `/sections/{section_id}/lessons` | Lesson | **PARTIAL** | Có owner, tạo DRAFT và trim title. Unique position vi phạm trả 500 thay vì 409 (Q28); cần kiểm concurrent/transaction và PostgreSQL. | `backend/app/api/lessons.py:82`; `backend/app/services/lesson_service.py:156`; `backend/app/repositories/lessons_repo.py:72`; `Q28`; contract:59; runtime/OpenAPI: có |
| 18 | GET | `/sections/{section_id}/lessons` | Lesson | **PARTIAL** | Có publish/enrollment và lọc lesson PUBLISHED; thiếu section unlock. Student gọi section 2 đang khóa vẫn HTTP 200. | `backend/app/services/lesson_service.py:255`; `backend/app/services/lesson_service.py:181`; `Q06`; contract:60; runtime/OpenAPI: có |
| 19 | GET | `/lessons/{lesson_id}` | Lesson | **PARTIAL** | Có owner/published/enrollment nhưng thiếu unlock. DTO chỉ metadata, transcript/summary qua /content ngoài bảng contract; Q05/Q07 xác nhận truy cập section locked. | `backend/app/api/lessons.py:110`; `backend/app/services/lesson_service.py:199`; `backend/app/schemas/lesson.py:17`; `Q05/Q07`; contract:61; runtime/OpenAPI: có |
| 20 | PATCH | `/lessons/{lesson_id}` | Lesson | **PARTIAL** | Chỉ owner và whitelist title/position; chưa có test update/position collision, map IntegrityError và tác động reorder khóa học đã publish: UNVERIFIED. | `backend/app/api/lessons.py:233`; `backend/app/services/lesson_service.py:231`; contract:62; runtime/OpenAPI: có |
| 21 | POST | `/courses/{course_id}/enroll` | Enrollment | **PARTIAL** | Có Student-only, published, chống trùng bằng unique và 409, repo rollback. Thiếu test HTTP+DB cho enroll thành công/trùng/draft/concurrency; không có enrollment ACTIVE/cancel state để kiểm v6. | `backend/app/api/enrollments.py:31`; `backend/app/services/enrollment_service.py:135`; `backend/app/models/enrollment.py:9`; contract:63; runtime/OpenAPI: có |
| 22 | PUT | `/lessons/{lesson_id}/progress` | Progress | **PARTIAL** | Thiếu publish/unlock; tin ranges tùy ý, completed ngưỡng 10%, không lưu resume/ranges, ghi đè watched_seconds. Payload FE có session/sequence/request_id bị 422. | `backend/app/api/progress.py:39`; `backend/app/schemas/learning.py:21`; `backend/app/models/progress.py:16`; `Q18/Q20/Q21/Q27`; contract:64; runtime/OpenAPI: có |
| 23 | GET | `/courses/{course_id}/progress` | Progress | **PARTIAL** | Có kiểm enrollment nhưng không reject course DRAFT; resume=0/ranges=[] sau reload, overall theo lesson.completed 10%, không phải completion checkpoint; Q19/Q20. | `backend/app/api/progress.py:90`; `backend/app/services/screen_workflows.py:104`; `Q19/Q20`; contract:65; runtime/OpenAPI: có |
| 24 | GET | `/students/me/progress` | Progress | **PROPOSED** | Path chưa có; GET /students/me/learning-overview + checkpoint-history là phương án đã code nhưng chưa được contract ghi nhận; không mặc định tương đương schema. | `backend/app/api/screen_workflows.py:76`; `backend/app/services/screen_workflows.py:136`; contract:66; runtime/OpenAPI: không |
| 25 | POST | `/lessons/{lesson_id}/upload-url` | Upload | **PARTIAL** | Owner, size ≤500 MiB, MIME/extension, presign; hỗ trợ cả webm/mov khác mặc định MP4 v6. Chỉ khi bật ledger mới bind upload DB; AWS pipeline/S3 thật UNVERIFIED. | `backend/app/api/uploads.py:29`; `backend/app/services/upload_service.py:13`; `backend/app/services/upload_service.py:72`; `backend/tests/unit/test_video_pipeline.py:434`; contract:67; runtime/OpenAPI: có |
| 26 | POST | `/lessons/{lesson_id}/confirm-upload` | Upload | **PROPOSED** | DECISION chưa chọn confirm; path không có. Ledger/event claim có binding/HeadObject/dedup, cần chốt event-only và ghi tài liệu; không tự coi thiếu confirm là pipeline hỏng. | `backend/app/services/video_pipeline_service.py:105`; `docs/api-contract.md:433`; contract:68; runtime/OpenAPI: không |
| 27 | GET | `/lessons/{lesson_id}/video-url` | Video | **PARTIAL** | Processed-only production, no-store, S3 Head/presign/error mapping có; thiếu unlock nên vẫn gọi signer cho section locked (Q09). S3 thật UNVERIFIED; 27 test video hiện thất bại. | `backend/app/services/lesson_service.py:94`; `backend/app/adapters/storage/s3_storage.py:28`; `Q09`; contract:69; runtime/OpenAPI: có |
| 28 | GET | `/lessons/{lesson_id}/processing-status` | Processing | **PARTIAL** | Có owner-only đọc trạng thái thật, no-store và che lỗi nhạy cảm. Nhiều test HTTP cũ dùng X-Demo-User không còn hợp lệ; E2E trạng thái PostgreSQL/AWS UNVERIFIED. | `backend/app/api/lessons.py:20`; `backend/app/services/processing_service.py:54`; `backend/tests/integration/test_video_processing_db.py:24`; contract:70; runtime/OpenAPI: có |
| 29 | POST | `/lessons/{lesson_id}/retry` | Processing | **PARTIAL** | Có FAILED-only, lock, chống retry kép, rollback/outbox và ngoại lệ ADMIN. Policy Admin chưa chốt; unit ledger đạt nhưng dispatch/recovery AWS và PostgreSQL thật UNVERIFIED. | `backend/app/services/processing_service.py:89`; `backend/app/services/video_pipeline_service.py:304`; `backend/tests/unit/test_video_pipeline.py:291`; contract:71; runtime/OpenAPI: có |
| 30 | POST | `/lessons/{lesson_id}/review-drafts` | AI Review | **PARTIAL** | Sinh AI draft + flashcards từ concepts và ghi atomic; mock/adapter tests đạt. Không bảo toàn timestamp khi thay transcript bằng text; 2 options được chấp nhận; Bedrock thật UNVERIFIED. | `backend/app/services/review_service.py:152`; `backend/app/schemas/review.py:42`; `backend/tests/unit/test_review_service.py:76`; `Q29`; contract:72; runtime/OpenAPI: có |
| 31 | GET | `/lessons/{lesson_id}/review-draft` | AI Review | **PARTIAL** | Owner/revision/flashcards đã có và service tests đạt. Không có nguồn timestamp/chunk trong question/concept/card DTO như luồng review mục tiêu; PostgreSQL/E2E UNVERIFIED. | `backend/app/api/review.py:103`; `backend/app/services/review_service.py:80`; `backend/app/schemas/review.py:24`; `backend/tests/unit/test_review_service.py:102`; contract:73; runtime/OpenAPI: có |
| 32 | PUT | `/lessons/{lesson_id}/review-draft` | AI Review | **PARTIAL** | PUT đầy đủ có expected_revision, validate/rollback và flashcards. Source timestamps/4 options chưa đủ; không được suy từ test 2 options pass thành đáp ứng v6. | `backend/app/api/review.py:126`; `backend/app/services/review_service.py:198`; `backend/app/repositories/review_repo.py:155`; `Q29`; contract:74; runtime/OpenAPI: có |
| 33 | POST | `/lessons/{lesson_id}/review-draft/approvals` | AI Review | **PARTIAL** | Revision và ownership có, nhưng dùng cùng approve_draft thiếu guard processed video/điều kiện nội dung tin cậy; có thể publish lesson thiếu video. | `backend/app/api/review.py:151`; `backend/app/services/review_service.py:228`; `backend/app/repositories/review_repo.py:211`; `Q24`; contract:75; runtime/OpenAPI: có |
| 34 | GET | `/lessons/{lesson_id}/ai-content` | AI Review | **PARTIAL** | Có response draft + transcript và kiểm owner; transcript không luôn có timestamp, DTO nguồn học liệu chưa đầy đủ. GET trả dict, schema response OpenAPI thiếu độ cụ thể. | `backend/app/api/review.py:177`; `backend/app/services/review_service.py:193`; contract:76; runtime/OpenAPI: có |
| 35 | PATCH | `/lessons/{lesson_id}/ai-content` | AI Review | **PARTIAL** | Lỗi dữ liệu: whitelist bỏ flashcards, values thiếu trường này nên DraftUpdate mặc định []; PATCH summary xóa toàn bộ 3 flashcards (Q23). Gửi flashcards trực tiếp bị 422. | `backend/app/api/review.py:225`; `backend/app/schemas/review.py:76`; `backend/app/repositories/review_repo.py:183`; `Q23`; contract:77; runtime/OpenAPI: có |
| 36 | POST | `/lessons/{lesson_id}/approve` | AI Review | **PARTIAL** | Alias dùng chung approve_draft; HTTP 200/PUBLISHED dù processed_video_key=NULL. Chưa đủ điều kiện approve/publish v6; approval tests 20 lỗi setup, không phải đã nghiệm thu. | `backend/app/api/review.py:240`; `backend/app/services/review_service.py:228`; `Q24`; contract:78; runtime/OpenAPI: có |
| 37 | GET | `/instructor/review-queue` | AI Review | **PARTIAL** | Đã có nhưng đăng ký 2 handler khác nhau; runtime screen_workflows không trả PUBLISHED, thiếu query lọc/phân trang. OpenAPI mô tả handler review đăng ký sau. | `backend/app/main.py:55`; `backend/app/api/screen_workflows.py:37`; `backend/app/api/review.py:24`; `backend/app/services/screen_workflows.py:35`; contract:79; runtime/OpenAPI: có |
| 38 | GET | `/instructor/courses/{course_id}/publish-readiness` | AI Review | **PROPOSED** | Chưa có path; có thể mở rộng owner course detail thay vì route mới. Hiện detail chưa trả can_publish/missing_items/approved count. | `docs/api-contract.md:508`; `backend/app/services/screen_workflows.py:14`; contract:80; runtime/OpenAPI: không |
| 39 | GET | `/sections/{section_id}/flashcards` | Flashcard | **PROPOSED** | Chưa có section path; đã có lesson-scoped flashcards. Cần chốt mapping/aggregation và bảo vệ unlock, không ghi Flashcard toàn module là chưa code. | `backend/app/api/flashcards.py:49`; `docs/api-contract.md:546`; `Q08`; contract:81; runtime/OpenAPI: không |
| 40 | POST | `/flashcards/{flashcard_id}/reviews` | Flashcard | **PROPOSED** | Chưa có endpoint hoặc model/repository lưu remembered/needs-review theo Student. LocalStorage UI không phải PostgreSQL persistence. | `backend/app/models/flashcard.py:17`; `docs/api-contract.md:563`; contract:82; runtime/OpenAPI: không |
| 41 | GET | `/courses/{course_id}/flashcards` | Flashcard | **PROPOSED** | Chưa có course aggregate; phụ thuộc phương án section/lesson và chính sách chỉ các section unlocked. | `docs/api-contract.md:548`; `backend/app/api/flashcards.py:49`; contract:83; runtime/OpenAPI: không |
| 42 | GET | `/sections/{section_id}/quiz` | Quiz | **PARTIAL** | GET checkpoint mới đã kiểm enrollment/published/approved/previous sections/lesson completion, che đáp án, tests đạt. Chưa khóa schema/options=4, dữ liệu cũ 2 options vẫn hợp lệ; PostgreSQL concurrency UNVERIFIED. | `backend/app/services/quiz_service.py:62`; `backend/app/services/quiz_service.py:116`; `backend/tests/unit/test_checkpoint_backend.py:87`; `Q11/Q12/Q29`; contract:84; runtime/OpenAPI: có |
| 43 | POST | `/quizzes/{quiz_id}/attempts` | Quiz | **PARTIAL** | Chấm server, bỏ trống tính sai, UUID idempotency, transaction và chặn <50% đã test. Response results=null, thiếu explanation/band theo UI; Tutor legacy không mở guard; 2 test legacy/schema thất bại. | `backend/app/services/quiz_service.py:291`; `backend/app/services/quiz_service.py:212`; `backend/app/schemas/quiz.py:210`; `Q13/Q16`; contract:85; runtime/OpenAPI: có |
| 44 | GET | `/student/quizzes/history` | Quiz | **PARTIAL** | Own-student query và pagination/title có, test service mapping đạt. Chưa có HTTP own-only/filter/course scope và PostgreSQL integration đủ bằng chứng; giữ PARTIAL thay vì suy từ schema. | `backend/app/api/quizzes.py:86`; `backend/app/services/quiz_service.py:588`; `backend/app/repositories/quizzes_repo.py:453`; `backend/tests/unit/test_quiz_service.py:141`; contract:86; runtime/OpenAPI: có |
| 45 | GET | `/courses/{course_id}/unlock-status` | Unlock | **PARTIAL** | Tính chuỗi mở khóa có test; endpoint không kiểm course published/enrollment, không có 404 course thiếu, quy tắc no-quiz khác checkpoint. Q10 student chưa enroll vẫn 200. | `backend/app/services/unlock_service.py:77`; `backend/app/repositories/quizzes_repo.py:385`; `Q10`; contract:87; runtime/OpenAPI: có |
| 46 | POST | `/tutor/sessions` | AI Tutor | **PARTIAL** | Có session/messages/practice persistence và owner/enrollment/published attempt. Body thực attempt_id, response id/explanation/practice; không tạo workflow_state/steps/references/quota như v6, không tự nối retry state. | `backend/app/api/tutor.py:22`; `backend/app/services/tutor_service.py:81`; `backend/app/repositories/tutor_repo.py:11`; `Q14/Q16`; contract:88; runtime/OpenAPI: có |
| 47 | POST | `/tutor/sessions/{session_id}/messages` | AI Tutor | **PARTIAL** | Owner/course/lesson/enrollment được kiểm; trả trích đoạn keyword từ transcript, không phải hội thoại Bedrock ở handler này. Không quota/token usage; grounded timestamp test đạt, AI thật UNVERIFIED. | `backend/app/services/tutor_service.py:125`; `backend/app/repositories/tutor_repo.py:37`; `backend/tests/unit/test_week4_tutor_analytics.py:191`; contract:89; runtime/OpenAPI: có |
| 48 | POST | `/tutor/sessions/{session_id}/practice-attempts` | AI Tutor | **PARTIAL** | Session tạo bởi /tutor/sessions dùng all-correct, 2/3 bị false; 3/3 chỉ cập nhật TutorSession, checkpoint can_retry vẫn false. Nhánh workflow_state mới khác và đã test đạt 2/3. | `backend/app/services/tutor_service.py:156`; `backend/app/repositories/tutor_repo.py:88`; `backend/app/services/quiz_service.py:100`; `Q15–Q17`; contract:90; runtime/OpenAPI: có |
| 49 | GET | `/tutor/sessions/{session_id}` | AI Tutor | **PROPOSED** | Path chưa có; GET /student/remediation/{session_id} đã hỗ trợ resume cho workflow mới. Cần chốt alias/schema thay vì dựng thêm hệ thống session. | `backend/app/api/screen_workflows.py:63`; `backend/app/services/remediation_service.py:20`; contract:91; runtime/OpenAPI: không |
| 50 | GET | `/instructor/dashboard` | Analytics | **PARTIAL** | Đã có; runtime tính owner-scoped metrics nhưng trùng handler analytics, shape/count lesson khác OpenAPI. Thiếu regression dashboard thực và tỷ lệ/định nghĩa dữ liệu thống nhất. | `backend/app/api/screen_workflows.py:33`; `backend/app/services/screen_workflows.py:43`; `backend/app/api/analytics.py:18`; contract:92; runtime/OpenAPI: có |
| 51 | GET | `/instructor/courses/{course_id}/analytics` | Analytics | **PARTIAL** | Owner, enrolled/attempt/pass/average/completion/errors có và SQLite tests đạt. Không có tutor_usage theo yêu cầu tối thiểu; completion dựa trên progress lỗi, không thay cho student detail. | `backend/app/services/analytics_service.py:7`; `backend/app/repositories/analytics_repo.py:18`; `backend/tests/unit/test_week4_tutor_analytics.py:61`; contract:93; runtime/OpenAPI: có |
| 52 | GET | `/instructor/courses/{course_id}/students` | Analytics | **PROPOSED** | Course-scoped path chưa có. GET /instructor/students tổng hợp nhiều course không tương đương; thiếu filter theo course/điểm mới nhất/tutor. Có lỗi với course DRAFT trong read model. | `backend/app/api/screen_workflows.py:41`; `backend/app/services/screen_workflows.py:58`; contract:94; runtime/OpenAPI: không |
| 53 | GET | `/instructor/courses/{course_id}/students/{student_id}/analytics` | Analytics | **PROPOSED** | Course+student-scoped path chưa có. GET /instructor/students/{id} thay thế hiện HTTP 500 KeyError progress_percent và attempt_count không giới hạn course. | `backend/app/services/screen_workflows.py:78`; `backend/app/services/screen_workflows.py:119`; `Q22`; contract:95; runtime/OpenAPI: không |
| 54 | GET | `/admin/users` | Admin | **PARTIAL** | Đã có require_admin + search. Không role/status filter/page/limit; model User không có active/status, không audit; thiếu functional admin list tests. | `backend/app/api/admin.py:21`; `backend/app/models/user.py:6`; contract:96; runtime/OpenAPI: có |
| 55 | POST | `/admin/users` | Admin | **PARTIAL** | Đã có Cognito provisioning + DB record; cho cả STUDENT, bắt password, SUPPRESS invitation và Permanent=True, khác invite/đổi password lần đầu v6. Thiếu compensate/idempotency/audit và AWS test. | `backend/app/api/admin.py:36`; `backend/app/services/auth_service.py:347`; `backend/app/schemas/auth.py:33`; contract:97; runtime/OpenAPI: có |
| 56 | PATCH | `/admin/users/{user_id}` | Admin | **PARTIAL** | Có Admin-only update name/email/role, gọi Cognito rồi commit DB. Không khóa account/revoke/audit/last-admin guard; Q26 hạ Admin cuối thành Student, Q03 token cũ phục hồi role. | `backend/app/api/admin.py:68`; `backend/app/services/auth_service.py:396`; `backend/app/models/user.py:6`; `Q03/Q26`; contract:98; runtime/OpenAPI: có |
| 57 | POST | `/admin/users/{user_id}/reset-password` | Admin | **MISSING** | Không có admin reset-password route/helper được gọi. Public forgot/reset-password không tương đương administrative reset/invite; cần triển khai đúng policy đã chốt. | `backend/app/api/admin.py:18`; `backend/app/api/auth.py:54`; `docs/api-contract.md:240`; contract:99; runtime/OpenAPI: không |
| 58 | GET | `/admin/operations/summary` | Admin | **PROPOSED** | Chưa có metrics summary. /admin/monitoring/jobs là list ledger, không có cost/AI usage/CloudWatch summary. | `backend/app/api/admin.py:124`; `docs/api-contract.md:696`; contract:100; runtime/OpenAPI: không |
| 59 | GET | `/admin/operations/jobs` | Admin | **PROPOSED** | Chưa có exact operations path. /admin/monitoring/jobs có tối đa 50 run, chưa pagination/filter và chưa phải CloudWatch monitoring đầy đủ. | `backend/app/api/admin.py:124`; `docs/api-contract.md:697`; contract:101; runtime/OpenAPI: không |
| 60 | GET | `/admin/operations/jobs/{job_id}` | Admin | **PROPOSED** | Chưa có job-detail/log route, CloudWatch link/redaction/detail stage. AWS readiness và quyền đọc log UNVERIFIED. | `docs/api-contract.md:698`; `backend/app/api/admin.py:124`; contract:102; runtime/OpenAPI: không |

## 5. API source có nhưng chưa ghi trong bảng 60 API

**24 cặp unique**, đã loại trùng registrations. Một số phục vụ chức năng đã nêu trong phần mô tả v6 nhưng **exact method/path chưa được ghi**; không đồng nhất “ngoài contract” với “không cần thiết”.

| STT | Method + path | Đánh giá và khoảng trống | Bằng chứng |
|---:|---|---|---|
| 1 | `GET /instructor/students` | PARTIAL — đa course, không phải list course #52; completion() chỉ nhận course published; thiếu filter/page/last score. | `backend/app/api/screen_workflows.py:41`; `backend/app/api/analytics.py:88` |
| 2 | `GET /instructor/students/{student_id}` | PARTIAL — runtime 500 (Q22), thiếu progress_percent và số liệu tutor/weak concepts là placeholder; attempt_count ngoài course scope. | `backend/app/api/screen_workflows.py:45`; `backend/app/api/analytics.py:131` |
| 3 | `GET /students/me/checkpoint-history` | PARTIAL — own-student join course/section có; chưa có test HTTP/SQL riêng và schema response; UNVERIFIED. | `backend/app/api/screen_workflows.py:50` |
| 4 | `GET /courses/{course_id}/completion` | PARTIAL — có kiểm enrolled+published và all lesson/all quiz; khác overall của progress, chưa có regression riêng. | `backend/app/api/screen_workflows.py:55` |
| 5 | `POST /student/remediation` | PARTIAL — tạo workflow resumable/idempotent, 2–3 câu; chưa thống nhất với Tutor contract/quota; Q17 chỉ kiểm một nhánh 2/3. | `backend/app/api/screen_workflows.py:59` |
| 6 | `GET /student/remediation/{session_id}` | PARTIAL — resume workflow có ownership/enrollment/publication; chưa thay thế contract #49 một cách được chốt. | `backend/app/api/screen_workflows.py:63` |
| 7 | `POST /student/remediation/{session_id}/advance` | PARTIAL — có order/item membership, ghi state; chỉ xác nhận hành động card/explanation, không chứng minh video đã xem. | `backend/app/api/screen_workflows.py:67` |
| 8 | `POST /student/remediation/{session_id}/practice` | PARTIAL — Q17 xác minh 2/3 và retry state; quota/regen/1-of-3/cross-session/cross-attempt đầy đủ UNVERIFIED. | `backend/app/api/screen_workflows.py:71` |
| 9 | `GET /students/me/learning-overview` | PARTIAL — alternative #24; aggregate published course có, công thức progress chưa thống nhất. | `backend/app/api/screen_workflows.py:76` |
| 10 | `GET /lessons/{lesson_id}/content` | PARTIAL — 2 handler, runtime dùng transcript dict/segments còn OpenAPI handler khác; thiếu unlock (Q07). | `backend/app/api/screen_workflows.py:81`; `backend/app/api/lessons.py:134` |
| 11 | `POST /auth/verify-email` | PARTIAL — proxy confirm_sign_up/admin_get_user/DB mapping, không phải OTP local; Cognito/DB atomic failure UNVERIFIED. | `backend/app/api/auth.py:38` |
| 12 | `POST /auth/resend-verification` | PARTIAL — Cognito proxy, retry_after không phải rate limiter backend; AWS UNVERIFIED. | `backend/app/api/auth.py:46` |
| 13 | `POST /auth/forgot-password` | PARTIAL — proxy Cognito, normalize UserNotFound; chưa kiểm quota/AWS thật. | `backend/app/api/auth.py:54` |
| 14 | `POST /auth/reset-password` | PARTIAL — proxy confirm_forgot_password; không thay admin reset #57; AWS UNVERIFIED. | `backend/app/api/auth.py:62` |
| 15 | `PATCH /auth/me` | PARTIAL — update name trong DB, chưa đồng bộ Cognito attributes; alias #5 cần chốt. | `backend/app/api/auth.py:79` |
| 16 | `POST /auth/change-password` | PARTIAL — truyền Bearer cho Cognito change_password; dịch vụ ngoài xác minh token, AWS UNVERIFIED. | `backend/app/api/auth.py:91` |
| 17 | `GET /quizzes/{quiz_id}/attempts` | PARTIAL — own-student history + access gate; test checkpoint HTTP/history đạt, response results/explanation còn thiếu. | `backend/app/api/quizzes.py:66` |
| 18 | `GET /courses/instructor/me` | PARTIAL — owner courses alias #12, schema CourseResponse không có lesson status như management detail; cần chọn API chuẩn. | `backend/app/api/courses.py:54` |
| 19 | `GET /admin/monitoring/jobs` | PARTIAL — Admin-only list 50 ledger runs; thiếu summary/log detail/cost/CloudWatch và pagination. | `backend/app/api/admin.py:124` |
| 20 | `POST /lessons/{lesson_id}/viewing-sessions` | PARTIAL — chỉ sinh UUID, không lưu/bind/expire phiên; không có publish/unlock; request progress không nhận ID này. | `backend/app/api/progress.py:18` |
| 21 | `GET /lessons/{lesson_id}/flashcards` | PARTIAL — approved/published/enrolled có, unlock thiếu (Q08); không có remembered state. | `backend/app/api/flashcards.py:49` |
| 22 | `POST /lessons/{lesson_id}/flashcards` | PARTIAL — owner Instructor hoặc Admin (Admin mọi course lệch v6), ghi DB nhưng chưa đủ test/approval versioning. | `backend/app/api/flashcards.py:112` |
| 23 | `PUT /lessons/{lesson_id}/flashcards/{card_id}` | PARTIAL — Q31 Admin sửa mọi course, Q32 Student từng là owner sửa/approve được; không có role guard tương đương POST. | `backend/app/api/flashcards.py:139` |
| 24 | `DELETE /lessons/{lesson_id}/flashcards/{card_id}` | PARTIAL — dùng cùng _owned_context, thiếu role guard; không kiểm review status/version. Static; DELETE-specific UNVERIFIED. | `backend/app/api/flashcards.py:165` |

Cần chốt đường API chuẩn cho profile, history, flashcards, instructor list/detail, monitoring và remediation; thêm alias/version chỉ sau đánh giá tương thích. **Không đề xuất dựng thêm API nếu route hoặc dữ liệu tương đương đã có và có thể mở rộng an toàn.**

## 6. Phân tách FastAPI, Cognito và AWS

| Chức năng | Nơi thực thi thực tế | Kết luận kiểm toán |
|---|---|---|
| Đăng nhập/lấy/refresh token/logout | Amplify Cognito SDK, `frontend/src/api/cognito.js:73/56/123` | EXTERNAL; POST /auth/login MISSING trong ma trận là route bị bỏ chủ ý, không phải đề nghị viết lại login local. Pool/flows thật UNVERIFIED. |
| Signup Student | FastAPI POST /auth/register → Cognito sign_up | Wrapper là FastAPI và nằm trong 60; identity/password do Cognito. Schema không nhận role tùy chọn. |
| OTP signup/resend/forgot/reset/change password | Các wrapper /auth/* → Cognito SDK backend | Source đã chọn proxy thay hướng FE SDK trực tiếp trong v6. Đây là API ngoài bảng contract, không thiếu OTP local. AWS thật UNVERIFIED. |
| JWT/API identity | FastAPI JWKS RS256 hoặc claims từ API Gateway authorizer event | Local signed-token checks đạt Q02. Authorizer deployment/trust boundary/revocation thật UNVERIFIED. Role sync có bug Q03. |
| Admin tạo/sửa identity | FastAPI Admin → Cognito → PostgreSQL | Chưa có atomic compensation/idempotency/audit, permanent password khác invite tạm; không coi Cognito admin feature là đã đủ Backend endpoint. |
| Upload bytes | Browser PUT presigned URL vào S3 | **Không** đếm PUT presigned URL là FastAPI operation. Backend cấp URL; nguồn dispatch đã có ledger/event claim nhưng cần chốt D07. |
| Transcode/transcribe/AI | EventBridge/Step Functions/Lambda/MediaConvert/Transcribe/Bedrock | Internal workers/adapters không phải HTTP router FastAPI. Unit ledger/dedup đạt; end-to-end AWS, IAM, trigger và AI worker thật UNVERIFIED. |
| Playback | FastAPI GET video-url → S3 Head/presigned GET | Backend guard vẫn thiếu unlock; response signer mock không chứng minh phát video/Range 206 trên S3 thật. |
| Monitor/log/cost | Hiện FastAPI chỉ có /admin/monitoring/jobs đọc DB ledger | CloudWatch logs/job detail/cost/AI usage chưa có contract implementation đầy đủ. |

## 7. Kiểm toán nghiệp vụ, dữ liệu và bảo mật theo module

| Module | Request/response | Dữ liệu/persistence | Auth/role/ownership và trạng thái | Lỗi/test và kết luận |
|---|---|---|---|---|
| Auth/Profile | name thay full_name; thiếu email_verified/status; signup đổi sang Cognito; /users/me alias chưa có | sync sub/email/name/role commit DB; profile PATCH chỉ đổi DB name | Không còn demo identity; RS256 các claim chính đạt. Group token cũ ghi đè role DB; không có User active/revoked state | 7 auth tests đạt + Q01–Q03. JWKS thật/token revoke/User Pool UNVERIFIED; source `auth_service.py:164–194/206`. |
| Course | Public list không filter/page; detail chỉ outline nhưng không lọc draft lesson; cover base64 đã có | ORM courses/sections/lessons, owner-scoped updates, publish row locks | Instructor owner có; publish chỉ kiểm lesson status + JSON/text presence, không processed video hoặc quiz approval | Q04/Q25; nhiều test publish cũ không vào logic do auth setup. CRUD/PG concurrency UNVERIFIED. |
| Section/Lesson | DTO LessonResponse chỉ id/section/title/position; content extra endpoint có transcript | ORM create/update rollback; unique position ở DB | Publish/enrollment có; **unlock không có** ở lesson list/detail/content/playback; owner-only write | Q05–Q09/Q28; lỗi duplicate lesson 500 thay 409. Static `lesson_service.py:181–213/255`. |
| Enrollment | List MyCourseEnrollmentResponse khác mẫu items v6; 201/409 enroll | Unique (student,course), repo commit/rollback; chưa có ACTIVE state | Student-only và published kiểm tại service | 2 list tests mock shape/role, không đủ chứng minh enrollment DB flow. Source `enrollment_service.py:135`, PG UNVERIFIED. |
| Upload/Processing | Request filename/content_type/file_size; có chế độ legacy vs ledger, no response DTO upload cụ thể | Ledger VideoUpload/VideoPipelineRun có schema/unique/composite FK; event binding/HeadObject/race fences | Owner; pipeline upload chỉ DRAFT khi bật flag. Retry FAILED-only, Admin là exception pending policy | 37 pipeline unit + 4 migration tests đạt; nhiều HTTP tests cũ 401. AWS/RDS/trigger readiness UNVERIFIED. |
| AI Review | Draft PUT hỗ trợ flashcards, PATCH whitelist không hỗ trợ và xóa; 2 options, không source timestamps | Atomic replace/lock section/revision; quiz dùng chung một section; regenerate bị chặn khi có attempts | Role+owner+revision có; approve không kiểm processed video/required video; không có guard trạng thái đầy đủ trước approve | 31 review tests đạt **không phủ các lỗi Q23/Q24/Q29**; 20 approval tests lỗi patch target. `review_repo.py:155/211`. |
| Quiz/Unlock | UUID request_id và selected_answer khác mẫu proposed; results=null, thiếu explanation/band ở actual submit | Attempt+answers atomic/idempotent; thấp <50 tạo CheckpointRemediation; SQL lock compile có | Checkpoint mới kiểm enrollment/published/approved/prior sections/completed lesson; unlock-status standalone chưa check course/enroll | 11 checkpoint tests đạt; 2 legacy/schema tests lỗi + 1 OpenAPI test lệch status; Q10–Q13. PG locks/triggers UNVERIFIED. |
| AI Tutor/Remediation | /tutor nhận attempt_id; workflow /student/remediation có steps/result/resume riêng; không quota chuẩn | TutorSession/messages/practice JSON; legacy complete chỉ bool, workflow ghi CheckpointRemediation | Owner/enroll/published có. Legacy 2/3 false và 3/3 chưa mở retry; workflow mới 2/3 đạt | 8 Tutor/Analytics tests và Q14–Q17. Không có test repository riêng cho toàn workflow mới; Bedrock thật UNVERIFIED. |
| Progress | FE gửi playback_session_id/sequence/request_id bị DTO extra=forbid; GET resume=0/ranges=[] | Model chỉ watched_seconds/completed, không lưu ranges/resume/session; ghi đè thay hợp nhất | Student+enrollment có, không course/lesson publish/unlock; ranges vượt duration vẫn accepted, completed=10% | Q18–Q21/Q27. Không có service/repo progress: hai file rỗng, logic ở router. Không thể ghi DONE từ test schema alone. |
| Flashcard | Read/CRUD lesson khác paths section/course/review state v6 | Nội dung Flashcard có; không có learner remembered/review table | Student read thiếu unlock; Admin mọi course; PUT/DELETE thiếu role guard, Student former owner sửa và approve được | Q08/Q31/Q32. Review auto approves toàn cards; edit trực tiếp thiếu invalidate/revision policy. Functional standalone/PG tests UNVERIFIED. |
| Analytics | Owner metrics cơ bản; thiếu tutor_usage; global student alias khác per-course contract | Query enrolled/attempt/pass/completion/errors có; completion lệ thuộc progress 10%; detail placeholders | Own course aggregate có; student detail attempt_count không scope course, `completion` trả không có `progress_percent` | Q22 HTTP 500. Test analytics counts/ownership đạt nhưng không phủ dashboard/list/detail read models; `screen_workflows.py:78–93/104`. |
| Admin | List chỉ search; create yêu cầu password, cho STUDENT; không status/filter/page/reset | Gọi AWS rồi commit DB, không compensation/audit; User không is_active | require_admin có; last admin không bảo vệ, token cũ role rollback. Không có revoke/disable account | Q03/Q26, static `admin.py:36/68`, `auth_service.py:347/396`; Cognito admin functional tests UNVERIFIED. |

### 7.1. PostgreSQL/migration: blocker phát hành không được che bởi SQLite

1. Có **bốn file cùng version `0004`**, không chỉ hai như contract: `0004_add_lesson_approved_status.sql:66`, `0004_checkpoint_attempt_idempotency.sql:18`, `0004_cognito_auth_cutover.sql:6`, `0004_remove_approved_lesson_status.sql:24`.
2. Registry `schema_migrations.version` là PK (`database/schema.sql:166`). Script trong `database/migrations/README.md:122` skip theo version có thể ghi version đầu rồi **bỏ các thay đổi 0004 còn lại**. `0004_add...` còn từ chối description khác; `0005_video_pipeline_ledger.sql:23–33` yêu cầu chính xác description Remove approved. Vì vậy không thể tuyên bố chuỗi migrate hiện tại hội tụ đủ schema.
3. Bootstrap chưa có `courses.cover_image` và `tutor_sessions.workflow_state` (thêm ở `0006_screen_workflows.sql:3–4`); chưa có `practice_questions/remediation_completed` (legacy `V3__...:3–5`); chưa có request_id/hash/CheckpointRemediation (một nhánh 0004). Chỉ chạy `schema.sql` hoặc chỉ glob 0003+ có thể không đủ cho ORM hiện tại.
4. `APPROVED` còn trong `V2__allow_approved_lesson_status.sql:6` và `0004_add...`; source enum và remove migration không dùng APPROVED. Không suy version label là đủ; cần review constraint thực trên PostgreSQL test riêng.
5. README nói 0003 không có nhưng file `0003_reconcile_legacy_schema.sql` hiện đã có; tài liệu migration cũng cần cập nhật.
6. SQL có triggers kiểm role/consistency mà SQLite ORM fixture không tái tạo (`schema.sql:173–264`). DDL compile/SQLite FK pass không xác minh trigger chạy đúng hoặc FOR UPDATE/nowait thật.

**Trạng thái applied schema/RDS: UNVERIFIED.** Audit không chạy bất kỳ SQL migration nào. Nhiệm vụ tiếp theo là hợp nhất kế hoạch version rồi kiểm migration/rollback trên PostgreSQL cách ly do nhóm chuẩn bị; không chạy script “apply tất cả” lên production để thử.

### 7.2. Phân biệt lỗi HTTP/test cũ và lỗi nghiệp vụ đã xác minh

Error handlers đã thống nhất `detail/code/request_id`, che thông tin 5xx (`backend/app/utils/errors.py:112/205/222`); không còn đúng nhận định “chưa có chuẩn lỗi” của snapshot. Tuy vậy duplicate lesson vẫn map generic 500 (Q28), `detail` đôi khi là object cho Cognito và list validation; status documented trong OpenAPI chưa phủ mọi lỗi. Các test cần xác minh schema errors hiện tại.

Không sửa guard để làm các test X-Demo-User cũ xanh. Chúng cần fixture Bearer/JWT hoặc override identity rõ ràng; phải giữ test anti-impersonation độc lập.

## 8. Bằng chứng kiểm thử động

### 8.1. Test repository hiện có — lượt cuối

Cách chạy dùng Python cài sẵn làm pytest runner và chèn `.venv/Lib/site-packages` để lấy đúng dependencies Backend; không cài package, không sửa environment dự án. Không dùng `unittest discover` thay pytest vì sẽ bỏ các pytest function tests. Chạy `backend/tests/unit`, collect integration ở opt-in=0 và `ai_pipeline/tests`.

| File | Passed | Failed | Skipped |
|---|---:|---:|---:|
| `backend/tests/unit/test_ai_adapters.py` | 9 | 0 | 0 |
| `backend/tests/unit/test_auth_integration.py` | 7 | 0 | 0 |
| `backend/tests/unit/test_checkpoint_backend.py` | 11 | 0 | 0 |
| `backend/tests/unit/test_enrollment_list.py` | 2 | 0 | 0 |
| `backend/tests/unit/test_learning_contract.py` | 3 | 0 | 0 |
| `backend/tests/unit/test_lesson_approval.py` | 4 | 20 | 0 |
| `backend/tests/unit/test_lesson_video_url.py` | 6 | 27 | 0 |
| `backend/tests/unit/test_quiz_openapi.py` | 0 | 1 | 0 |
| `backend/tests/unit/test_quiz_service.py` | 3 | 2 | 0 |
| `backend/tests/unit/test_review_service.py` | 31 | 0 | 0 |
| `backend/tests/unit/test_unlock_service.py` | 4 | 0 | 0 |
| `backend/tests/unit/test_video_pipeline.py` | 37 | 0 | 0 |
| `backend/tests/unit/test_video_pipeline_migration.py` | 4 | 0 | 0 |
| `backend/tests/unit/test_video_processing.py` | 8 | 25 | 0 |
| `backend/tests/unit/test_week4_tutor_analytics.py` | 8 | 0 | 0 |
| `backend/tests/integration/test_video_pipeline_ledger_db.py` | 0 | 0 | 6 |
| `backend/tests/integration/test_video_processing_db.py` | 0 | 0 | 10 |
| `ai_pipeline/tests/test_processors.py` | 15 | 0 | 0 |
| `ai_pipeline/tests/test_processors_smoke.py` | 11 | 0 | 0 |
| `ai_pipeline/tests/test_tutor_context.py` | 2 | 0 | 0 |
| **Tổng (không cộng subtests lần hai)** | **165** | **75** | **16** |

26 subtests đạt được pytest liệt kê riêng. `backend/tests/integration/test_quiz_flow.py` rỗng, **không phải** integration coverage. Các test “PostgreSQL DDL/lock” hiện chỉ compile SQL, không kết nối PostgreSQL.

Nhóm lỗi 75: **20** approval setup patch `review_service.S3StorageAdapter` không tồn tại; **52** ở video URL/processing (phần lớn fixtures demo auth cũ trả 401 trước nghiệp vụ, thêm kỳ vọng identity/schema/log lỗi thời); **2** quiz legacy DTO/call signature; **1** OpenAPI quiz kỳ vọng response 400/schema cũ. Không gọi cả 75 là 75 lỗi logic độc lập. Các lỗi nghiệp vụ thật trong audit được tái hiện riêng ở Qxx dưới đây.

### 8.2. 32 kịch bản audit in-memory, không ghi source/test file

Q02 ký JWT bằng RSA key sinh local, **không mock jwt.decode**; chỉ giả lập JWKS key provider. Các business probes sau đó override current_user bằng User trong SQLite để cô lập nghiệp vụ, không được xem là full AWS-auth E2E. Q09 dùng signer mock; Q23/Q24 dùng MockAIAdapter; Q26 mock Cognito role/profile calls. Các fixture/ID/timestamp chỉ là dữ liệu giả.

“KHÔNG ĐẠT” nghĩa **kỳ vọng contract bị vi phạm và đã quan sát kết quả**, không phải probe bị crash. Q29 là validation probe tại schema Python; các Q khác qua ASGI HTTP, Q16/Q17 kiểm thêm service retry state trên cùng SQLite.

| ID | Kịch bản | Quan sát thực tế | Kết luận |
|---|---|---|---|
| Q01 | Thiếu token và giả mạo X-Demo-User | `[401,401]` | ĐẠT kịch bản hẹp |
| Q02 | JWT RS256 thật, chỉ JWKS được mock | `[200,401,401,401,401,401]` | ĐẠT kịch bản hẹp |
| Q03 | Group trong token cũ khôi phục role vừa hạ ở DB | `{"http":200,"db_role":"INSTRUCTOR"}` | KHÔNG ĐẠT yêu cầu |
| Q04 | Public outline có lesson DRAFT | `{"http":200,"draft_title_exposed":true}` | KHÔNG ĐẠT yêu cầu |
| Q05 | GET lesson section locked | `200` | KHÔNG ĐẠT yêu cầu |
| Q06 | GET lessons section locked | `200` | KHÔNG ĐẠT yêu cầu |
| Q07 | GET content section locked | `200` | KHÔNG ĐẠT yêu cầu |
| Q08 | GET flashcards section locked | `200` | KHÔNG ĐẠT yêu cầu |
| Q09 | GET video URL section locked, signer mock được gọi | `{"http":200,"adapter_calls":1}` | KHÔNG ĐẠT yêu cầu |
| Q10 | Student chưa enroll đọc unlock-status | `{"http":200,"body":[{"section_id":1,"is_unlocked":true},{"section_id":2,"is_unlocked":false}]}` | KHÔNG ĐẠT yêu cầu |
| Q11 | Student chưa enroll đọc checkpoint bị chặn | `403` | ĐẠT kịch bản hẹp |
| Q12 | Checkpoint hợp lệ không lộ đáp án/explanation | `{"http":200,"answer_leak":false}` | ĐẠT kịch bản hẹp |
| Q13 | Bỏ trống chấm 0 và chặn retry mức <50% | `{"http":200,"score":0,"results":null,"can_retry":false,"remediation_required":true}` | ĐẠT kịch bản hẹp |
| Q14 | Tutor legacy sinh 3 câu cho 3 lỗi | `{"http":201,"count":3}` | ĐẠT kịch bản hẹp |
| Q15 | Legacy practice đúng 2/3 | `{"correct":2,"total":3,"remediation_completed":false}` | KHÔNG ĐẠT yêu cầu |
| Q16 | Legacy practice đúng 3/3 nhưng checkpoint vẫn bị khóa | `{"legacy_complete":true,"checkpoint_can_retry":false}` | KHÔNG ĐẠT yêu cầu |
| Q17 | Workflow remediation mới đúng 2/3 sau đủ steps | `{"http":200,"correct":2,"total":3,"passed":true,"can_retry":true}` | ĐẠT kịch bản hẹp |
| Q18 | Ghi progress section locked với range vượt duration | `{"http":200,"body":{"last_position_seconds":100,"watched_seconds":100000,"watched_ranges":[[0,100000]],"completed":true}}` | KHÔNG ĐẠT yêu cầu |
| Q19 | GET progress course DRAFT | `200` | KHÔNG ĐẠT yêu cầu |
| Q20 | Resume/ranges mất sau reload | `{"lesson_id":1,"progress_percent":90,"completed":true,"last_position_seconds":0,"watched_seconds":90,"watched_ranges":[]}` | KHÔNG ĐẠT yêu cầu |
| Q21 | Progress từ 90 giây bị ghi đè còn 10 | `10` | KHÔNG ĐẠT yêu cầu |
| Q22 | Instructor student detail | `500` | KHÔNG ĐẠT yêu cầu |
| Q23 | PATCH summary làm mất flashcard | `{"http":200,"before":3,"after":0}` | KHÔNG ĐẠT yêu cầu |
| Q24 | Approve lesson processed_video_key=NULL | `{"http":200,"lesson_status":"PUBLISHED","processed_video_key":null}` | KHÔNG ĐẠT yêu cầu |
| Q25 | Publish course có lesson thiếu processed video | `{"http":200,"course_status":"PUBLISHED"}` | KHÔNG ĐẠT yêu cầu |
| Q26 | Admin cuối tự hạ role | `{"http":200,"role":"STUDENT"}` | KHÔNG ĐẠT yêu cầu |
| Q27 | Payload progress FE hiện tại có session/sequence/request_id | `422` | KHÔNG ĐẠT yêu cầu |
| Q28 | Tạo lesson trùng position | `500` | KHÔNG ĐẠT yêu cầu |
| Q29 | ReviewQuestion chấp nhận 2 options | `{"accepted_options":2}` | KHÔNG ĐẠT yêu cầu |
| Q30 | Health response đúng | `{"http":200,"body":{"status":"ok"}}` | ĐẠT kịch bản hẹp |
| Q31 | Admin sửa flashcard course không sở hữu | `200` | KHÔNG ĐẠT yêu cầu |
| Q32 | Student từng là owner sửa và approve flashcard | `{"http":200,"approved":true}` | KHÔNG ĐẠT yêu cầu |

Q03 là **rủi ro nguồn role/revocation**, không phải chứng minh client có thể tự giả chữ ký JWT. Token có chữ ký hợp lệ mang group cũ được chấp nhận tới khi hết hạn; hiện sync ghi ngược group đó vào DB. Policy phải quyết định DB hoặc group là nguồn thẩm quyền, và thiết kế hiệu lực hạ quyền/session refresh tương ứng.

Q31/Q32 không giả định mọi Student sở hữu course: fixture mô phỏng user **từng là Instructor owner rồi bị Admin đổi role**, trường hợp hệ thống hiện cho phép. PUT không kiểm role nên vẫn sửa/approve nội dung. DELETE dùng chung helper, được ghi static/UNVERIFIED thay vì suy kết quả DELETE đã test.

## 9. Mức độ đáp ứng 56 màn hình

Phân loại **bao phủ giao diện/API**, độc lập trạng thái DONE của API:

- **ĐỦ ROUTE: 25** — đã có các lời gọi cần thiết hoặc alternative path hiện hữu; không đồng nghĩa logic/an toàn/integration đã đạt.
- **MỘT PHẦN: 16** — thiếu dữ liệu/hành động/filter/contract hoặc route hiện không thực hiện trọn chức năng.
- **THIẾU: 2** — screen 15 thiếu learner review persistence; screen 54 thiếu job-log detail.
- **EXTERNAL: 5** — các screen auth dựa Cognito; wrapper FastAPI có code, pool/runtime thật UNVERIFIED.
- **UI STATE: 8** — modal/thông báo/policy/unauthorized không cần endpoint riêng; vẫn phụ thuộc API nền.

Đối chiếu từng màn, không lấy ảnh giao diện làm bằng chứng test backend:

| Screen | Nghiệp vụ | Bao phủ API | API/dịch vụ thực tế | Gap/kết quả kiểm chứng | Nguồn screen |
|---:|---|---|---|---|---|
| 01 | Đăng nhập | **EXTERNAL** | Cognito signIn + GET /auth/me (#4) | Q01/Q02 đạt ở local RSA; User Pool/client thật UNVERIFIED. | `docs/ui-doc/ui-spec/SPEC.md:101`; v6:114 |
| 02 | Đăng ký học viên | **EXTERNAL** | POST /auth/register (#2) → Cognito | Wrapper tồn tại, khác hướng SDK trực tiếp; signup/DB/OTP E2E UNVERIFIED. | `docs/ui-doc/ui-spec/SPEC.md:112`; v6:115 |
| 03 | Xác minh email/OTP | **EXTERNAL** | POST /auth/verify-email; /auth/resend-verification | Proxy Cognito ngoài bảng 60; không thiếu một hệ thống OTP FastAPI độc lập. | `docs/ui-doc/ui-spec/SPEC.md:123`; v6:116 |
| 04 | Đăng ký thành công | **UI STATE** | Kết quả confirm-signup | Không cần route mới; thành công thật phụ thuộc Cognito. | `docs/ui-doc/ui-spec/SPEC.md:134`; v6:117 |
| 05 | Quên mật khẩu | **EXTERNAL** | POST /auth/forgot-password → Cognito | Wrapper có; chống enumeration một phần, AWS thật UNVERIFIED. | `docs/ui-doc/ui-spec/SPEC.md:145`; v6:118 |
| 06 | Đặt lại mật khẩu | **EXTERNAL** | POST /auth/reset-password → Cognito | OTP/password do Cognito; không đồng nhất admin reset #57. | `docs/ui-doc/ui-spec/SPEC.md:156`; v6:119 |
| 07 | Khám phá khóa học | **MỘT PHẦN** | GET /courses (#6) | Có catalog; q/page/limit/search/filter không được route xử lý. | `docs/ui-doc/ui-spec/SPEC.md:167`; v6:120 |
| 08 | Chi tiết course/enroll | **ĐỦ ROUTE** | #7 + #21 | Q04 lộ title lesson draft; enroll DB chưa được kiểm thử đủ. | `docs/ui-doc/ui-spec/SPEC.md:178`; v6:121 |
| 09 | Enroll thành công | **UI STATE** | Response POST enroll (#21) | Modal không cần endpoint riêng; không coi UI là test enrollment. | `docs/ui-doc/ui-spec/SPEC.md:189`; v6:122 |
| 10 | Khóa học của tôi | **ĐỦ ROUTE** | #14 + #23 | Đã có list; tiến độ phụ thuộc completed 10%, resume không bền. | `docs/ui-doc/ui-spec/SPEC.md:200`; v6:123 |
| 11 | Lộ trình course | **ĐỦ ROUTE** | #16 + #18 + #45 | Có cấu trúc; đọc lesson/video chưa thực thi unlock (Q05–Q10). | `docs/ui-doc/ui-spec/SPEC.md:211`; v6:124 |
| 12 | Học video/transcript | **ĐỦ ROUTE** | #19 + #27 + #22; GET /lessons/{id}/content | Q09/Q18/Q20/Q27: khóa học bị vượt, mất resume, FE save 422. | `docs/ui-doc/ui-spec/SPEC.md:222`; v6:125 |
| 13 | Section bị khóa | **ĐỦ ROUTE** | #45 + lỗi 403 từ lesson/video | Có state khóa nhưng lesson/video vẫn cho truy cập trực tiếp; Q05/Q09. | `docs/ui-doc/ui-spec/SPEC.md:233`; v6:126 |
| 14 | Flashcard mặt trước | **MỘT PHẦN** | GET /lessons/{id}/flashcards; #39/#41 chưa có | Có bộ thẻ lesson; section/course aggregate và unlock chưa đủ (Q08). | `docs/ui-doc/ui-spec/SPEC.md:244`; v6:127 |
| 15 | Flashcard mặt sau/nhớ | **THIẾU** | #40 chưa có | Lật thẻ là UI; remembered/needs-review chưa có server endpoint/model lưu user state. | `docs/ui-doc/ui-spec/SPEC.md:255`; v6:128 |
| 16 | Tổng kết flashcard | **MỘT PHẦN** | Lesson flashcards + review summary cần #40 | Có nội dung, không có remembered/needs-review bền qua phiên. | `docs/ui-doc/ui-spec/SPEC.md:266`; v6:129 |
| 17 | Checkpoint bắt đầu | **ĐỦ ROUTE** | #42 + #45 | Checkpoint gate mới đã test; trạng thái hoàn thành lesson vẫn có thể giả qua progress. | `docs/ui-doc/ui-spec/SPEC.md:277`; v6:130 |
| 18 | Làm checkpoint | **ĐỦ ROUTE** | #42 | Q12 và test_checkpoint_backend che đáp án; quy tắc 4 options chưa enforce. | `docs/ui-doc/ui-spec/SPEC.md:288`; v6:131 |
| 19 | Xác nhận nộp | **UI STATE** | #43 khi xác nhận | Không cần route modal; submit UUID idempotency có test đạt. | `docs/ui-doc/ui-spec/SPEC.md:299`; v6:132 |
| 20 | Kết quả ≥80% | **MỘT PHẦN** | #43 + #45 | Có score/pass/unlock; result per-question explanation trả null/chưa đủ. | `docs/ui-doc/ui-spec/SPEC.md:310`; v6:133 |
| 21 | Kết quả 50–79% | **MỘT PHẦN** | #43 + #46 | Retry mức trung bình đã test; result explanations/band/alias response cần thống nhất. | `docs/ui-doc/ui-spec/SPEC.md:321`; v6:134 |
| 22 | Kết quả <50% | **ĐỦ ROUTE** | #43 + POST /student/remediation | Guard checkpoint mới có và test đạt; luồng Tutor contract cũ chưa nối guard. | `docs/ui-doc/ui-spec/SPEC.md:332`; v6:135 |
| 23 | Tutor giải thích lỗi | **ĐỦ ROUTE** | #46/#47 hoặc /student/remediation | Workflow mới có errors/explanation; hai bộ schema song song, AI/quota UNVERIFIED. | `docs/ui-doc/ui-spec/SPEC.md:343`; v6:136 |
| 24 | Tutor xem lại bài/thẻ | **MỘT PHẦN** | POST /student/remediation/{id}/advance | Có step guard, nhưng thẻ được dựng từ câu sai, chưa gắn resource IDs/nguồn thời gian như UI. | `docs/ui-doc/ui-spec/SPEC.md:354`; v6:137 |
| 25 | Practice | **ĐỦ ROUTE** | POST /student/remediation/{id}/practice; #48 | Workflow mới đạt 2/3 (Q17); legacy #48 không đạt (Q15). Có thể sinh 2 thay vì luôn 3 câu. | `docs/ui-doc/ui-spec/SPEC.md:365`; v6:138 |
| 26 | Practice đạt | **ĐỦ ROUTE** | Workflow practice + checkpoint retry | Q17 cập nhật CheckpointRemediation và mở retry; Q16 legacy vẫn chặn. | `docs/ui-doc/ui-spec/SPEC.md:376`; v6:139 |
| 27 | Practice chưa đạt | **ĐỦ ROUTE** | Practice result + start(regenerate=true) | Có nhánh sinh lại sau kết quả; cần regression riêng 1/3/regenerate/giới hạn quota. | `docs/ui-doc/ui-spec/SPEC.md:387`; v6:140 |
| 28 | Hoàn thành course | **ĐỦ ROUTE** | GET /courses/{id}/completion; #14/#23 | Có tính cả lesson+checkpoint ở completion; không đồng nhất overall_percent của progress. | `docs/ui-doc/ui-spec/SPEC.md:398`; v6:141 |
| 29 | Tiến độ/lịch sử | **ĐỦ ROUTE** | #44; /students/me/learning-overview; /students/me/checkpoint-history | Có read model thay #24, chưa khóa alias/schema; tiến độ source chưa đáng tin. | `docs/ui-doc/ui-spec/SPEC.md:409`; v6:142 |
| 30 | Instructor dashboard | **ĐỦ ROUTE** | #50 + #12/#37 | Handler runtime khác handler Swagger; thiếu regression và định nghĩa metrics. | `docs/ui-doc/ui-spec/SPEC.md:420`; v6:143 |
| 31 | Danh sách course Instructor | **MỘT PHẦN** | #12 hoặc /courses/instructor/me | Có owner DRAFT/PUBLISHED; search/filter theo UI chưa có query handler. | `docs/ui-doc/ui-spec/SPEC.md:431`; v6:144 |
| 32 | Tạo course/cover | **ĐỦ ROUTE** | #8 | Cover base64 PNG/JPEG hỗ trợ ≤250 KB, không cần tự thêm S3 cover route; DB migration 0006 chưa verify. | `docs/ui-doc/ui-spec/SPEC.md:442`; v6:145 |
| 33 | Cấu trúc course | **ĐỦ ROUTE** | #13/#9/#15/#17 | Owner draft có; thiếu test quản lý cấu trúc đầy đủ, readiness không có DTO. | `docs/ui-doc/ui-spec/SPEC.md:453`; v6:146 |
| 34 | Thêm lesson | **ĐỦ ROUTE** | #17 | Owner/DRAFT có; trùng position trả 500 (Q28). | `docs/ui-doc/ui-spec/SPEC.md:464`; v6:147 |
| 35 | Upload video | **ĐỦ ROUTE** | #25 + PUT presigned URL ở S3 | Ledger/event-only có code; #26 là DECISION, AWS/S3 thật UNVERIFIED. | `docs/ui-doc/ui-spec/SPEC.md:475`; v6:148 |
| 36 | Theo dõi xử lý | **ĐỦ ROUTE** | #28 | Polling source DB có; video/AI workflow end-to-end UNVERIFIED. | `docs/ui-doc/ui-spec/SPEC.md:486`; v6:149 |
| 37 | Pipeline lỗi/retry | **ĐỦ ROUTE** | #29 | Failed-only/outbox có unit test; policy Admin và deploy dispatch chưa nghiệm thu. | `docs/ui-doc/ui-spec/SPEC.md:497`; v6:150 |
| 38 | Hàng chờ AI | **MỘT PHẦN** | #37 | Handler đầu chỉ pending/processing/failed, thiếu published/filter; route trùng Swagger. | `docs/ui-doc/ui-spec/SPEC.md:508`; v6:151 |
| 39 | Review summary | **ĐỦ ROUTE** | #34/#35 hoặc #31/#32 | PATCH summary xóa flashcards (Q23); FE hiện gọi review-draft legacy. | `docs/ui-doc/ui-spec/SPEC.md:519`; v6:152 |
| 40 | Review concepts | **ĐỦ ROUTE** | #34/#35 hoặc #31/#32 | Sửa term/definition có; source chunk/timestamp DTO chưa hỗ trợ. | `docs/ui-doc/ui-spec/SPEC.md:530`; v6:153 |
| 41 | Review flashcards | **MỘT PHẦN** | #31/#32; lesson-scoped flashcard CRUD | PUT draft hỗ trợ flashcards; PATCH ai-content không nhận và có thể xóa chúng. | `docs/ui-doc/ui-spec/SPEC.md:541`; v6:154 |
| 42 | Review quiz | **MỘT PHẦN** | #31/#32/#34/#35 | 2 options vẫn hợp lệ, source timestamps bị bỏ khỏi review DTO/replacement (Q29). | `docs/ui-doc/ui-spec/SPEC.md:552`; v6:155 |
| 43 | Xác nhận approve | **UI STATE** | #33 hoặc #36 | Modal không cần route mới; approve thiếu processed-video guard (Q24). | `docs/ui-doc/ui-spec/SPEC.md:563`; v6:156 |
| 44 | Publish course | **MỘT PHẦN** | #10; #38 chưa có | Thiếu readiness/missing-items và publish thiếu guard video (Q25); endpoint readiness riêng là tùy chọn. | `docs/ui-doc/ui-spec/SPEC.md:574`; v6:157 |
| 45 | Danh sách học viên/báo cáo | **MỘT PHẦN** | #51; GET /instructor/students | Có aggregate khác contract #52, thiếu scope/filter/last score/tutor usage; source read model có lỗi draft course. | `docs/ui-doc/ui-spec/SPEC.md:585`; v6:158 |
| 46 | Chi tiết học viên | **MỘT PHẦN** | GET /instructor/students/{id}; #53 chưa có | HTTP 500 KeyError progress_percent (Q22); placeholder average/tutor/topics và attempt_count ngoài course. | `docs/ui-doc/ui-spec/SPEC.md:596`; v6:159 |
| 47 | Quản trị tài khoản | **MỘT PHẦN** | #54 | Có list/search, thiếu role/status/page và active state. | `docs/ui-doc/ui-spec/SPEC.md:607`; v6:160 |
| 48 | Tạo Instructor/Admin | **ĐỦ ROUTE** | #55 | Có provision, nhưng permanent password/SUPPRESS, không invite/compensation/audit; AWS thật UNVERIFIED. | `docs/ui-doc/ui-spec/SPEC.md:618`; v6:161 |
| 49 | Xác nhận cấp Admin | **UI STATE** | #55 sau xác nhận | Không cần endpoint xác nhận riêng; server vẫn phải enforce ADMIN. | `docs/ui-doc/ui-spec/SPEC.md:629`; v6:162 |
| 50 | Tạo account thành công | **UI STATE** | Response #55 | Không cần route riêng; flow invite/temporary password hiện khác v6. | `docs/ui-doc/ui-spec/SPEC.md:640`; v6:163 |
| 51 | Sửa/khóa/reset account | **MỘT PHẦN** | #56; #57 chưa có | Không có disable/reset/audit; Admin cuối tự hạ được (Q26), stale group phục hồi role (Q03). | `docs/ui-doc/ui-spec/SPEC.md:651`; v6:164 |
| 52 | Vai trò/quyền | **UI STATE** | Policy matrix cố định | Không bắt buộc GET /admin/roles; thực thi server có lỗi Flashcard writes Q31/Q32. | `docs/ui-doc/ui-spec/SPEC.md:662`; v6:165 |
| 53 | Giám sát hệ thống | **MỘT PHẦN** | GET /admin/monitoring/jobs; #58/#59 chưa có | Chỉ list 50 ledger run, thiếu cost/AI/CloudWatch metrics và pagination. | `docs/ui-doc/ui-spec/SPEC.md:673`; v6:166 |
| 54 | Job log modal | **THIẾU** | #60 chưa có | Không có log/job-detail read model hoặc CloudWatch link/redaction phục vụ modal. | `docs/ui-doc/ui-spec/SPEC.md:684`; v6:167 |
| 55 | Profile/đổi mật khẩu | **ĐỦ ROUTE** | GET/PATCH /auth/me + POST /auth/change-password | Đủ path thực tế khác #5; update name chỉ DB, Cognito đồng bộ/đổi password thật UNVERIFIED. | `docs/ui-doc/ui-spec/SPEC.md:695`; v6:168 |
| 56 | Không có quyền | **UI STATE** | 401/403 của dependencies | Q01/Q02 và role tests đạt; UI routing/browser không được kiểm thử trong audit. | `docs/ui-doc/ui-spec/SPEC.md:706`; v6:169 |

Tỷ lệ “đủ route” trong 43 màn hình cần nghiệp vụ FastAPI: **25/(56−5−8) = 58,14%**. Đây là tỷ lệ mapping kỹ thuật, không phải tỷ lệ UI hoàn thiện. **0 màn hình được chứng nhận E2E hoàn chỉnh** trong audit này vì không chạy browser/Cognito/S3/PostgreSQL thật; ghi UNVERIFIED, **không kết luận 56 màn hình đều hỏng**. Các màn UI STATE không bị coi thiếu API chỉ vì không có route riêng.

## 10. Công thức và thống kê theo module

Đặt `N_m` = số cặp method/path của module trong bảng 60; `E_m` = số cặp có cả runtime và OpenAPI; `D_m` = số DONE theo tiêu chí mục 2.3.

- **Tỷ lệ endpoint tồn tại**: `100 × E_m / N_m`.
- **Tỷ lệ chức năng khép đủ bằng chứng**: `100 × D_m / N_m`. Không gán PARTIAL=50%, không lấy tỷ lệ test pass thay completion.
- **Tỷ lệ đã nghiệm thu trong số endpoint hiện hữu** (chỉ số bổ sung): `100 × D / E = 1/44 = 2,27%`.
- Tỷ lệ toàn hệ thống dùng **tổng tử số/tổng mẫu số**, không lấy trung bình phần trăm các module.
- 24 API ngoài contract không nằm trong mẫu 60; 5 duplicate registrations không tăng endpoint count. PROPOSED/DECISION vẫn trong mẫu 60 để tái lập số liệu. Nếu muốn chỉ tính scope chắc chắn của draft hiện tại: `N'=60−14=46`, endpoint tồn tại `44/46=95,65%`, DONE `1/46=2,17%`; chưa được hiểu là nhóm đã chốt scope này.

| Module theo bảng contract | N | E | DONE | PARTIAL | MISSING | PROPOSED | BLOCKED | Endpoint tồn tại | Khép đủ bằng chứng |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| System | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 1/1 = 100.00% | 1/1 = 100.00% |
| Auth | 3 | 2 | 0 | 2 | 1 | 0 | 0 | 2/3 = 66.67% | 0/3 = 0.00% |
| Profile | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0/1 = 0.00% | 0/1 = 0.00% |
| Course | 9 | 8 | 0 | 8 | 0 | 1 | 0 | 8/9 = 88.89% | 0/9 = 0.00% |
| Section | 2 | 2 | 0 | 2 | 0 | 0 | 0 | 2/2 = 100.00% | 0/2 = 0.00% |
| Lesson | 4 | 4 | 0 | 4 | 0 | 0 | 0 | 4/4 = 100.00% | 0/4 = 0.00% |
| Enrollment | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1/1 = 100.00% | 0/1 = 0.00% |
| Progress | 3 | 2 | 0 | 2 | 0 | 1 | 0 | 2/3 = 66.67% | 0/3 = 0.00% |
| Upload | 2 | 1 | 0 | 1 | 0 | 1 | 0 | 1/2 = 50.00% | 0/2 = 0.00% |
| Video | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1/1 = 100.00% | 0/1 = 0.00% |
| Processing | 2 | 2 | 0 | 2 | 0 | 0 | 0 | 2/2 = 100.00% | 0/2 = 0.00% |
| AI Review | 9 | 8 | 0 | 8 | 0 | 1 | 0 | 8/9 = 88.89% | 0/9 = 0.00% |
| Flashcard | 3 | 0 | 0 | 0 | 0 | 3 | 0 | 0/3 = 0.00% | 0/3 = 0.00% |
| Quiz | 3 | 3 | 0 | 3 | 0 | 0 | 0 | 3/3 = 100.00% | 0/3 = 0.00% |
| Unlock | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1/1 = 100.00% | 0/1 = 0.00% |
| AI Tutor | 4 | 3 | 0 | 3 | 0 | 1 | 0 | 3/4 = 75.00% | 0/4 = 0.00% |
| Analytics | 4 | 2 | 0 | 2 | 0 | 2 | 0 | 2/4 = 50.00% | 0/4 = 0.00% |
| Admin | 7 | 3 | 0 | 3 | 1 | 3 | 0 | 3/7 = 42.86% | 0/7 = 0.00% |
| **Toàn hệ thống** | **60** | **44** | **1** | **43** | **2** | **14** | **0** | **44/60 = 73,33%** | **1/60 = 1,67%** |

Các mục chưa xác minh PostgreSQL/AWS là giới hạn bằng chứng, không được cộng vào DONE hoặc suy ra dependency đã hỏng. Có thể nâng trạng thái sau khi khắc phục gap và test cách ly thực sự đạt.

## 11. Backlog Backend theo P0 → P1 → P2

### P0 — bảo vệ quyền và dữ liệu trước public/release

| ID | Nhiệm vụ cụ thể | Bằng chứng | Tiêu chí nghiệm thu |
|---|---|---|---|
| P0-01 | Chốt nguồn role; ngăn JWT group cũ ghi ngược role đã bị hạ, thêm policy revoke/disabled nếu cần | Q03; `auth_service.py:179–194`; `admin.py:68` | Demote/disable có hiệu lực theo policy; token cũ không khôi phục quyền; test signed JWT + DB, không chỉ mock token_user. |
| P0-02 | Enforce Instructor owner ở Flashcard PUT/DELETE, bỏ Admin bypass ngoài policy đã chốt | Q31/Q32; `api/flashcards.py:37/139/165` | Student/former owner/Admin không được sửa course khác; không tự approve; GET/POST/PUT/DELETE role matrix và publish/version negative tests. |
| P0-03 | Chặn PATCH AI summary xóa flashcards ngoài ý định, chốt field whitelist và partial merge | Q23; `api/review.py:225`; `review_repo.py:183` | PATCH summary giữ nguyên card IDs/content/count; PATCH/PUT flashcards đúng schema, rollback khi validation/conflict; không sửa production data trong task này. |
| P0-04 | Không cho approve/publish nội dung thiếu processed video/approval checkpoint và prerequisite học liệu | Q24/Q25; `review_service.py:228`; `course_service.py:87` | Thiếu video/AI/quiz/flashcards bắt buộc trả 409; không thay visibility/state; owner-only, concurrency và PostgreSQL tests cách ly. |
| P0-05 | Bảo vệ Admin cuối, audit role changes và tránh Cognito/DB lệch sau partial failure | Q26; `admin.py:68`; `auth_service.py:347/396` | Last-admin/self-demotion theo policy; audit entry; retry/idempotent compensation; user role/token DB nhất quán. |
| P0-06 | Chốt kế hoạch migration version và registry trước deploy mới | 4 version 0004; 0005 description guard; V3/0006 fields | Test từ bootstrap/legacy trên PostgreSQL riêng đủ ORM schema/triggers; không sửa migration đã apply; migration mới/reconcile plan được review, không tự chạy lên RDS. |

### P1 — hoàn thiện các luồng học/giảng dạy và tương thích

| ID | Nhiệm vụ | API/screen | Tiêu chí nghiệm thu |
|---|---|---|---|
| P1-01 | Dùng access guard chung cho lesson/list/content/video/flashcards/progress và unlock-status | #18/#19/#22/#23/#27/#45, extra content/cards; screen 11–18 | Student phải enrolled+published+unlocked; no URL/key/content khi locked; course thiếu 404, role sai 403; Q05–Q10/Q18/Q19 đổi thành đạt. |
| P1-02 | Chốt progress contract/session/sequence/idempotency/resume, bound ranges theo duration tin cậy, lưu tích lũy | #22/#23; extra viewing-sessions; screen 10–12/28–29 | Payload FE không 422; resume/ranges bền qua reload; range không vượt duration/time policy; không giảm watch history; định nghĩa completion không tự gán 10% thành production rule. |
| P1-03 | Hợp nhất Tutor legacy và remediation workflow, tái dùng service/route sẵn có | #46–#49 + 4 /student/remediation operations; screen 21–27 | 1/3 chặn retry, 2/3 và 3/3 mở đúng user/attempt/section; giữ step guard; resume sau reload; quota/negative/cross-session/regen tests; không dựng API song song thứ ba. |
| P1-04 | Chuẩn hóa checkpoint response và legacy/schema tests | #42–#44; screen 17–22/29 | UUID idempotency được document; score/band/can_retry/remediation/results/explanation theo JSON đã chốt; 4 options; không đáp án trước submit; test 80/60/20 và actual app router. |
| P1-05 | Lọc lesson draft khỏi public outline; bổ sung catalog/instructor search/filter/page và test CRUD/enroll | #6–#21; screen 07–11/30–34 | Public không lộ metadata chưa publish; own-only draft; 201/409/422 đúng, duplicate lesson không 500; enrollment thật/rollback/concurrency trên test DB. |
| P1-06 | Hợp nhất 5 cặp duplicate routers, khóa DTO/operationId/read-model regression | Dashboard/queue/students/content | Một handler mỗi method/path; runtime response khớp OpenAPI; sửa Q22 KeyError và scope attempt_count; queue/filter/status thống nhất. |
| P1-07 | Hoàn thiện learner Flashcard remembered/review state, source refs và review output | #39/#40; extra lesson Flashcard APIs; screen 14–16/39–42 | Quyết định tận dụng lesson endpoint hay add section alias; Student reviews lưu theo user; approved/unlocked; source timestamp đúng; không tự tăng API không cần thiết. |
| P1-08 | Hoàn thiện instructor student reports/tutor usage và bỏ placeholder | #51–#53 hoặc mở rộng extra students; screen 45–46 | Course owner + enrolled student, course-scoped attempts/tutor/weak topics/progress; không 500, không lộ dữ liệu course khác; negative/SQL tests. |
| P1-09 | Admin reset/disable/filter/pagination, provision invite/temporary password, profile sync | #54–#57/#5 hoặc /auth/me; screen 47–55 | Không mật khẩu permanent lộ qua UI flow; không provision public role; disable/revoke/audit; reset đúng Cognito administrative operation; AWS mocked và staging test riêng. |
| P1-10 | Nghiệm thu đường upload event-only/ledger/AI worker và sửa test fixtures auth cũ | #25–#36; screen 35–44 | Issued key/HeadObject/size/time/ETag/dedup/outbox/AI complete tới REVIEW_REQUIRED; đóng browser vẫn chạy; S3/Step Functions/IAM/Bedrock chỉ kiểm ở môi trường test được chuẩn bị riêng. |

### P2 — quyết định sản phẩm và vận hành sau các guard cốt lõi

| ID | Nhiệm vụ | Ghi chú |
|---|---|---|
| P2-01 | Admin monitoring summary/jobs/detail/log/cost (#58–#60) | Tái dùng ledger và /admin/monitoring/jobs; bổ sung CloudWatch adapter/log redaction/pagination, không phát AWS credentials cho browser. Job-log detail screen 54 vẫn là gap thật. |
| P2-02 | Chốt course flashcard aggregation, publish-readiness và optional unpublish | #41/#38/#11; có thể gộp readiness trong owner detail, không mặc định cần route mới. Unpublish phải có policy cho learner/progress và video replacement. |
| P2-03 | Đồng bộ Contract v6 với actual Cognito wrappers/aliases/schema | Gỡ nhãn local login/demo auth đã lỗi thời; ghi 24 extra paths được chọn duy trì, deprecate alias có version; không xóa route chỉ vì chưa có trong bảng. |
| P2-04 | Chuẩn hóa observability/quota/DTO docs | Request/response schemas rõ hơn, bounded pagination, machine codes, quota Tutor/AI, tránh log signed URL/token. Không dùng số route/test pass làm KPI hoàn thiện. |

**Phần bị thiếu trong contract nhưng UI/source đã cần**: 24 exact paths mục 5, đặc biệt remediation advance/resume/practice, viewing-sessions, learning-overview/completion, lesson content, Cognito wrappers và lesson Flashcard CRUD. **Thiết kế chưa được ghi**: progress session/sequence/request_id hiện FE đã gửi, persistence learner review theo revision/user, policy revoke/last-admin/audit. Chúng cần chốt field/workflow trước; không có căn cứ đề xuất thêm HTTP endpoint cho mỗi modal, OTP local, S3 PUT hoặc bảng role tĩnh.

## 12. Cách tái lập kiểm toán an toàn

Chạy từ root repository, PowerShell. Các script dưới đây chỉ tạo dữ liệu trong SQLite RAM, không sửa source; dùng settings giả và chặn network. Các test opt-in PostgreSQL vẫn bị tắt. Đừng thay DATABASE_URL bằng RDS.

### 12.1. Runner pytest với network guard, toàn bộ test functions được thu thập

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; @'
import os,sys,runpy,socket,contextlib,io,json
from unittest.mock import patch
sys.path.insert(0,'.venv/Lib/site-packages');sys.path.insert(0,'backend')
ns=runpy.run_path('backend/tests/run_unit_offline.py')
os.environ.pop('AWS_LAMBDA_FUNCTION_NAME',None)
os.environ.update({'COGNITO_USER_POOL_ID':'ap-southeast-1_testpool','COGNITO_APP_CLIENT_ID':'test-client','LEARNCLOUD_RUN_PIPELINE_DB_TESTS':'0'})
import pytest
class Recorder:
 def __init__(self): self.rows=[]
 def pytest_runtest_logreport(self,report):
  r=report
  if r.when=='call' or r.failed or r.skipped:
   self.rows.append({'id':r.nodeid,'phase':r.when,'outcome':r.outcome,'reason':str(r.longrepr)[-650:] if r.failed or r.skipped else ''})
r=Recorder();o=io.StringIO()
with contextlib.ExitStack() as s:
 for obj,name,replacement in [(socket.socket,'connect',ns['deny_network']),(socket.socket,'connect_ex',ns['deny_network']),(socket.socket,'sendto',ns['deny_network']),(socket,'getaddrinfo',ns['deny_network']),(socket,'create_connection',ns['deny_network']),(socket,'socketpair',ns['internal_socketpair'])]: s.enter_context(patch.object(obj,name,replacement))
 with contextlib.redirect_stdout(o),contextlib.redirect_stderr(o):
  code=pytest.main(['backend/tests/unit','backend/tests/integration','ai_pipeline/tests','-q','-p','no:cacheprovider','--tb=no','--disable-warnings'],plugins=[r])
print(json.dumps({'exit_code':code,'summary':o.getvalue().splitlines()[-1],'tests':r.rows},ensure_ascii=False))
'@ | python -X utf8 -
```

### 12.2. Các probe bổ sung có thể chạy lại không cần thêm test file

Đây là script đã chạy cho Q01–Q32. Nó dùng source hiện hữu và MockAIAdapter; các kết quả vi phạm được ghi thành observations, không sửa ứng dụng để làm assertion xanh. ID/đáp án/cognito client/credentials đều là giả. Script không có ý nghĩa kiểm chứng production.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
@'
import os,sys,runpy,socket,json,contextlib,io,time,logging
from unittest.mock import patch,Mock
from types import SimpleNamespace
from uuid import uuid4
sys.path.insert(0,'.venv/Lib/site-packages');sys.path.insert(0,'backend')
ns=runpy.run_path('backend/tests/run_unit_offline.py')
os.environ.pop('AWS_LAMBDA_FUNCTION_NAME',None)
os.environ.update({'COGNITO_USER_POOL_ID':'ap-southeast-1_testpool','COGNITO_APP_CLIENT_ID':'test-client','TUTOR_USE_BEDROCK':'false'})
rows=[]
def record(id,scenario,expected,observed,ok):
 rows.append(dict(id=id,scenario=scenario,expected=expected,observed=observed,requirement_met=bool(ok)))
with contextlib.ExitStack() as stack:
 for obj,name,replacement in [(socket.socket,'connect',ns['deny_network']),(socket.socket,'connect_ex',ns['deny_network']),(socket.socket,'sendto',ns['deny_network']),(socket,'getaddrinfo',ns['deny_network']),(socket,'create_connection',ns['deny_network']),(socket,'socketpair',ns['internal_socketpair'])]: stack.enter_context(patch.object(obj,name,replacement))
 from sqlalchemy import create_engine,select,event
 from sqlalchemy.orm import Session
 from sqlalchemy.pool import StaticPool
 from app.main import app
 from app.database import Base
 from app.models.user import User
 from app.models.course import Course
 from app.models.section import Section
 from app.models.lesson import Lesson
 from app.models.enrollment import Enrollment
 from app.models.progress import LessonProgress
 from app.models.quiz import Quiz,Question,QuizAttempt,QuizAnswer,CheckpointRemediation
 from app.models.flashcard import Flashcard
 from app.models.tutor import TutorSession
 from app.dependencies import get_db,get_current_user
 from app.services import auth_service,quiz_service
 from app.api import screen_workflows
 from fastapi.testclient import TestClient
 engine=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
 @event.listens_for(engine,'connect')
 def fk(connection,record): connection.execute('PRAGMA foreign_keys=ON')
 Base.metadata.create_all(engine); db=Session(engine)
 for id,role in [(1,'INSTRUCTOR'),(2,'STUDENT'),(3,'STUDENT'),(4,'INSTRUCTOR'),(5,'ADMIN')]:
  db.add(User(id=id,cognito_sub=f'sub-{id}',name=f'User {id}',email=f'u{id}@example.com',role=role))
 db.commit()
 db.add_all([Course(id=1,instructor_id=1,title='Public course',status='PUBLISHED'),Course(id=2,instructor_id=1,title='Draft course',status='DRAFT'),Course(id=3,instructor_id=4,title='Other teacher',status='PUBLISHED')]);db.commit()
 for id,cid,pos in [(1,1,1),(2,1,2),(3,2,1),(4,3,1)]: db.add(Section(id=id,course_id=cid,title=f'Section {id}',position=pos))
 db.commit()
 for id,sid,pos,status in [(1,1,1,'PUBLISHED'),(2,2,1,'PUBLISHED'),(3,1,2,'DRAFT'),(4,3,1,'PUBLISHED'),(5,4,1,'PUBLISHED')]:
  db.add(Lesson(id=id,section_id=sid,position=pos,title='PRIVATE DRAFT' if id==3 else f'Lesson {id}',status=status,duration_seconds=100,processed_video_key=None if id==1 else f'lessons/{id}/processed/video.mp4',transcript_json={'text':'Cloud explains networks.','segments':[{'start':0,'end':10,'text':'Cloud explains networks.'}]},summary='Cloud summary',key_concepts_json=[{'term':'Cloud','definition':'Networks'}]))
 db.commit()
 db.add_all([Enrollment(student_id=2,course_id=1),Enrollment(student_id=2,course_id=2),Enrollment(student_id=2,course_id=3),LessonProgress(student_id=2,lesson_id=1,watched_seconds=100,completed=True)])
 db.add_all([Quiz(id=1,section_id=1,title='Quiz',is_approved=True),Quiz(id=2,section_id=2,title='Locked Quiz',is_approved=True),Quiz(id=3,section_id=4,title='Other course Quiz',is_approved=True)]);db.commit()
 for id in range(1,4): db.add(Question(id=id,quiz_id=1,question=f'Cloud question {id}',options_json=['A','B','C','D'],correct_answer='A',explanation='Cloud explains networks.',position=id))
 db.add_all([Question(id=4,quiz_id=2,question='Cloud locked',options_json=['A','B','C','D'],correct_answer='A',explanation='Cloud',position=1),Flashcard(id=1,lesson_id=2,front='Cloud',back='Networks',position=1,is_approved=True)])
 db.commit()
 app.dependency_overrides[get_db]=lambda:db
 logging.disable(logging.CRITICAL)
 with contextlib.redirect_stdout(io.StringIO()), TestClient(app,raise_server_exceptions=False) as client:
  health=client.get('/health');record('Q30','Health contract response','200 status=ok',{'http':health.status_code,'body':health.json()},health.status_code==200 and health.json()=={'status':'ok'})
  unauth=[client.get('/auth/me').status_code,client.get('/auth/me',headers={'X-Demo-User':'5'}).status_code]
  record('Q01','Anonymous and X-Demo-User do not authenticate',[401,401],unauth,unauth==[401,401])
  from cryptography.hazmat.primitives.asymmetric import rsa
  import jwt
  key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
  otherkey=rsa.generate_private_key(public_exponent=65537,key_size=2048)
  issuer='https://cognito-idp.ap-southeast-1.amazonaws.com/ap-southeast-1_testpool'
  claims={'sub':'sub-2','iss':issuer,'client_id':'test-client','token_use':'access','exp':int(time.time())+600}
  def token(changes=None,signer=key):
   return jwt.encode({**claims,**(changes or {})},signer,algorithm='RS256')
  jwk=SimpleNamespace(get_signing_key_from_jwt=lambda _:SimpleNamespace(key=key.public_key()))
  with patch.object(auth_service.jwt,'PyJWKClient',return_value=jwk):
   statuses=[]
   for change,signer in [({},key),({'exp':0},key),({'iss':'wrong'},key),({'client_id':'wrong'},key),({'token_use':'id'},key),({},otherkey)]:
    statuses.append(client.get('/auth/me',headers={'Authorization':'Bearer '+token(change,signer)}).status_code)
   record('Q02','Real local RS256 signature/expiry/issuer/client/token_use verification (JWKS mocked)',[200,401,401,401,401,401],statuses,statuses==[200,401,401,401,401,401])
   # A signed token keeps an obsolete privileged group after DB demotion.
   stale=token({'sub':'sub-4','cognito:groups':['INSTRUCTOR']})
   db.get(User,4).role='STUDENT';db.commit()
   response=client.get('/instructor/courses',headers={'Authorization':'Bearer '+stale})
   record('Q03','Old privileged group must not undo a deliberate DB demotion','403; role remains STUDENT',{'http':response.status_code,'db_role':db.get(User,4).role},response.status_code==403 and db.get(User,4).role=='STUDENT')
   db.get(User,4).role='INSTRUCTOR';db.commit()
  app.dependency_overrides[get_current_user]=lambda:db.get(User,2)
  response=client.get('/courses/1');private=any(l['title']=='PRIVATE DRAFT' for s in response.json().get('sections',[]) for l in s.get('lessons',[]))
  record('Q04','Public course outline filters draft lesson metadata','no PRIVATE DRAFT',{'http':response.status_code,'draft_title_exposed':private},not private)
  for id,path in [('Q05','/lessons/2'),('Q06','/sections/2/lessons'),('Q07','/lessons/2/content'),('Q08','/lessons/2/flashcards')]:
   response=client.get(path);record(id,'Enrolled student cannot access locked section: '+path,'403/404',response.status_code,response.status_code in (403,404))
  fake_storage=Mock();fake_storage.generate_download_url.return_value='https://mock.invalid/video'
  with patch('app.services.lesson_service.S3StorageAdapter',return_value=fake_storage):
   response=client.get('/lessons/2/video-url')
   record('Q09','Playback URL must not be issued for locked section','403/404; adapter not called',{'http':response.status_code,'adapter_calls':fake_storage.generate_download_url.call_count},response.status_code in (403,404) and not fake_storage.generate_download_url.called)
  app.dependency_overrides[get_current_user]=lambda:db.get(User,3)
  response=client.get('/courses/1/unlock-status')
  record('Q10','Unenrolled student cannot read course unlock state','403/404',{'http':response.status_code,'body':response.json()},response.status_code in (403,404))
  response=client.get('/sections/1/quiz')
  record('Q11','Unenrolled student cannot obtain checkpoint','403',response.status_code,response.status_code==403)
  app.dependency_overrides[get_current_user]=lambda:db.get(User,2)
  response=client.get('/sections/1/quiz')
  record('Q12','Eligible checkpoint does not disclose answers/explanations','200 without answer keys',{'http':response.status_code,'answer_leak':'correct_answer' in response.text or 'explanation' in response.text},response.status_code==200 and 'correct_answer' not in response.text and 'explanation' not in response.text)
  response=client.post('/quizzes/1/attempts',json={'request_id':str(uuid4()),'answers':[]})
  aid=response.json().get('id')
  record('Q13','Server grades omitted answers and locks immediate low-score retry','0 score, remediation required, can_retry false',{'http':response.status_code,'body':response.json()},response.status_code==200 and float(response.json()['score'])==0 and response.json()['can_retry'] is False and response.json()['remediation_required'] is True)
  # Real generated legacy Tutor session, with three source mistakes.
  response=client.post('/tutor/sessions',json={'attempt_id':aid});sid=response.json().get('id')
  record('Q14','Legacy Tutor practice has three questions for v6','3 questions',{'http':response.status_code,'count':len(response.json().get('practice_questions',[]))},response.status_code==201 and len(response.json()['practice_questions'])==3)
  session=db.get(TutorSession,sid);questions=session.practice_questions
  answers=[q['correct_answer'] for q in questions]
  answers[-1]=next(a for a in questions[-1]['options'] if a!=questions[-1]['correct_answer'])
  response=client.post(f'/tutor/sessions/{sid}/practice-attempts',json={'answers':answers})
  record('Q15','Legacy Tutor 2/3 practice should complete remediation','remediation_completed=true',response.json(),response.json().get('remediation_completed') is True)
  response=client.post(f'/tutor/sessions/{sid}/practice-attempts',json={'answers':[q['correct_answer'] for q in questions]})
  can=quiz_service.can_retry(db,db.get(QuizAttempt,aid))
  record('Q16','Legacy Tutor success should unlock checkpoint retry','can_retry=true',{'legacy_complete':response.json().get('remediation_completed'),'checkpoint_can_retry':can},can)
  response=client.post('/student/remediation',json={'attempt_id':aid});payload=response.json();newid=payload['id']
  for e in payload['errors']: payload=client.post(f'/student/remediation/{newid}/advance',json={'kind':'explanation','item_id':e['id']}).json()
  for card in payload['cards']: payload=client.post(f'/student/remediation/{newid}/advance',json={'kind':'card','item_id':card['id']}).json()
  q=db.get(TutorSession,newid).practice_questions
  answers=[x['correct_answer'] for x in q];answers[-1]=next(a for a in q[-1]['options'] if a!=q[-1]['correct_answer'])
  response=client.post(f'/student/remediation/{newid}/practice',json={'answers':answers})
  record('Q17','New remediation route 2/3 plus all steps unlocks checkpoint','pass and can_retry=true',{'http':response.status_code,'result':response.json().get('result'),'can_retry':quiz_service.can_retry(db,db.get(QuizAttempt,aid))},response.status_code==200 and response.json()['result']['passed'] and quiz_service.can_retry(db,db.get(QuizAttempt,aid)))
  # Progress on locked/published or draft content lacks publication/unlock checks.
  response=client.put('/lessons/2/progress',json={'last_position_seconds':100,'watched_ranges':[[0,100000]]})
  record('Q18','Progress enforces unlock and trusted duration bounds','403/404; no completion',{'http':response.status_code,'body':response.json()},response.status_code in (403,404))
  response=client.get('/courses/2/progress')
  record('Q19','Progress must reject unpublished course','403/404',response.status_code,response.status_code in (403,404))
  client.put('/lessons/1/progress',json={'last_position_seconds':90,'watched_ranges':[[0,90]]})
  response=client.get('/courses/1/progress');lesson=next(x for x in response.json()['lessons'] if x['lesson_id']==1)
  record('Q20','Progress reload preserves watched ranges and resume','resume=90; ranges=[[0,90]]',lesson,lesson['last_position_seconds']==90 and lesson['watched_ranges']==[[0,90]])
  client.put('/lessons/1/progress',json={'last_position_seconds':10,'watched_ranges':[[0,10]]})
  record('Q21','Progress accumulates previous watched coverage','>=90 seconds',db.scalar(select(LessonProgress.watched_seconds).where(LessonProgress.student_id==2,LessonProgress.lesson_id==1)),db.scalar(select(LessonProgress.watched_seconds).where(LessonProgress.student_id==2,LessonProgress.lesson_id==1))>=90)
  response=client.put('/lessons/1/progress',json={'last_position_seconds':10,'watched_ranges':[[0,10]],'playback_session_id':'mock-session','sequence':1,'request_id':str(uuid4())})
  record('Q27','Current frontend progress payload must match backend DTO','200',response.status_code,response.status_code==200)
  app.dependency_overrides[get_current_user]=lambda:db.get(User,1)
  db.query(Enrollment).filter(Enrollment.student_id==2,Enrollment.course_id==2).delete();db.commit()
  response=client.get('/instructor/students/2')
  record('Q22','Instructor student detail responds using course-scoped progress','200',response.status_code,response.status_code==200)
  # Generate real draft with mock AI, then PATCH only summary.
  db.get(Course,1).status='DRAFT';db.commit()
  from app.adapters.ai.mock_ai import MockAIAdapter
  with patch('app.api.review.BedrockAIAdapter',return_value=MockAIAdapter()):
   response=client.post('/lessons/1/review-drafts',json={'transcript':'Cloud networking explains networks.','allow_fallback':True})
  # Existing attempts prevent regeneration, so prepare another draft course/lesson.
  db.get(Course,1).status='PUBLISHED';db.commit()
  with patch('app.api.review.BedrockAIAdapter',return_value=MockAIAdapter()):
   response=client.post('/lessons/4/review-drafts',json={'transcript':'Cloud networking explains networks.','allow_fallback':True})
  draft=response.json();before=len(draft.get('flashcards',[]))
  response=client.patch('/lessons/4/ai-content',json={'summary':'Updated summary','expected_revision':draft['revision']})
  after=len(response.json().get('flashcards',[]))
  record('Q23','PATCH summary must preserve existing flashcards',f'{before} cards retained',{'http':response.status_code,'before':before,'after':after},before>0 and after==before)
  draft=response.json()
  db.get(Lesson,4).processed_video_key=None;db.commit()
  response=client.post('/lessons/4/approve',json={'expected_revision':draft['revision']})
  record('Q24','Approval requires processed video','409 when processed_video_key missing',{'http':response.status_code,'lesson_status':db.get(Lesson,4).status,'processed_video_key':db.get(Lesson,4).processed_video_key},response.status_code==409)
  # Remove the processed key explicitly and try publish with otherwise complete content.
  db.get(Lesson,4).processed_video_key=None;db.commit()
  response=client.post('/courses/2/publish')
  record('Q25','Publish refuses lesson without processed video','409',{'http':response.status_code,'course_status':db.get(Course,2).status},response.status_code==409)
  response=client.post('/sections/1/lessons',json={'title':'Duplicate position','position':1})
  record('Q28','Duplicate lesson position maps to conflict','409',response.status_code,response.status_code==409)
  from app.schemas.review import ReviewQuestion
  two=ReviewQuestion(question='Question',options=['A','B'],correct_answer='A',explanation='Explanation')
  record('Q29','Review questions validate four A-D options for v6','2-option question rejected',{'accepted_options':len(two.options)},False)
  app.dependency_overrides[get_current_user]=lambda:db.get(User,5)
  response=client.put('/lessons/2/flashcards/1',json={'front':'Admin changed card'})
  record('Q31','Admin does not automatically own instructor flashcards','403',response.status_code,response.status_code==403)
  db.get(User,1).role='STUDENT';db.commit()
  app.dependency_overrides[get_current_user]=lambda:db.get(User,1)
  response=client.put('/lessons/2/flashcards/1',json={'front':'Student changed card','is_approved':True})
  record('Q32','Student former owner cannot edit or approve instructor flashcards','403',{'http':response.status_code,'approved':response.json().get('is_approved')},response.status_code==403)
  db.get(User,1).role='INSTRUCTOR';db.commit()
  # last-admin protection without invoking Cognito.
  app.dependency_overrides[get_current_user]=lambda:db.get(User,5)
  with patch.object(auth_service,'admin_update_profile'),patch.object(auth_service,'admin_update_role'):
   response=client.patch('/admin/users/5',json={'role':'STUDENT'})
  record('Q26','Last admin cannot demote themselves','409/403; admin retained',{'http':response.status_code,'role':db.get(User,5).role},response.status_code in (403,409) and db.get(User,5).role=='ADMIN')
  app.dependency_overrides.clear()
 db.close();engine.dispose()
print(json.dumps(rows,ensure_ascii=False,default=str))
'@ | python -X utf8 -
```

## 13. Phần chưa thể kết luận và bàn giao

- **UNVERIFIED**: PostgreSQL applied migrations/schema/triggers/locks; Cognito pool/IAM/invites/OTP/revocation thật; API Gateway authorizer deploy; S3 upload/playback/Range; EventBridge/Step Functions workers; Transcribe/Bedrock thật; CloudWatch/cost; browser wiring đầy đủ 56 màn.
- Các số liệu API là snapshot local tại thời điểm audit, không khẳng định deployed Lambda/container đang phục vụ cùng source.
- Không đổi source, không tự tạo endpoint hoặc migration, không tự sửa Contract v6 hay chạy AWS/RDS. Chỉ tạo **`agent/output/API_CONTRACT_IMPLEMENTATION_AUDIT.md`**.
- Test failures, observations vi phạm và số liệu thiếu bằng chứng được giữ nguyên để nhóm lập nhiệm vụ tiếp; chỉ nâng DONE khi các tiêu chí cụ thể ở bảng API/backlog có bằng chứng đạt.

