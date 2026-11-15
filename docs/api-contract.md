# LearnCloud — API Contract v6 (đối chiếu 56 màn hình)

> **Phiên bản:** Draft v6 — 09/11/2026  
> **Mục đích:** Chốt giao diện trao đổi dữ liệu giữa React, FastAPI, Cognito và các dịch vụ AWS để triển khai **56 màn hình đã cung cấp**.  
> **Đầu vào:** `screens.zip` (01–56.png); `api-contract(1).md` (Draft v5, 30/10/2026); `LEARNCLOUD_YEU_CAU_VA_LOGIC_NGHIEP_VU.md`; ba PDF thiết kế/tiến độ của LearnCloud; báo cáo kiểm toán `INSTRUCTOR_AUTH_AUDIT.md` (08/11/2026, source commit `ae20df5`).  
> **Tình trạng:** **DỰ THẢO CẦN NHÓM DUYỆT**. Đã hoàn thiện bản đặc tả, **không thay đổi source code, database, API Gateway hoặc AWS**.  
> **Người cần review:** Huy (Backend/auth), Hùng (Frontend), Tuấn (Quiz/AI/Tutor), Dũng (Cognito/AWS/điều phối).

## 0. Cách đọc và giới hạn bằng chứng

### 0.1. Quy ước trạng thái (không đánh đồng route với tính năng hoàn chỉnh)

| Ký hiệu | Ý nghĩa |
|---|---|
| **ROUTE** | Có method/path trong Backend được báo cáo kiểm toán xác nhận. Không có nghĩa đã an toàn hoặc pass end-to-end. |
| **PARTIAL** | Có route, nhưng còn thiếu điều kiện nghiệp vụ, auth hoặc kiểm chứng triển khai. |
| **MISSING** | Chưa thấy route trong bản source được kiểm toán; cần xây dựng nếu chức năng UI yêu cầu. |
| **EXTERNAL** | React dùng Cognito SDK/dịch vụ ngoài FastAPI; không tự coi là FastAPI API. |
| **PROPOSED** | Method/path hoặc schema **đề xuất cho v6**, chưa có cam kết triển khai. |
| **DECISION** | Nhóm cần quyết định trước khi khóa contract hoặc thực hiện migration. |

- Mã `screen NN` = file `NN.png` trong ZIP; **màn hình là yêu cầu sản phẩm**, không phải bằng chứng code đã xong.
- Danh sách **ROUTE** dựa trên kiểm toán mã nguồn ngày 08/11/2026: **42 `APIRoute` được đăng ký nhưng chỉ 35 cặp method/path duy nhất**, do bảy route review đăng ký lặp. **Chưa đọc lại OpenAPI của commit mới hơn và chưa kiểm chứng RDS/AWS production**.
- **Chưa xác minh request/response Pydantic chính xác của tất cả route**. Những JSON được đánh dấu `ĐỀ XUẤT` trong tài liệu là contract mục tiêu, **không được giả định là schema hiện tại**. Trước khi sửa code, phải so với `GET /openapi.json` từ môi trường đang chạy, routers và schemas.
- V5 dùng một số tên endpoint cũ hoặc trạng thái triển khai sai; v6 ghi **đường dẫn thực** và tách hẳn endpoint **đề xuất**.
- Các màn hình 01–56 đã được rà soát theo tên và hành vi hiển thị; những dữ liệu không thể suy ra chắc chắn từ ảnh được đánh dấu `DECISION`.

### 0.2. Nguyên tắc tương thích và bảo mật

1. Giữ method/path của các route đang có; thêm endpoint mới chỉ khi thực sự thiếu chức năng. **Không lặng lẽ đổi path** vì màn hình dùng tên khác.
2. Request/response dạng JSON `snake_case`, định danh Course/Section/Lesson số nguyên như Backend hiện tại; dùng UTC ISO-8601 cho timestamp; trả dữ liệu tối thiểu cần cho UI.
3. Backend xác minh JWT và lấy danh tính từ token; `role`, `user_id`, `instructor_id`, `student_id` **không được tin từ body/query/header tự chọn**. `X-Demo-User` chỉ là legacy đang có lỗ hổng P0, **không phải contract được phép dùng**.
4. `INSTRUCTOR` chỉ sửa/quản lý tài nguyên mình sở hữu; `STUDENT` chỉ học khi course/lesson đã publish, đã enroll và section đã unlock; `ADMIN` quản lý tài khoản/vận hành, không tự động được sửa khóa học của mọi giảng viên.
5. Không trả đáp án quiz cho Student **trước submit**. Nội dung nháp của AI, raw video và tài nguyên private không được lộ qua public API.
6. Không truyền byte MP4 qua FastAPI: browser PUT trực tiếp lên S3 bằng URL tạm; URL ký **không được ghi vào logs/database**.
7. Chuẩn lỗi mong muốn: `{ "detail": "...", "code": "MACHINE_READABLE_CODE", "request_id": "..." }`; khi chuẩn hóa phải kiểm tương thích format lỗi hiện tại, **không thay toàn bộ ngay**.
8. `401`: token thiếu/sai/hết hạn; `403`: thiếu role, ownership, enrollment/unlock; `404`: không tồn tại hoặc cố ý che tài nguyên; `409`: sai trạng thái nghiệp vụ; `422`: dữ liệu không hợp lệ; `429`: quá quota; `502/503`: lỗi dependency. **Chốt một chính sách 403/404 thống nhất** để tránh lộ tài nguyên.

### 1. Danh sách API FastAPI

| STT | Nhóm | Method | Endpoint | Quyền | Trạng thái | Ưu tiên |
|---:|---|---|---|---|---|---|
| 1 | System | GET | `/health` | Public | ROUTE | P2 |
| 2 | Auth | POST | `/auth/register` | Public | ROUTE (local) | P1 |
| 3 | Auth | POST | `/auth/login` | Public | ROUTE (local) | P1 |
| 4 | Auth | GET | `/auth/me` | User | PARTIAL | P0 |
| 5 | Profile | PATCH | `/users/me` | User | PROPOSED | P1 |
| 6 | Course | GET | `/courses` | Public | ROUTE | P1 |
| 7 | Course | GET | `/courses/{course_id}` | Public | PARTIAL | P1 |
| 8 | Course | POST | `/courses` | Instructor | PARTIAL | P1 |
| 9 | Course | PATCH | `/courses/{course_id}` | Instructor Owner | PARTIAL | P1 |
| 10 | Course | POST | `/courses/{course_id}/publish` | Instructor Owner | PARTIAL | P1 |
| 11 | Course | POST | `/courses/{course_id}/unpublish` | Instructor Owner | DECISION | P2 |
| 12 | Course | GET | `/instructor/courses` | Instructor | MISSING | P1 |
| 13 | Course | GET | `/instructor/courses/{course_id}` | Instructor Owner | PROPOSED | P1 |
| 14 | Course | GET | `/students/me/courses` | Student | MISSING | P1 |
| 15 | Section | POST | `/courses/{course_id}/sections` | Instructor Owner | PARTIAL | P1 |
| 16 | Section | GET | `/courses/{course_id}/sections` | User | PARTIAL | P1 |
| 17 | Lesson | POST | `/sections/{section_id}/lessons` | Instructor Owner | PARTIAL | P1 |
| 18 | Lesson | GET | `/sections/{section_id}/lessons` | Student / Instructor | PARTIAL | P1 |
| 19 | Lesson | GET | `/lessons/{lesson_id}` | Student / Instructor | PARTIAL | P1 |
| 20 | Lesson | PATCH | `/lessons/{lesson_id}` | Instructor Owner | PARTIAL | P1 |
| 21 | Enrollment | POST | `/courses/{course_id}/enroll` | Student | PARTIAL | P1 |
| 22 | Progress | PUT | `/lessons/{lesson_id}/progress` | Student | MISSING | P1 |
| 23 | Progress | GET | `/courses/{course_id}/progress` | Student | MISSING | P1 |
| 24 | Progress | GET | `/students/me/progress` | Student | PROPOSED | P1 |
| 25 | Upload | POST | `/lessons/{lesson_id}/upload-url` | Instructor Owner | PARTIAL | P1 |
| 26 | Upload | POST | `/lessons/{lesson_id}/confirm-upload` | Instructor Owner | DECISION | P1 |
| 27 | Video | GET | `/lessons/{lesson_id}/video-url` | Student / Instructor | PARTIAL | P1 |
| 28 | Processing | GET | `/lessons/{lesson_id}/processing-status` | Instructor Owner | PARTIAL | P1 |
| 29 | Processing | POST | `/lessons/{lesson_id}/retry` | Instructor Owner / Admin* | PARTIAL | P1 |
| 30 | AI Review | POST | `/lessons/{lesson_id}/review-drafts` | Instructor Owner | PARTIAL | P1 |
| 31 | AI Review | GET | `/lessons/{lesson_id}/review-draft` | Instructor Owner | PARTIAL | P1 |
| 32 | AI Review | PUT | `/lessons/{lesson_id}/review-draft` | Instructor Owner | PARTIAL | P1 |
| 33 | AI Review | POST | `/lessons/{lesson_id}/review-draft/approvals` | Instructor Owner | PARTIAL | P1 |
| 34 | AI Review | GET | `/lessons/{lesson_id}/ai-content` | Instructor Owner | PARTIAL | P1 |
| 35 | AI Review | PATCH | `/lessons/{lesson_id}/ai-content` | Instructor Owner | PARTIAL | P1 |
| 36 | AI Review | POST | `/lessons/{lesson_id}/approve` | Instructor Owner | PARTIAL | P1 |
| 37 | AI Review | GET | `/instructor/review-queue` | Instructor | MISSING | P1 |
| 38 | AI Review | GET | `/instructor/courses/{course_id}/publish-readiness` | Instructor Owner | PROPOSED | P2 |
| 39 | Flashcard | GET | `/sections/{section_id}/flashcards` | Student | PROPOSED | P1 |
| 40 | Flashcard | POST | `/flashcards/{flashcard_id}/reviews` | Student | PROPOSED | P1 |
| 41 | Flashcard | GET | `/courses/{course_id}/flashcards` | Student | PROPOSED | P2 |
| 42 | Quiz | GET | `/sections/{section_id}/quiz` | Student | PARTIAL | P1 |
| 43 | Quiz | POST | `/quizzes/{quiz_id}/attempts` | Student | PARTIAL | P1 |
| 44 | Quiz | GET | `/student/quizzes/history` | Student | ROUTE | P1 |
| 45 | Unlock | GET | `/courses/{course_id}/unlock-status` | Student | PARTIAL | P1 |
| 46 | AI Tutor | POST | `/tutor/sessions` | Student | PARTIAL | P1 |
| 47 | AI Tutor | POST | `/tutor/sessions/{session_id}/messages` | Student | PARTIAL | P1 |
| 48 | AI Tutor | POST | `/tutor/sessions/{session_id}/practice-attempts` | Student | PARTIAL | P1 |
| 49 | AI Tutor | GET | `/tutor/sessions/{session_id}` | Student | PROPOSED | P1 |
| 50 | Analytics | GET | `/instructor/dashboard` | Instructor | MISSING | P1 |
| 51 | Analytics | GET | `/instructor/courses/{course_id}/analytics` | Instructor Owner | PARTIAL | P1 |
| 52 | Analytics | GET | `/instructor/courses/{course_id}/students` | Instructor Owner | PROPOSED | P1 |
| 53 | Analytics | GET | `/instructor/courses/{course_id}/students/{student_id}/analytics` | Instructor Owner | PROPOSED | P1 |
| 54 | Admin | GET | `/admin/users` | Admin | MISSING | P1 |
| 55 | Admin | POST | `/admin/users` | Admin | MISSING | P1 |
| 56 | Admin | PATCH | `/admin/users/{user_id}` | Admin | MISSING | P1 |
| 59 | Admin | PATCH | `/admin/users/{user_id}/status` | Active Admin | ROUTE (source; unverified in AWS) | P1 |
| 57 | Admin | POST | `/admin/users/{user_id}/reset-password` | Admin | MISSING | P1 |
| 58 | Admin | GET | `/admin/operations/summary` | Admin | PROPOSED | P2 |
| 59 | Admin | GET | `/admin/operations/jobs` | Admin | PROPOSED | P2 |
| 60 | Admin | GET | `/admin/operations/jobs/{job_id}` | Admin | PROPOSED | P2 |

*Quyền Admin tại API retry phải tuân theo chính sách được nhóm chốt. Không mặc định Admin sở hữu mọi khóa học.*

---

## 1. Truy vết 56 màn hình → dữ liệu và API

**Bảng này là yêu cầu của UI.** API ghi bên cạnh có thể là `ROUTE`, `EXTERNAL` hoặc `PROPOSED`; tra bảng trạng thái ở mục 2–10 trước khi sử dụng.

| Screen | Màn hình/hành động | API hoặc dịch vụ cần dùng | Mức độ hiện tại |
|---|---|---|---|
| 01 | Đăng nhập | Cognito `signIn` **hoặc** legacy `POST /auth/login`; `GET /auth/me` | EXTERNAL đích / PARTIAL local |
| 02 | Đăng ký học viên | Cognito `signUp` (đích); legacy `POST /auth/register` STUDENT-only | EXTERNAL đích / ROUTE local |
| 03 | Nhập OTP xác minh email, gửi lại mã | Cognito `confirmSignUp`, `resendSignUpCode` | EXTERNAL, chưa xác minh pool |
| 04 | Đăng ký thành công | Kết quả xác minh từ Cognito / UI state | Không cần route riêng |
| 05 | Quên mật khẩu, gửi mã | Cognito `resetPassword` | EXTERNAL |
| 06 | Nhập OTP và mật khẩu mới | Cognito `confirmResetPassword` | EXTERNAL |
| 07 | Khám phá khóa học, tìm/lọc | `GET /courses`, tham số tìm kiếm/lọc đề xuất | ROUTE / PROPOSED filter |
| 08 | Chi tiết khóa học, outline, đăng ký | `GET /courses/{id}`, `POST /courses/{id}/enroll` | ROUTE, public outline cần lọc draft |
| 09 | Modal enroll thành công | Kết quả `POST /courses/{id}/enroll` | ROUTE |
| 10 | Khóa học của tôi, tiến độ | `GET /students/me/courses` | MISSING |
| 11 | Lộ trình section/lesson, khóa/mở | `GET /courses/{id}/sections`, `GET /sections/{id}/lessons`, `GET /courses/{id}/unlock-status` | ROUTE/PARTIAL |
| 12 | Xem video, transcript, tóm tắt | `GET /lessons/{id}`, `GET /lessons/{id}/video-url`, progress | PARTIAL; progress MISSING |
| 13 | Section bị khóa | `GET /courses/{id}/unlock-status` + 403/404 từ API lesson/video | ROUTE/PARTIAL |
| 14 | Flashcard mặt trước | `GET /sections/{id}/flashcards` hoặc danh sách theo course | MISSING |
| 15 | Flashcard mặt sau, Đã nhớ/Cần ôn | `POST /flashcards/{id}/reviews` (đề xuất) | MISSING |
| 16 | Tổng kết bộ Flashcard | Tổng hợp từ danh sách/reviews hoặc API summary | MISSING |
| 17 | Giới thiệu checkpoint | `GET /sections/{id}/quiz`, unlock status | PARTIAL |
| 18 | Làm checkpoint | `GET /sections/{id}/quiz` (không có đáp án) | PARTIAL |
| 19 | Xác nhận nộp | `POST /quizzes/{id}/attempts` | PARTIAL |
| 20 | Kết quả đạt ≥80% | Response attempt + `GET /courses/{id}/unlock-status` | PARTIAL |
| 21 | Kết quả 50–79% | Response attempt: cho retry ngay hoặc Tutor | PARTIAL; quy tắc cần xác nhận |
| 22 | Kết quả dưới 50% | Response attempt: bắt buộc remediation/practice | PARTIAL; guard chưa được xác nhận |
| 23 | Tutor giải thích các câu sai | `POST /tutor/sessions`; `POST /tutor/sessions/{id}/messages` | ROUTE, auth PARTIAL |
| 24 | Tutor gợi ý video/flashcard liên quan | Response session/message có resource refs hợp lệ | PROPOSED schema, không nhất thiết thêm route |
| 25 | Tutor practice 3 câu | `POST /tutor/sessions/{id}/practice-attempts` + dữ liệu practice | ROUTE; tiêu chí 2/3 là yêu cầu UI |
| 26 | Practice đạt ≥2/3, mở retry | Response practice `can_retry_checkpoint=true` | PROPOSED response/guard |
| 27 | Practice dưới 2/3, phải luyện lại | Response practice `can_retry_checkpoint=false` | PROPOSED response/guard |
| 28 | Hoàn thành khóa học | `GET /courses/{id}/progress` hoặc `GET /students/me/courses` | MISSING |
| 29 | Tiến độ học tập và lịch sử quiz | `GET /students/me/progress`; `GET /student/quizzes/history` | MISSING / ROUTE |
| 30 | Instructor dashboard | `GET /instructor/dashboard` (đề xuất); list/course/analytics | MISSING phần tổng hợp |
| 31 | Danh sách course của Instructor | `GET /instructor/courses` | MISSING |
| 32 | Tạo course và ảnh bìa tùy chọn | `POST /courses`; quy trình upload ảnh bìa cần chốt | ROUTE / DECISION |
| 33 | Quản lý cấu trúc course, publish | `GET /instructor/courses/{id}` (đề xuất), `POST /courses/{id}/sections`, `PATCH /courses/{id}` | MISSING detail draft / ROUTE create/edit |
| 34 | Thêm lesson | `POST /sections/{id}/lessons` | ROUTE |
| 35 | Upload video giảng viên | `POST /lessons/{id}/upload-url` + PUT presigned URL đến S3 | ROUTE + S3; confirm-upload DECISION |
| 36 | Xem trạng thái xử lý | `GET /lessons/{id}/processing-status` | ROUTE |
| 37 | Pipeline FAILED, chạy lại | `POST /lessons/{id}/retry` | ROUTE; AWS dispatch chưa xác minh |
| 38 | Danh sách học liệu AI chờ duyệt | `GET /instructor/review-queue` (đề xuất) | MISSING |
| 39 | Review transcript + summary | `GET /lessons/{id}/ai-content`, `PATCH /lessons/{id}/ai-content` | ROUTE; JSON phải so OpenAPI |
| 40 | Review key concepts | Như màn 39 | ROUTE; cần schema item |
| 41 | Review flashcards | Như màn 39, **phải bổ sung flashcard vào review/output** | PARTIAL / DECISION model |
| 42 | Review quiz/đáp án + nguồn | Như màn 39 | ROUTE; không rò correct_answer sang student |
| 43 | Duyệt học liệu (modal) | `POST /lessons/{id}/approve` hoặc review-draft approvals | ROUTE; trạng thái approval DECISION |
| 44 | Publish course (modal kiểm tra điều kiện) | `POST /courses/{id}/publish`, tùy chọn `GET /instructor/courses/{id}/publish-readiness` | ROUTE / PROPOSED readiness |
| 45 | Danh sách học viên & báo cáo course | `GET /instructor/courses/{id}/analytics`, `GET /instructor/courses/{id}/students` | ROUTE / MISSING |
| 46 | Chi tiết tiến độ học viên của course | `GET /instructor/courses/{id}/students/{student_id}/analytics` | MISSING |
| 47 | Admin danh sách tài khoản, lọc | `GET /admin/users` | MISSING |
| 48 | Admin tạo Instructor/Admin | `POST /admin/users` (đề xuất); Cognito admin provision đằng sau | MISSING |
| 49 | Xác nhận cấp role đặc quyền | Bước xác nhận UI + `POST /admin/users` | Không cần endpoint xác nhận riêng nếu một transaction |
| 50 | Thông báo tài khoản vừa tạo | Response `POST /admin/users` | MISSING; không lộ password lâu dài |
| 51 | Admin sửa role/trạng thái, reset mật khẩu | `PATCH /admin/users/{id}`, `POST /admin/users/{id}/reset-password` (đề xuất) | MISSING |
| 52 | Bảng vai trò và quyền | Policy matrix cố định từ contract, tùy chọn `GET /admin/roles` | Không cần backend riêng nếu tĩnh |
| 53 | Admin monitor pipeline, logs, cost alerts | `GET /admin/operations/summary`, `GET /admin/operations/jobs` | MISSING; CloudWatch/AWS adapter |
| 54 | Modal logs của job | `GET /admin/operations/jobs/{job_id}` (đề xuất) | MISSING |
| 55 | Hồ sơ cá nhân, đổi mật khẩu | `GET /auth/me`; `PATCH /users/me` (đề xuất); Cognito `updatePassword` | PARTIAL / MISSING / EXTERNAL |
| 56 | Trang Không có quyền truy cập | HTTP `401/403` chuẩn từ các API bảo vệ | UI có; Backend auth P0 |

> **Screen 25–27:** UI thể hiện ba câu practice và ngưỡng **2/3 câu đúng**. Đây là **yêu cầu cần hiện thực/kiểm chứng ở Backend**, không khẳng định `tutor_service.py` hiện đã thực thi đủ ngưỡng.

---

## 2. Kiểm kê API FastAPI đã có — nguồn thực tế để giữ tương thích

**Snapshot kiểm toán 08/11/2026.** Ký hiệu `PARTIAL` ở cột cuối nói rõ chỗ thiếu; vẫn là route đã tồn tại. `INSTRUCTOR` được viết tắt `I`, `STUDENT` là `S`, `USER` là `U`, `PUBLIC` là `P`.

| # | Method + path thực tế | Quyền mục tiêu | Tình trạng / điểm cần lưu ý |
|---:|---|---|---|
| 01 | `GET /health` | P | ROUTE; health tĩnh, không probe DB |
| 02 | `POST /auth/register` | P | ROUTE; **chỉ tạo STUDENT**, role khác bị 422 |
| 03 | `POST /auth/login` | P | ROUTE; phát JWT **local**, chưa bảo vệ API nghiệp vụ |
| 04 | `GET /auth/me` | U | PARTIAL; lấy identity từ `X-Demo-User`, không xác minh Bearer |
| 05 | `GET /courses` | P | ROUTE; hiện chỉ trả published course; chưa chắc có filter/search |
| 06 | `POST /courses` | I | PARTIAL; guard role/owner phụ thuộc identity demo |
| 07 | `GET /courses/{course_id}` | P | PARTIAL; published course nhưng có thể lộ metadata lesson chưa duyệt |
| 08 | `PATCH /courses/{course_id}` | I-owner | PARTIAL; guard theo identity demo |
| 09 | `POST /courses/{course_id}/publish` | I-owner | PARTIAL; migration và policy approve/publish chưa thống nhất |
| 10 | `POST /courses/{course_id}/sections` | I-owner | PARTIAL; guard theo identity demo |
| 11 | `GET /courses/{course_id}/sections` | U | PARTIAL; thiếu bảo đảm quyền enroll/unlock tùy dữ liệu trả |
| 12 | `POST /sections/{section_id}/lessons` | I-owner | PARTIAL; guard theo identity demo |
| 13 | `GET /sections/{section_id}/lessons` | S enrolled/unlocked hoặc I-owner | PARTIAL; student có thể đọc section locked |
| 14 | `GET /lessons/{lesson_id}` | S enrolled/unlocked hoặc I-owner | PARTIAL; thiếu unlock |
| 15 | `PATCH /lessons/{lesson_id}` | I-owner | PARTIAL; guard theo identity demo |
| 16 | `POST /lessons/{lesson_id}/upload-url` | I-owner | PARTIAL; route + adapter, auth phải sửa |
| 17 | `GET /lessons/{lesson_id}/processing-status` | I-owner | PARTIAL; chưa chứng minh toàn pipeline AWS E2E |
| 18 | `POST /lessons/{lesson_id}/retry` | I-owner; Admin theo policy | PARTIAL; retry/dispatch AWS chưa nghiệm thu |
| 19 | `GET /lessons/{lesson_id}/video-url` | S enrolled/unlocked hoặc I-owner | PARTIAL; thiếu unlock; trả URL có hạn |
| 20 | `POST /lessons/{lesson_id}/review-drafts` | I-owner | PARTIAL; review với AI có mock/adapter |
| 21 | `GET /lessons/{lesson_id}/review-draft` | I-owner | PARTIAL |
| 22 | `PUT /lessons/{lesson_id}/review-draft` | I-owner | PARTIAL |
| 23 | `POST /lessons/{lesson_id}/review-draft/approvals` | I-owner | PARTIAL |
| 24 | `GET /lessons/{lesson_id}/ai-content` | I-owner | PARTIAL; schema cần đối chiếu với UI summary/concepts/flashcards/quiz |
| 25 | `PATCH /lessons/{lesson_id}/ai-content` | I-owner | PARTIAL; schema cập nhật cần đối chiếu, có whitelist field |
| 26 | `POST /lessons/{lesson_id}/approve` | I-owner | PARTIAL; dùng chung logic approve_draft; không tạo 2 quy trình song song |
| 27 | `GET /instructor/courses/{course_id}/analytics` | I-owner | PARTIAL; có analytics cơ bản, chưa chắc đủ cho screen 45–46 |
| 28 | `POST /courses/{course_id}/enroll` | S | PARTIAL; kiểm course published và enroll trùng; auth demo |
| 29 | `GET /sections/{section_id}/quiz` | S | PARTIAL; **thiếu kiểm enrollment/course publish** |
| 30 | `POST /quizzes/{quiz_id}/attempts` | S | PARTIAL; **thiếu enrollment/course publish**, có thể ghi attempt sai phạm vi |
| 31 | `GET /student/quizzes/history` | S | ROUTE/PARTIAL auth; **đây là path thật**, không phải `/students/me/quiz-history` |
| 32 | `GET /courses/{course_id}/unlock-status` | S | PARTIAL; thiếu enrollment/course publish |
| 33 | `POST /tutor/sessions` | S-owner attempt | PARTIAL; đã có route và kiểm attempt/enrollment nhưng auth demo |
| 34 | `POST /tutor/sessions/{session_id}/messages` | S-owner session | PARTIAL; route có, chưa nghiệm thu Bedrock thật |
| 35 | `POST /tutor/sessions/{session_id}/practice-attempts` | S-owner session | PARTIAL; **có route**, nhưng cần test chặt điều kiện 2/3 và retry |

**Đường dẫn review:** Hiện tại có cả `/review-draft[s]` và `/ai-content` + `/approve`. Không tạo thêm endpoint trùng. Trong v6, **Frontend nên dùng nhóm `/ai-content` và `/approve` hiện có** để giảm số contract; giữ nhóm review-draft cũ tới khi đánh giá tương thích, rồi deprecate theo phiên bản, không xóa ngay.

**Các endpoint KHÔNG có trong snapshot:** `GET /instructor/courses`, `GET /students/me/courses`, `/admin/users`, `POST /lessons/{id}/confirm-upload`, `PUT /lessons/{id}/progress`, `GET /courses/{id}/progress`. `backend/app/api/progress.py` rỗng và chưa được include. Không ghi những path này là “đã làm”.

**Bằng chứng bảo mật bắt buộc xử lý trước public:** `get_current_user()` hiện dùng `X-Demo-User` và mặc định ID 1, bỏ qua JWT phát ra sau login. Những kiểm tra `require_instructor`, ownership, `require_student` có code nhưng có thể bị vượt qua bằng giả mạo ID. Chức năng auth/role được đánh dấu **PARTIAL / P0**, không phải DONE.

---

## 3. Auth, profile và quản trị tài khoản (screen 01–06, 47–52, 55–56)

### 3.1. Contract xác thực đích: Cognito + FastAPI

| Thao tác | Nơi xử lý đề nghị | Contract / lưu ý |
|---|---|---|
| Đăng ký Student | **EXTERNAL** Cognito | React `signUp({ username: email, password, options: { userAttributes: { email, name } } })` hoặc cấu hình tương ứng; không cho chọn `INSTRUCTOR` trên public signup |
| Xác thực email | **EXTERNAL** Cognito | `confirmSignUp({ username, confirmationCode })`, `resendSignUpCode` |
| Đăng nhập | **EXTERNAL** Cognito | `signIn`; lấy access token phù hợp với API; **không gửi ID token thay access token khi authorizer yêu cầu access token** |
| Quên mật khẩu | **EXTERNAL** Cognito | `resetPassword`, `confirmResetPassword` qua OTP |
| Đổi mật khẩu đã đăng nhập | **EXTERNAL** Cognito | `updatePassword`, chính sách Cognito và đăng nhập lại nếu cần |
| Backend đọc user hiện tại | `GET /auth/me` **ROUTE, sửa P0** | Xác minh token, map `sub` đã xác minh tới `users.cognito_sub`, lấy role từ nguồn đã chốt |
| Cập nhật hồ sơ cơ bản | `PATCH /users/me` **PROPOSED** | Chỉ sửa `full_name`/thuộc tính cho phép; email cần quy trình xác minh riêng |
| Cấp tài khoản Instructor/Admin | `POST /admin/users` **PROPOSED** | Chỉ ADMIN; service provision Cognito rồi đồng bộ DB, xử lý rollback/idempotency |
| Sửa role/trạng thái | `PATCH /admin/users/{user_id}` **PROPOSED** | Admin, ghi audit, revoke/disable session theo chính sách |
| Khôi phục mật khẩu tài khoản bởi Admin | `POST /admin/users/{user_id}/reset-password` **PROPOSED** | Dùng Cognito administrative reset/invite; không trả mật khẩu hiện tại |

**Local đang có** `POST /auth/register` và `POST /auth/login` bằng Argon2id/JWT HS256. Đây là đường local thực tế, **không phải bằng chứng Cognito đã được tích hợp**. Khi nhóm chọn Cognito cho production cần chốt deprecate/disable các đường local đó ngoài môi trường dev; **không vận hành hai nguồn mật khẩu song song cho cùng người dùng**.

**Trước khi public:** sửa FastAPI `get_current_user` để `Authorization: Bearer <JWT>` được kiểm signature (JWKS của đúng User Pool khi dùng Cognito), issuer, audience/client, token_use và expiration; map `sub` sang tài khoản nội bộ, không có fallback user 1; `X-Demo-User` không bao giờ chọn danh tính production. Không tự tin vào role của payload do client gửi. Mô hình role: PostgreSQL là nguồn role nghiệp vụ, hoặc map nhóm Cognito đã xác minh theo policy rõ ràng; không dùng cả hai mà không có quy tắc ưu tiên.

### 3.2. Schema mục tiêu (ĐỀ XUẤT, phải khớp với model thật)

`GET /auth/me` — phản hồi cho navbar, phân tuyến và Screen 55:

```json
{
  "id": 23,
  "full_name": "Le Thu Ha",
  "email": "ha@example.com",
  "email_verified": true,
  "role": "STUDENT",
  "status": "ACTIVE"
}
```

`POST /admin/users` — tạo Instructor/Admin qua Admin (đề xuất):

```http
POST /admin/users
Authorization: Bearer <admin-access-token>
Content-Type: application/json
```

```json
{
  "full_name": "Tran Thi Mai",
  "email": "mai@example.com",
  "role": "INSTRUCTOR"
}
```

```json
{
  "id": 33,
  "email": "mai@example.com",
  "role": "INSTRUCTOR",
  "status": "INVITED",
  "invitation_sent": true
}
```

- **Không** cho user tự set role bằng public signup, không nhận `instructor_id` tùy ý từ client.
- Màn 48–50 hiển thị mật khẩu khởi tạo. Nếu sử dụng Cognito, **ưu tiên invite / password tạm dùng một lần qua kênh an toàn và buộc đổi ở lần đăng nhập đầu**; không lưu/trả lại mật khẩu sau khi tạo, không log, không hiển thị trong danh sách. Màn 50 nên sửa wording theo invite (cần Hùng/Dũng chốt).
- Màn 51: `PATCH /admin/users/{id}` nhận `role` và/hoặc `is_active`; không cho Admin vô tình tự khóa tài khoản quản trị cuối cùng; thay đổi đặc quyền yêu cầu audit. Reset password là thao tác riêng với Cognito, không tự sinh SQL update mật khẩu từ Frontend.
- Màn 52: role matrix trong UI là **thông tin**, không phải nguồn phân quyền. Nếu policy tĩnh, **không cần `GET /admin/roles`**; nếu động thì thêm sau.
- Màn 56: `401/403` phải đến từ backend thực, không chỉ route guard React.

### 3.3. Chính sách quyền v6

| Hành vi | Guest | Student | Instructor (owner) | Admin |
|---|---:|---:|---:|---:|
| Xem catalog course published | Có | Có | Có | Có |
| Đăng ký/học/checkpoint/Tutor | Không | Có, đủ điều kiện | Không mặc định | Không mặc định |
| Tạo/sửa/upload/review/publish course | Không | Không | Có, course của mình | Không mặc định |
| Xem analytics/học viên course | Không | Không | Có, course của mình | Không mặc định |
| Tạo/đổi role/khóa tài khoản | Không | Không | Không | Có |
| Xem job/monitor/log vận hành | Không | Không | Không | Có |
| Retry pipeline lỗi | Không | Không | Owner có; Admin là ngoại lệ cần policy | Có thể, nếu policy chốt |

**DECISION AUTH-1:** Chọn Cognito là xác thực production, `STUDENT` tự đăng ký; `INSTRUCTOR` và `ADMIN` chỉ do Admin provision như Screen 48/52. Đây là hướng đề xuất phù hợp UI; không khẳng định đã có API hoặc User Pool thật.

---

## 4. Course, Section, Lesson & Enrollment (screen 07–13, 28, 30–34, 44)

### 4.1. API hiện có và phần mở rộng cần thiết

| API | Trạng thái | Contract mong muốn |
|---|---|---|
| `GET /courses` | ROUTE | Public catalog course `PUBLISHED`; **PROPOSED** query `q`, `page`, `limit`; không làm lộ draft lesson/AI |
| `GET /courses/{id}` | PARTIAL | Detail course đã publish + outline công khai đã lọc lesson draft; chưa enroll vẫn xem giới thiệu được |
| `POST /courses/{id}/enroll` | ROUTE | Chỉ Student, course published, chống enrollment trùng/idempotent theo policy |
| `GET /students/me/courses` | **MISSING/P1** | Course đã enroll, tiến độ %, trạng thái `IN_PROGRESS/COMPLETED` cho screen 10 |
| `GET /instructor/dashboard` | **MISSING/P1** | Tổng khóa học, lesson chờ duyệt, student, checkpoint summary ở screen 30 |
| `GET /instructor/courses` | **MISSING/P1** | Danh sách course **kể cả DRAFT** của instructor đang đăng nhập |
| `GET /instructor/courses/{id}` | **PROPOSED/P1** | Detail draft và section/lesson của owner; **không mở public** `GET /courses/{id}` ra draft |
| `POST /courses` | ROUTE | Instructor tạo, tự gán `instructor_id` từ identity |
| `PATCH /courses/{id}` | ROUTE | Chỉ owner sửa metadata hợp lệ, không tự publish |
| `POST /courses/{id}/sections` | ROUTE | Owner tạo section có thứ tự |
| `GET /courses/{id}/sections` | PARTIAL | Phân biệt outline public và học theo enrollment/unlock |
| `POST /sections/{id}/lessons` | ROUTE | Owner tạo lesson DRAFT trong section |
| `GET /sections/{id}/lessons` | PARTIAL | Student enrolled nhưng locked không đọc lesson nhạy cảm |
| `GET /lessons/{id}` | PARTIAL | Owner xem draft; Student chỉ thấy lesson published+enrolled+unlocked |
| `PATCH /lessons/{id}` | ROUTE | Owner sửa lesson metadata, không làm bypass review/publish |
| `POST /courses/{id}/publish` | PARTIAL | Course chỉ publish khi đủ điều kiện học liệu/lesson; trả lỗi thiếu rõ ràng |
| `GET /instructor/courses/{id}/publish-readiness` | **PROPOSED/P2** | Cho modal Screen 44 biết số lesson đạt/chưa đạt trước khi bấm publish; cũng có thể gộp vào `GET /instructor/courses/{id}` |
| `POST /courses/{id}/unpublish` | **PROPOSED/P2** | Chỉ nếu nhóm duy trì yêu cầu unpublish của PDF; phải chốt ảnh hưởng enrollment/progress |

### 4.2. Ví dụ contract mục tiêu cho màn hình khóa học (ĐỀ XUẤT)

`GET /students/me/courses`:

```json
{
  "items": [
    {
      "id": 8,
      "title": "Cloud Computing cơ bản",
      "instructor_name": "Nguyen Van An",
      "progress_percent": 25,
      "completed_lessons": 2,
      "total_lessons": 8,
      "learning_status": "IN_PROGRESS"
    }
  ]
}
```

`GET /instructor/courses`:

```json
{
  "items": [
    {
      "id": 8,
      "title": "Cloud Computing cơ bản",
      "status": "DRAFT",
      "section_count": 2,
      "lesson_count": 8,
      "review_required_count": 1
    }
  ]
}
```

`GET /courses/{id}/unlock-status` là endpoint **đã có**, phải tái sử dụng; với Student, response mục tiêu nên chỉ rõ `section_id`, `is_unlocked`, `checkpoint_passed`, `prerequisite_section_id`. Không tạo API `unlock` để frontend tự mở; unlock do Backend tính từ điểm và trạng thái thực tế.

**Ảnh bìa screen 32:** có trường upload ảnh tùy chọn, nhưng chưa có bằng chứng endpoint cover upload. Quyết định dùng một URL đã upload sẵn/local asset cho MVP, hoặc thiết kế riêng presigned image-upload trước khi thêm API. Không chấp nhận URL tùy ý gây SSRF ở Backend.

---

## 5. Video Upload, Processing & Playback (screen 12, 35–37)

**Giữ trọng tâm và các ràng buộc quan trọng từ Contract v5.**

### 5.1. Luồng nghiệp vụ

```text
Instructor POST /lessons/{id}/upload-url
   └─ FastAPI xác minh instructor + ownership + trạng thái → Presigned PUT
       └─ Browser PUT file MP4 trực tiếp S3/private
           ├─ S3 ObjectCreated → EventBridge → Step Functions (theo kiến trúc đã chọn)
           │    └─ MediaConvert → Transcribe → Bedrock/AI worker → AI draft
           └─ Cơ chế xác nhận/đối chiếu upload với DB (cần chốt)
                └─ Lesson status → REVIEW_REQUIRED hoặc FAILED
Instructor GET /lessons/{id}/processing-status / POST .../retry
Instructor GET/PATCH AI draft → approve → publish
Student đủ quyền GET /lessons/{id}/video-url → S3 Presigned GET/CloudFront
```

**`PUT {presigned_url}` là S3 API, KHÔNG phải FastAPI endpoint.** S3 trả 200 sau PUT không có nghĩa AI pipeline hoàn thành và cũng không phải Instructor approve.

### 5.2. API & yêu cầu

| API | Trạng thái | Hành vi |
|---|---|---|
| `POST /lessons/{id}/upload-url` | ROUTE | Instructor owner; validate filename/MIME/size; cấp URL PUT, key, expiry; chỉ đường raw; không nhận byte video |
| `PUT {upload_url}` | EXTERNAL S3 | Upload MP4 bằng headers đúng chữ ký, không mang JWT FastAPI |
| `POST /lessons/{id}/confirm-upload` | **MISSING/DECISION** | V5 đề xuất xác nhận upload session, `HeadObject`, liên kết DB; **không được FE gọi như API đã có** |
| `GET /lessons/{id}/processing-status` | ROUTE | Trả status, retry_count, lỗi an toàn, updated_at; polling có điểm dừng |
| `POST /lessons/{id}/retry` | PARTIAL | Chỉ FAILED, owner/Admin theo policy, retry idempotent hoặc chống xử lý trùng |
| `GET /lessons/{id}/video-url` | PARTIAL | Student chỉ được cấp URL khi course/lesson published + enrolled + unlocked, Instructor owner được kiểm quyền; không dùng raw mặc định production |

**Giữ giới hạn v5 làm mặc định dự kiến:** MP4, `file_size > 0` và `≤ 500 MiB` lúc xin URL, presigned TTL ví dụ `900 giây`. Kích thước khai báo không đủ chứng minh kích thước object thật; cần `HeadObject`/quy trình xử lý tin cậy. `Content-Type` không chứng minh codec/bitstream hợp lệ. Phát video có thể trả 206 Range; không ghi/log URL ký.

**Response hiện có minh họa từ v5** (phải so `OpenAPI` trước khi coi exact schema):

```json
{
  "upload_url": "<presigned-put-url>",
  "object_key": "lessons/6/raw/<random-id>.mp4",
  "expires_in": 900,
  "method": "PUT",
  "content_type": "video/mp4"
}
```

```json
{
  "lesson_id": 8,
  "status": "PROCESSING",
  "retry_count": 0,
  "error_message": null,
  "updated_at": "2026-11-09T08:00:00Z"
}
```

**Upload confirm — quyết định kỹ thuật chưa khóa:**

- Nếu chọn `POST /lessons/{id}/confirm-upload`, `POST /upload-url` cần tạo `upload_id`/session server-side (hoặc token ràng buộc tương đương), bind đúng lesson+user+key+expiry; confirm phải idempotent, `HeadObject` đúng key, không tin `object_key` client tự nhập.
- Tránh dispatch kép khi dùng cả S3 EventBridge và confirm; **chỉ một nguồn khởi chạy workflow**. Nếu event đến trước confirm, có gate/timing/replay bảo đảm không mất job; chống duplicate event.
- Nếu **không** dùng confirm-upload, ghi rõ cơ chế sự kiện nào là nguồn xác thực upload và cách liên kết DB an toàn; xóa yêu cầu FE gọi confirm. **Không tự triển khai cả hai cách cùng lúc.**
- `lesson_upload_sessions` và migration của v5 là **đề xuất**, không phải bảng đã có.

**Playability:** chỉ dùng `processed_video_key` khi production phát video cho học viên; video raw chỉ dùng đường development có flag và vẫn kiểm quyền. Nếu dùng CloudFront Signed URL thay S3 Presigned GET thì phải cập nhật response khi quyết định triển khai, không đổi ngầm.

---

## 6. AI Review, Flashcards & Publishing (screen 38–44)

### 6.1. API cần dùng

| API | Trạng thái | Hành vi |
|---|---|---|
| `GET /instructor/review-queue` | **MISSING/P1** | Danh sách lesson `REVIEW_REQUIRED`, đang xử lý, failed, published của owner; sort/filter theo status |
| `GET /lessons/{id}/ai-content` | ROUTE/PARTIAL | Instructor owner lấy Transcript timestamp, Summary, Concepts, Quiz, **Flashcards mục tiêu** |
| `PATCH /lessons/{id}/ai-content` | ROUTE/PARTIAL | Lưu bản chỉnh sửa có validate; không tự publish; cần schema hỗ trợ flashcard |
| `POST /lessons/{id}/approve` | ROUTE/PARTIAL | Xác nhận bản nháp đủ và hợp lệ, checkpoint/quiz dữ liệu đúng; không public nếu course chưa publish |
| `GET/PUT/POST /lessons/{id}/review-draft[s]...` | ROUTE legacy | Các alias cũ; không tăng thêm call FE khi đã có `/ai-content`/`approve` |
| `POST /courses/{id}/publish` | ROUTE/PARTIAL | Chỉ owner, kiểm toàn bộ lesson/AI được duyệt, số lesson tối thiểu và video processing hợp lệ |

### 6.2. Dữ liệu review đích (ĐỀ XUẤT, không khẳng định schema đang trả)

```json
{
  "lesson_id": 6,
  "lesson_status": "REVIEW_REQUIRED",
  "review_status": "PENDING",
  "transcript": [
    {"chunk_id": "c1", "start_seconds": 15, "end_seconds": 34, "text": "VPC cung cấp mạng ảo..."}
  ],
  "summary": "Tóm tắt về VPC và subnet...",
  "key_concepts": [
    {"concept_id": "k1", "term": "Public subnet", "definition": "...", "source_chunk_id": "c1"}
  ],
  "flashcards": [
    {"flashcard_id": "f1", "front": "Public subnet là gì?", "back": "...", "source_chunk_id": "c1"}
  ],
  "quiz": {
    "questions": [
      {
        "question_id": "q1",
        "stem": "Thành phần nào quyết định đường đi của lưu lượng trong VPC?",
        "options": [{"id": "A", "text": "Security Group"}, {"id": "B", "text": "Route table"}],
        "correct_option_id": "B",
        "explanation": "Route table quy định tuyến đường.",
        "source_chunk_id": "c1"
      }
    ]
  }
}
```

**Mẫu trên rút gọn lựa chọn để dễ đọc; nghiệp vụ quiz thật yêu cầu 4 đáp án (A–D)** và phải được backend validate. Chỉ Instructor owner được nhận `correct_option_id` trước publish. Source timestamp lấy từ transcript, không yêu cầu LLM tự sáng tác thời gian.

**Screen 38–43** yêu cầu review cả Flashcard, nhưng Contract v5 chỉ nói flashcards như đề xuất và Backend chưa được kiểm toán xác nhận hỗ trợ đầy đủ. Đây là **gap chức năng AI/DB/Backend**, không chỉ sửa UI.

### 6.3. Trạng thái xử lý và xuất bản — hợp nhất khái niệm, giữ quyết định pending

**Vòng xử lý video/AI dùng trong mô tả:**

`DRAFT → UPLOADED → PROCESSING → TRANSCRIBING → AI_PROCESSING → REVIEW_REQUIRED`, với nhánh lỗi `FAILED` và `retry` quay lại xử lý.

**Hai khái niệm cần tách:**

- **`review_status`**: `PENDING`/`APPROVED` (logic giảng viên đã duyệt học liệu chưa).
- **`course.status`/`lesson.status`**: `DRAFT`/`PUBLISHED` (nội dung đã công bố cho học viên chưa).

**Hướng contract v6 đề xuất:** `approve` đánh dấu nội dung AI **đã duyệt** nhưng **chưa tự làm course public**; `POST /courses/{id}/publish` chỉ thành công nếu tất cả điều kiện được đáp ứng, sau đó nội dung đủ điều kiện được hiển thị Student. Đây là **mô hình logic đích**, không bắt buộc phải có cột `review_status` mới nếu DB hiện có đã lưu approval ở bảng review.

**DECISION REVIEW-1 (BẮT BUỘC):** hiện trong migration có **hai phiên bản 0004 xung đột** và v5 vừa nêu chuyển trạng thái approve `APPROVED` vừa nêu `PUBLISHED`. Không thể tuyên bố tên enum trạng thái cuối cùng đã khóa. Dũng/Huy/Tuấn cần chọn ánh xạ chính xác giữa `review_status`, `lesson.status`, `course.status` và sửa migration/test **trên PostgreSQL thử nghiệm**, không chạy trực tiếp RDS thật trước khi kiểm chứng.

**Publish readiness cho screen 44:** yêu cầu cho UI biết `approved_lessons`, `total_lessons`, `missing_items`, `can_publish`; có thể đặt trong instructor course detail để khỏi tạo route mới. `POST /courses/{id}/publish` phải **tự kiểm lại** và từ chối `409` nếu còn lesson thiếu video/học liệu duyệt.

---

## 7. Student Learning, Progress, Flashcard (screen 10–16, 28–29)

### 7.1. Course access & unlock

- Public/guest xem được tiêu đề, mô tả và outline đã lọc dữ liệu chưa publish, nhưng không nhận lesson payload private, transcript chưa duyệt, presigned playback.
- Student muốn xem lesson/quiz/video phải `enrollment ACTIVE`, `course PUBLISHED`, lesson `PUBLISHED` và section được unlock. **Không tin nút khóa trên UI**; API kiểm tra server-side.
- Section đầu mở sau khi enroll. Section `n+1` mở khi checkpoint của section `n` có attempt hợp lệ `score >= 80%`. Điểm là **theo từng Student**, không cập nhật global khóa học.

### 7.2. API progress và dữ liệu mong muốn

| API | Trạng thái | Màn hình |
|---|---|---|
| `PUT /lessons/{lesson_id}/progress` | **MISSING/P1** | 12, 29; ghi tiến độ lesson của Student hiện tại |
| `GET /courses/{course_id}/progress` | **MISSING/P1** | 10, 11, 28; tổng tiến độ khóa học + hoàn thành |
| `GET /students/me/progress` | **PROPOSED/P1** | 29; tổng hợp các course và lịch sử học |
| `GET /student/quizzes/history` | ROUTE | 29; lịch sử quiz **path hiện có** |
| `GET /students/me/courses` | MISSING | 10; course đã đăng ký |

`PUT /lessons/{lesson_id}/progress` — **ĐỀ XUẤT**:

```json
{
  "resume_position_seconds": 315,
  "watched_seconds": 480,
  "completed": false
}
```

**DECISION PROGRESS-1:** `resume_position_seconds` là vị trí tiếp tục phát; `watched_seconds` là **tổng thời lượng thực xem**, không đồng nhất hai khái niệm; định nghĩa tính phần trăm, chống client tự khai đã hoàn thành và khi nào course `COMPLETED` cần chốt. Nếu không theo dõi thời gian xem đáng tin cậy, định nghĩa progress theo completion/lesson thay vì hứa tính chi tiết.

### 7.3. Flashcard — tính năng bắt buộc theo screen 14–16, 41

| API mục tiêu | Trạng thái | Chức năng |
|---|---|---|
| `GET /sections/{section_id}/flashcards` | **PROPOSED/P1** | Trả bộ thẻ đã duyệt, thứ tự, `front`, `back`, source; chỉ Student enrolled/unlocked |
| `POST /flashcards/{flashcard_id}/reviews` | **PROPOSED/P1** | Lưu `remembered=true/false` cho **Student hiện tại**; không cho tự chỉ định student_id |
| `GET /courses/{course_id}/flashcards` | **PROPOSED/P2** | Tổng hợp flashcards nhiều section cho trang Flashcard từ sidebar, vẫn kiểm unlock |

**Response danh sách mục tiêu (ĐỀ XUẤT):**

```json
{
  "section_id": 12,
  "items": [
    {"id": 81, "front": "Public subnet là gì?", "back": "...", "source_timestamp_seconds": 134}
  ],
  "remembered_count": 9,
  "needs_review_count": 3
}
```

**Review:** `POST /flashcards/81/reviews` body `{ "remembered": true }`; trả `remembered_count`, `needs_review_count`, `reviewed_count`. Lượt xem/lật thẻ có thể là state UI; **chỉ “Đã nhớ/Cần ôn” cần ghi DB** nếu phải giữ giữa các phiên. Không để Student sửa nội dung flashcard đã được Instructor duyệt.

---

## 8. Checkpoint, Quiz & AI Tutor (screen 17–27)

### 8.1. Các API thực tế cần sửa logic

| API | Trạng thái | Yêu cầu v6 |
|---|---|---|
| `GET /sections/{section_id}/quiz` | **PARTIAL/P1** | Chỉ Student đã enroll, course/section published, unlocked; quiz approved; không trả đáp án đúng |
| `POST /quizzes/{quiz_id}/attempts` | **PARTIAL/P1** | Cùng kiểm quyền như GET; chấm tại server, lưu answers, attempt, score, band và retry state |
| `GET /student/quizzes/history` | ROUTE | Lịch sử của chính student, lọc course/section nếu cần |
| `GET /courses/{course_id}/unlock-status` | **PARTIAL/P1** | Thêm kiểm enrollment/course publish, trả từng section unlocked |
| `POST /tutor/sessions` | **PARTIAL** | Từ `quiz_attempt_id` thuộc chính student, chưa đạt; không mở Tutor không có attempt hợp lệ |
| `POST /tutor/sessions/{id}/messages` | **PARTIAL** | Giải thích kiến thức sai, ví dụ theo context, kiểm session owner, có quota |
| `POST /tutor/sessions/{id}/practice-attempts` | **PARTIAL** | Server chấm 3 câu practice, cập nhật điều kiện retry, kiểm session owner |
| `GET /tutor/sessions/{id}` | **PROPOSED/P1** | Cho UI resume step và hiển thị giải thích/practice sau reload; cũng có thể tích hợp vào GET session list nếu chốt |

### 8.2. Bảng quyết định checkpoint — quy tắc sản phẩm

| Điểm `score_percent` | Trạng thái | Section tiếp | Làm lại checkpoint | Remediation |
|---|---|---|---|---|
| **≥80%** | `PASSED` | **Mở** | Không bắt buộc | Không bắt buộc |
| **50% đến <80%** | `REVIEW` | Khóa | **Cho làm lại ngay** | Tutor được gợi ý, không bắt buộc |
| **<50%** | `REMEDIATION_REQUIRED` | Khóa | **Chặn tới khi practice đạt** | Bắt buộc AI Tutor/practice |

Đối với **screen 25–27**, ngưỡng hoàn thành practice trong giao diện là **≥2/3 câu đúng**. Đây là hợp đồng sản phẩm cho bản v6, cần Backend Tuấn/Huy xác nhận và hiện thực đúng (không lấy cờ thành công từ frontend). Nộp practice 1/3 thì `can_retry_checkpoint=false`, 2/3 hoặc 3/3 thì `true`.

**Điểm số phải tính từ dữ liệu server**, không nhận `score_percent`/`passed` do client gửi. Hướng đề xuất: `score = 100 * (số câu đúng / tổng câu)` không làm tròn trước khi xét ngưỡng; UI có thể làm tròn khi hiển thị. Ví dụ đúng 4/5 = 80% pass; 3/5 = 60% review; 1/5 = 20% remediation. **Nếu nhóm đang dùng công thức khác, phải chốt lại trong service/contract.**

### 8.3. Request / response mục tiêu (ĐỀ XUẤT)

`GET /sections/12/quiz` — không có `correct_option_id`:

```json
{
  "quiz_id": 31,
  "section_id": 12,
  "question_count": 5,
  "pass_score_percent": 80,
  "questions": [
    {
      "id": 1,
      "stem": "Thành phần nào quyết định đường đi của lưu lượng trong VPC?",
      "options": [
        {"id": "A", "text": "Security Group"},
        {"id": "B", "text": "Route table"},
        {"id": "C", "text": "IAM Role"},
        {"id": "D", "text": "S3 Bucket"}
      ]
    }
  ]
}
```

`POST /quizzes/31/attempts`:

```json
{
  "answers": [
    {"question_id": 1, "selected_option_id": "B"}
  ]
}
```

Response **mục tiêu, không phải schema hiện tại**:

```json
{
  "attempt_id": 120,
  "quiz_id": 31,
  "score_percent": 60,
  "score_band": "REVIEW",
  "passed": false,
  "next_section_unlocked": false,
  "can_retry_checkpoint": true,
  "remediation_required": false,
  "results": [
    {"question_id": 1, "is_correct": true, "explanation": "Route table quy định tuyến đường."}
  ]
}
```

Khi `<50%`, `score_band="REMEDIATION_REQUIRED"`, `remediation_required=true` và `can_retry_checkpoint=false` cho tới khi practice đạt.

`POST /tutor/sessions` — đề xuất body gắn với attempt thực:

```json
{ "quiz_attempt_id": 120 }
```

Session/message response **mục tiêu** cần cho screens 23–25: `session_id`, `step` (`EXPLAIN`/`REVIEW`/`PRACTICE`), `wrong_topics`, `explanations`, `related_lesson_ids`, `related_flashcard_ids`, `practice_questions`, `required_correct=2`, `total_questions=3` (khi vào practice). Giữ phân trang/hạn quota nếu schema có nhiều nội dung. Không trả `correct_option_id` của practice trước khi nộp.

`POST /tutor/sessions/{id}/practice-attempts` — **ĐỀ XUẤT**:

```json
{
  "answers": [
    {"question_id": "p1", "selected_option_id": "B"},
    {"question_id": "p2", "selected_option_id": "C"},
    {"question_id": "p3", "selected_option_id": "A"}
  ]
}
```

```json
{
  "session_id": 41,
  "correct_count": 2,
  "total_count": 3,
  "practice_passed": true,
  "can_retry_checkpoint": true,
  "results": [
    {"question_id": "p1", "is_correct": true},
    {"question_id": "p2", "is_correct": true},
    {"question_id": "p3", "is_correct": false}
  ]
}
```

**Bảo đảm kiểm soát từ Backend:** endpoint `POST /quizzes/{id}/attempts` cũng phải kiểm xem attempt trước của cùng student/section có `REMEDIATION_REQUIRED` và remediation đã đủ điều kiện trước khi cho retry; không chỉ vô hiệu hóa nút trên React. Nếu quiz service hiện chưa lưu đủ remediation state, cần thiết kế bảng/cột riêng và migration sau khi nhóm chốt.

---

## 9. Instructor Analytics & Admin Monitoring (screen 30, 45–46, 53–54)

| API | Trạng thái | Dữ liệu tối thiểu |
|---|---|---|
| `GET /instructor/courses/{id}/analytics` | ROUTE/PARTIAL | Enrolled count, completion rate, checkpoint pass rate, average score, tutor usage thuộc course owner |
| `GET /instructor/courses/{id}/students` | **PROPOSED/P1** | Student name/email masked as appropriate, progress %, last score, pass/fail; filter/search/page |
| `GET /instructor/courses/{id}/students/{student_id}/analytics` | **PROPOSED/P1** | Progress lesson/section, quiz attempts/history, tutor sessions/topics cho **course owner** |
| `GET /instructor/dashboard` | **PROPOSED/P1** | Số course, số lesson chờ duyệt, tổng học viên, pass rate và danh sách gần đây |
| `GET /admin/operations/summary` | **PROPOSED/P1/P2** | Pipeline success %, failed jobs, AI usage, cost warning count — có định nghĩa số liệu |
| `GET /admin/operations/jobs` | **PROPOSED/P2** | Job ID/lesson ID, stage, status, started_at, duration, error_code, pagination |
| `GET /admin/operations/jobs/{job_id}` | **PROPOSED/P2** | Trạng thái từng bước và log **đã ẩn secrets**, CloudWatch link theo quyền |

**Tổ chức dữ liệu analytics:** `courses` → `enrollments` → `progress`/`quiz_attempts`/`tutor_sessions`; không cần trả toàn bộ bảng `users` hoặc content của learner cho instructor không sở hữu course. Admin monitoring là chức năng vận hành, **không trao AWS credentials hoặc CloudWatch full-access cho trình duyệt**. Nếu chỉ cần click “Mở CloudWatch” thì có thể điều hướng console được cấp quyền, nhưng screen 54 có modal xem log nên cần Backend/adapter đọc các log đã giới hạn và làm sạch.

**DECISION ANALYTICS-1:** screen 45–46 cần dữ liệu chi tiết hơn `GET /instructor/courses/{id}/analytics` hiện có; cần chọn mở rộng schema endpoint này hay bổ sung hai endpoint students phía trên. Đề xuất tách list/detail để không trả dữ liệu nhạy cảm quá rộng.

---

## 10. API đề xuất bổ sung — backlog chính thức cho UI v6

**Đây là các API `MISSING/PROPOSED`, không phải danh sách route đã deploy.** Các endpoint tùy chọn được giữ ở ưu tiên thấp. Mọi route mới phải có owner/role/negative tests.

| Ưu tiên | Method + path (đề xuất) | Screen | Owner phối hợp | Tiêu chí nghiệm thu chính |
|---|---|---|---|---|
| **P0** | **Sửa** `GET /auth/me` và dependency JWT (không tạo route mới) | 01,55,56 và mọi API | Huy + Dũng | Anonymous/invalid JWT 401; Student không giả Instructor; `X-Demo-User` vô hiệu production |
| **P1** | `GET /students/me/courses` | 10,28 | Huy + Hùng | Chỉ course chính mình đã enroll; progress thật |
| **P1** | `GET /instructor/courses` | 30,31 | Huy + Hùng | Bao gồm DRAFT/PUBLISHED **của owner**, không public |
| **P1** | `GET /instructor/courses/{id}` | 33,44 | Huy + Hùng | Chi tiết draft riêng owner; không lộ ra public |
| **P1** | `GET /instructor/dashboard` | 30 | Huy + Hùng | Tổng hợp và danh sách “cần xử lý” |
| **P1** | `GET /instructor/review-queue` | 38 | Tuấn + Huy + Hùng | Chỉ queue học liệu của owner, lọc trạng thái |
| **P1** | `PUT /lessons/{id}/progress` | 12,29 | Hùng/Huy | Chỉ Student enrolled/unlocked; không giả mạo user |
| **P1** | `GET /courses/{id}/progress` | 10,11,28 | Hùng/Huy | Tiến độ đúng theo lesson/section/checkpoint, completion |
| **P1** | `GET /students/me/progress` | 29 | Hùng/Huy | Tổng quan nhiều course, không đọc được tiến độ người khác |
| **P1** | `GET /sections/{id}/flashcards` | 14–16 | Tuấn + Huy + Hùng | Chỉ học liệu đã duyệt và đủ unlock |
| **P1** | `POST /flashcards/{id}/reviews` | 15–16 | Tuấn + Huy + Hùng | Lưu remembered/needs review theo user |
| **P1** | `GET /instructor/courses/{id}/students` | 45 | Huy + Hùng | Danh sách enrollment đúng course owner |
| **P1** | `GET /instructor/courses/{id}/students/{student_id}/analytics` | 46 | Huy + Hùng | Detail đúng course + student, chống IDOR |
| **P1** | `GET /admin/users` | 47 | Huy + Dũng + Hùng | ADMIN-only, lọc role/status, phân trang |
| **P1** | `POST /admin/users` | 48–50 | Huy + Dũng + Hùng | Provision Instructor/Admin có kiểm soát, đồng bộ Cognito/DB, audit |
| **P1** | `PATCH /admin/users/{id}` | 51–52 | Huy + Dũng | Update role/active, audit, không tự nâng quyền |
| **P1** | `POST /admin/users/{id}/reset-password` | 51 | Huy + Dũng | Dùng Cognito reset/invite, không hiển thị mật khẩu cũ |
| **P1** | `PATCH /users/me` | 55 | Huy + Hùng | Profile cơ bản, không tự đổi role/email_verified |
| **P1** | `GET /tutor/sessions/{id}` | 23–27 | Tuấn + Hùng | Resume session của owner; show step/practice |
| **P2** | `GET /courses/{id}/flashcards` | 14–16 | Tuấn + Hùng | Trang Flashcard tổng hợp course |
| **P2** | `GET /instructor/courses/{id}/publish-readiness` | 44 | Huy + Tuấn | Modal biết rõ điều kiện, không thay server-side validation khi publish |
| **P2** | `GET /admin/operations/summary` | 53 | Dũng + Huy | Metric/status có định nghĩa và thời gian cập nhật |
| **P2** | `GET /admin/operations/jobs` | 53 | Dũng + Huy | Danh sách job, filter, status, pagination |
| **P2** | `GET /admin/operations/jobs/{id}` | 54 | Dũng + Huy | Log redacted, hạn quyền Admin, không lộ secrets |
| **DECISION** | `POST /lessons/{id}/confirm-upload` | 35–36 | Huy + Dũng | Chỉ triển khai nếu chọn upload-session design; chống race/double trigger |
| **DECISION** | `POST /courses/{id}/unpublish` | 31,33 | Huy + Hùng | Chốt ảnh hưởng Student/enrollment/progress |

**Không bổ sung FastAPI endpoints không cần thiết:** OTP signup, resend OTP, forgot/reset/change password nếu Cognito đảm trách; `PUT {presigned_s3_url}` do S3 nhận; `GET /admin/roles` nếu matrix có thể là cấu hình tĩnh; modal xác nhận là UI state.

### Admin account status (implemented in source)

`PATCH /admin/users/{user_id}/status` accepts `{ "enabled": true|false }` and returns the user with `status: "ACTIVE"|"INACTIVE"`. It is ADMIN-only. Cognito is updated before the RDS status; an RDS write failure triggers a compensating Cognito update. If compensation fails, the API returns `502` with `ACCOUNT_SYNC_INCONSISTENT`, which requires reconciliation. The endpoint refuses self-disable and disabling the last active ADMIN. Existing authenticated API requests also reject an INACTIVE RDS account. Migration `0015_user_account_status.sql` adds the persisted status; it has not been applied to any database by this change.

---

## 11. Quy tắc dữ liệu và những ràng buộc phải có trước nghiệm thu

### 11.1. Các quan hệ dữ liệu nghiệp vụ

| Nhóm dữ liệu | Quan hệ logic | Ghi chú triển khai |
|---|---|---|
| Identity | `users` ↔ verified Cognito `sub`, `role`, status | `cognito_sub` đã có trong model; chưa có mapping request production |
| Course | `courses.instructor_id` → `users` | Ownership phải kiểm từ verified identity |
| Structure | `courses` → `sections` → `lessons` | Có thứ tự học, không coi section khóa là dữ liệu public |
| Enrollment | `(student_id, course_id)` | Chống trùng, kiểm course published |
| Progress | `(student_id, lesson_id)` và tổng hợp course | `api/progress.py` chưa đăng ký route; cần xác nhận schema/migration |
| Video | `lessons.raw_video_key`, `processed_video_key` | Byte nằm trên S3; không lưu presigned URL |
| AI artifacts | Transcript chunks, concepts, quiz, flashcards, review draft | Flashcard và hình thức approval cần đối chiếu schema thật |
| Quiz | `quizzes`, `quiz_questions`, `quiz_attempts`, answer details | Chấm trên server; dữ liệu attempts phục vụ analytics/Tutor |
| Tutor | `tutor_sessions`, `tutor_messages`, practice attempts/state | Kiểm đúng bảng/migration; đừng suy ra tên bảng mới nếu chưa đối chiếu |
| Observability | pipeline execution/job ID ↔ lesson ↔ CloudWatch | Redact URL ký, tokens, nội dung nhạy cảm |

### 11.2. Chính sách kiểm thử nghiệm thu v6

| ID | Kịch bản cần đạt | Kết quả mong muốn |
|---|---|---|
| A01 | Anonymous gọi `GET /auth/me`, `POST /courses` | `401`, không fallback ID 1 |
| A02 | STUDENT JWT hợp lệ nhưng gửi `X-Demo-User` ID Instructor | Không thể nâng quyền; 403 API Instructor |
| A03 | Instructor A sửa course B | `403/404`, không ghi DB |
| A04 | Public catalog/detail trên course published có lesson REVIEW_REQUIRED | Không lộ draft lesson content/metadata chưa được chốt public |
| A05 | STUDENT chưa enroll hoặc course DRAFT mở quiz/submits | Từ chối và không ghi attempt |
| A06 | Student enrolled truy cập section locked qua `GET /lessons`/video URL | 403/404; không cấp URL |
| A07 | Quiz 80%, 60%, 20% | Pass+unlock / Review+retry ngay / Tutor+practice trước retry |
| A08 | Dưới 50%, practice 1/3 | Không được retry checkpoint |
| A09 | Dưới 50%, practice 2/3 | Được retry checkpoint **cho chính attempt/section/user** |
| A10 | Student gửi score giả hoặc correct_answer giả | Server tính score/logic, không tin client |
| A11 | Tutor session lấy attempt của Student khác | Từ chối, không lộ context |
| A12 | Flashcard chưa duyệt hoặc section locked | Student không đọc được |
| A13 | Admin tạo Instructor và Student tự post role=INSTRUCTOR | Admin thành công theo contract đã chốt; public role injection bị chặn |
| A14 | Instructor publish chưa duyệt/thiếu processed video | 409, không public |
| A15 | Một upload event lặp/hết hạn/HeadObject size sai | Không tạo job kép hoặc ghi DB sai |
| A16 | Instructor tải video xong, đóng browser | Workflow xử lý bất đồng bộ; theo dõi được trạng thái |
| A17 | Instructor xem analytics course khác; Admin/student xem học viên của Instructor | Backend từ chối theo ownership/policy |
| A18 | React logout rồi dùng JWT cũ theo chính sách session | Token/session bị từ chối khi hết hạn hoặc revoke theo policy |
| A19 | FastAPI và Cognito triển khai đúng Region/audience/issuer | JWT chính xác được chấp nhận; JWT pool khác 401 |
| A20 | Các màn hình có API MISSING | Không render như dữ liệu thật nếu backend chưa có; UI dùng mock có ghi rõ hoặc trạng thái chưa hỗ trợ |

**Kiểm thử hiện tại không đủ điều kiện nghiệm thu:** Báo cáo offline gần nhất ghi `161 passed, 28 failed` và 78 assertion bổ sung (một số assertion **xác nhận lỗ hổng**). Không biến số lượng assertion đó thành tỉ lệ chất lượng bảo mật. Cần sửa auth P0, enrollment/unlock P1, các test setup/compatibility/migration và chạy regression trước demo public.

---

## 12. Quyết định mở — bắt buộc chốt trước khi đóng băng v6

| ID | Cần quyết định | Hướng đề nghị / bên chốt |
|---|---|---|
| D01 | Identity production và nguồn role | Cognito + FastAPI verified `sub` + role PostgreSQL; Huy/Dũng/Hùng |
| D02 | Provision Instructor/Admin | Admin tạo/invite, public signup STUDENT-only như screen 48/52; Huy/Dũng |
| D03 | Migration 0004 `APPROVED` conflict; approve có tự public lesson? | Tách approval khỏi visibility; kiểm tra DB/migration và cố định state mapping; Huy/Tuấn/Dũng |
| D04 | Flashcard lưu thế nào và AI/review hỗ trợ đầy đủ chưa? | Đánh dấu P1 vì screen 14–16, 41; Tuấn/Huy |
| D05 | Dưới 50% cần practice 2/3 trước retry | Theo screen 25–27, implement server guard; Tuấn/Huy |
| D06 | Công thức progress/completion, resume vs watch time | Chốt field và điều kiện hoàn thành; Hùng/Huy |
| D07 | Upload confirm session vs S3 event trực tiếp | Chọn một nguồn dispatch, chống race/duplicate; Huy/Dũng |
| D08 | S3 Presigned GET hay CloudFront Signed URL cho video | MVP giữ S3 GET tương thích, CloudFront khi ready; Hùng/Dũng/Huy |
| D09 | Course unpublish/replacement lesson video | Chốt chính sách state/ảnh hưởng học viên trước mở API; Huy/Tuấn |
| D10 | Analytics student-level được xem đến đâu | Chỉ Instructor owner/course member; ẩn dữ liệu thừa; Huy/Hùng |
| D11 | Bảng role permission có động không | Tĩnh ở MVP, vẫn validate server-side; Hùng/Huy |
| D12 | Cover image upload & schema | Ảnh bìa tùy chọn; cần chốt storage và URL chính thức; Hùng/Huy |
| D13 | Admin system monitoring dữ liệu từ đâu | CloudWatch adapter/DB tracking, hạn quyền và quota; Dũng/Huy |
| D14 | JSON shape hiện có theo Swagger và versioning | Bổ sung field không phá response; audit OpenAPI trước chốt; Huy/Hùng/Tuấn |

---

## 13. Thứ tự triển khai khuyến nghị, tránh làm lại

1. **P0 — Huy/Dũng:** chốt Cognito production/auth contract; sửa `get_current_user()` và test không thể giả mạo bằng `X-Demo-User`. Chưa public Backend khi chưa đạt.
2. **P1 — Huy/Tuấn:** sửa course access ở quiz, lesson/video unlock, public outline; cùng sửa và chạy lại unit tests.
3. **P1 — Huy/Hùng:** thêm instructor course list/detail, student my-courses, progress, dashboard dữ liệu; Frontend tích hợp từng màn.
4. **P1 — Tuấn/Huy/Hùng:** hoàn thiện review Flashcard, Student Flashcards, checkpoint dưới 50% + Tutor practice 2/3, route resume Tutor.
5. **P1 — Dũng/Huy/Hùng:** Cognito email verification/forgot password và Admin provision user; profile.
6. **P1/P2 — Huy/Tuấn/Dũng:** thống nhất approve/publish migration; thử video+AI pipeline thật rồi nối review/publish; analytics và monitoring sau.
7. **Review hợp đồng:** xuất FastAPI OpenAPI mới, so Pydantic schemas, mock UI theo trạng thái thiếu API, bổ sung tests và cập nhật trạng thái `ROUTE/PARTIAL/MISSING` theo bằng chứng.

### Đầu ra công việc cho từng thành viên

- **Hùng — Frontend:** dùng bảng screen 01–56 để map React actions → contract; không tự đoán endpoint; đánh dấu API thiếu và dùng mock có nhãn tạm.
- **Huy — Backend:** sửa auth P0, thêm các API nghiệp vụ thiếu, giữ/đánh version request/response, ngăn IDOR và bypass checkpoint.
- **Tuấn — AI/Quiz/Tutor:** chốt JSON schema học liệu (gồm flashcards), quizzing/remediation/practice, tích hợp Bedrock nhưng không giả định success với mocks.
- **Dũng — AWS/Admin:** Cognito pool, provision flow/roles, API Gateway authorizer (nếu dùng), S3/CloudFront, job monitoring và quyền truy cập phù hợp.

---

## 14. Nguồn, lịch sử thay đổi và kiểm chứng

- **[UI]** `screens.zip`, 56 file `01.png` đến `56.png`: cơ sở yêu cầu chức năng của giao diện, không phải bằng chứng API đã code.
- **[V5]** `api-contract(1).md`, Draft v5 (30/10/2026): giữ các contract video Upload/Processing/Review/Publish và ràng buộc presigned S3; sửa các thông tin triển khai đã cũ.
- **[BIZ]** `LEARNCLOUD_YEU_CAU_VA_LOGIC_NGHIEP_VU.md`, 09/11/2026: quy tắc role, enrollment, unlock, AI review/Tutor và những điểm mở.
- **[PDF1]** `LearnCloud_Hoan_Thien.docx.pdf`: MVP, Cloud/AI pipeline, Instructor/Student journey.
- **[PDF2]** `LearnCloud_Kien_truc_va_lo_trinh_4_tuan_v3.docx(1).pdf`: FastAPI local-first, API tham chiếu, mock/dev header theo giai đoạn.
- **[PDF3]** `PROGRESS_NHOM2_FINAL(1).pdf`: 3 vai trò, Flashcard, checkpoint remediation và kiến trúc M1–M8.
- **[AUDIT]** `INSTRUCTOR_AUTH_AUDIT.md`, 08/11/2026, commit `ae20df5`: 35 cặp method/path duy nhất, 7 review route trùng, lỗ hổng `X-Demo-User`, thiếu progress/admin/instructor lists và lỗi ở quiz/lesson unlock.

**Thay đổi nổi bật v5 → v6:** mở rộng từ video-centric sang **toàn bộ 56 screens**; thêm ma trận screen/API; xác thực email/forgot qua Cognito EXTERNAL; Admin tạo Instructor; ghi đúng `/student/quizzes/history`; bổ sung Tutor practice-attempts đã có; sửa tiến độ triển khai progress (thực tế chưa có); bổ sung flashcard/dashboard/analytics/admin/monitoring **dưới dạng đề xuất**; tách approval và visibility để loại mô tả mâu thuẫn; đưa auth P0 và access guards lên đầu backlog. Không thay đổi bất cứ tài nguyên chạy thật nào.
