# API Contract

> **Mục đích:** Đây là hợp đồng giao tiếp giữa Frontend và Backend
> LearnCloud.
>
> **Nguồn chuẩn về phạm vi:** Bảng `API endpoints MVP` do nhóm thống
> nhất. Method, path, chức năng, vai trò, file và phân công trong bảng
> đó được giữ nguyên trong tài liệu này.
>
> **Lưu ý trạng thái:** Có mặt trong tài liệu không đồng nghĩa endpoint
> đã được triển khai. Chỉ đánh dấu **Implemented** sau khi code và kiểm
> thử xác nhận.
>
> **Local base URL:** `http://127.0.0.1:8000`\
> **OpenAPI/Swagger:** `http://127.0.0.1:8000/docs`

------------------------------------------------------------------------

## 1. Quy ước chung

-   API theo kiểu REST, trao đổi JSON trừ phần upload file.
-   Dùng HTTPS khi triển khai trên môi trường công khai.
-   `{id}` là ID của tài nguyên tương ứng. Khi viết route FastAPI, nhóm
    có thể dùng tên biến cụ thể như `{course_id}` hoặc `{lesson_id}`,
    nhưng URL công khai phải thống nhất.
-   Request/response dưới đây chỉ là hợp đồng chi tiết khi đã được nhóm
    xác nhận. Các ví dụ có nhãn **Đề xuất --- cần xác nhận** không phải
    bằng chứng rằng backend hiện tại đã hỗ trợ cấu trúc đó.
-   Backend phải kiểm tra danh tính, vai trò, quyền sở hữu tài nguyên và
    điều kiện unlock ở phía server. Không tin vào vai trò hoặc trạng
    thái unlock do frontend tự gửi lên.

### 1.1. Mã lỗi tối thiểu

  ### Mã lỗi HTTP tối thiểu

| HTTP status | Ý nghĩa theo quy ước MVP |
|---|---|
| `400 Bad Request` | Input sai |
| `401 Unauthorized` | Chưa xác thực |
| `403 Forbidden` | Thiếu quyền hoặc nội dung chưa được unlock |
| `404 Not Found` | Tài nguyên không tồn tại |
| `409 Conflict` | Trạng thái không hợp lệ |
| `500 Internal Server Error` | Lỗi server |

Endpoint có thể trả thêm các mã HTTP phù hợp khác nếu nhóm thống nhất,
nhưng frontend tối thiểu cần xử lý các mã trên.

**Cấu trúc lỗi đề xuất (cần xác nhận với backend):**

``` json
{
  "detail": "Human-readable error message"
}
```

FastAPI có thể trả lỗi validation theo cấu trúc mặc định khác. Nếu muốn
response lỗi đồng nhất, backend cần chuẩn hóa và cập nhật tài liệu
OpenAPI.

------------------------------------------------------------------------

## 2. Danh sách endpoint MVP

  ----------------------------------------------------------------------------------------------------------------------------------------
  ## API endpoints MVP

Cột **Người · Tuần** cho biết ai phụ trách endpoint và thực hiện trong tuần nào.

| Method + path | Chức năng | Vai trò | File | Người · Tuần |
|---|---|---|---|---|
| `GET /health` | Kiểm tra backend. | All | `api/health.py` | A · T1 |
| `GET /courses` | Danh sách course đã publish. | Student | `api/courses.py` | D · T1 |
| `POST /courses` | Tạo course. | Instructor | `api/courses.py` | D · T2 |
| `GET /courses/{id}` | Chi tiết/outline course. | Student/Instructor | `api/courses.py` | D · T1 |
| `PATCH /courses/{id}` | Sửa metadata. | Instructor | `api/courses.py` | D · T2 |
| `POST /courses/{id}/publish` | Publish course. | Instructor | `api/courses.py` | D · T3 |
| `POST /courses/{id}/sections` | Tạo section. | Instructor | `api/sections.py` | D · T2 |
| `POST /sections/{id}/lessons` | Tạo lesson. | Instructor | `api/lessons.py` | D · T2 |
| `GET /lessons/{id}` | Lấy lesson có kiểm tra quyền/unlock. | Student/Instructor | `api/lessons.py` | D · T2 |
| `POST /lessons/{id}/upload-url` | Cấp presigned URL. | Instructor | `api/uploads.py` | D · T2 |
| `GET /lessons/{id}/processing-status` | Xem pipeline status. | Instructor | `api/lessons.py` | D · T3 |
| `POST /lessons/{id}/retry` | Retry job lỗi. | Instructor/Admin | `api/lessons.py` | D · T3 |
| `GET /lessons/{id}/ai-content` | Lấy transcript/summary/concepts/quiz nháp. | Instructor | `api/review.py` | C · T3 |
| `PATCH /lessons/{id}/ai-content` | Sửa nội dung AI. | Instructor | `api/review.py` | C · T3 |
| `POST /lessons/{id}/approve` | Approve trước publish. | Instructor | `api/review.py` | C · T3 |
| `POST /courses/{id}/enroll` | Đăng ký course. | Student | `api/enrollments.py` | D · T2 |
| `PUT /lessons/{id}/progress` | Lưu tiến độ học. | Student | `api/progress.py` | B · T2 |
| `GET /courses/{id}/progress` | Xem tiến độ. | Student | `api/progress.py` | B · T2 |
| `GET /sections/{id}/quiz` | Lấy checkpoint đã duyệt và được mở. | Student | `api/quizzes.py` | C · T2 |
| `POST /quizzes/{id}/attempts` | Nộp bài, backend chấm và lưu. | Student | `api/quizzes.py` | C · T2 |
| `GET /students/me/quiz-history` | Lịch sử điểm. | Student | `api/quizzes.py` | C · T2 |
| `POST /tutor/sessions` | Tạo remediation từ attempt chưa đạt. | Student | `api/tutor.py` | C · T4 |
| `POST /tutor/sessions/{id}/messages` | Gửi câu hỏi tiếp theo. | Student | `api/tutor.py` | C · T4 |
| `GET /instructor/courses/{id}/analytics` | Progress/pass-fail cơ bản. | Instructor | `api/analytics.py` | C · T4 |
  ----------------------------------------------------------------------------------------------------------------------------------------

------------------------------------------------------------------------

## 3. Contract theo nhóm chức năng

Phần này giữ phạm vi và ý nghĩa endpoint theo bảng MVP. Các
request/response cụ thể chưa được cung cấp đầy đủ trong bảng nguồn nên
cần được chốt giữa người phụ trách endpoint và frontend. Những ví dụ có
nhãn **Đề xuất** chỉ nhằm giúp nhóm thống nhất schema.

### 3.1. Health

#### `GET /health`

-   **Vai trò:** All.
-   **Chức năng:** Kiểm tra backend.
-   **Request body:** Không cần.
-   **Response:** Nhóm xác nhận schema health check thực tế trong
    `api/health.py`.
-   **Mã lỗi:** `500` nếu backend gặp lỗi không xử lý được.

### 3.2. Courses

#### `GET /courses`

-   **Vai trò:** Student.
-   **Chức năng:** Danh sách course đã publish.
-   **Request:** Không cần body.
-   **Response:** Danh sách course đã publish. Cần thống nhất các trường
    được trả về, ví dụ `id`, `title`, `description`, `thumbnail_url` nếu
    các trường này tồn tại trong model.
-   **Quy tắc:** Không trả course chưa publish cho Student.

#### `POST /courses`

-   **Vai trò:** Instructor.
-   **Chức năng:** Tạo course.
-   **Request/response:** Cần chốt schema course metadata với người phụ
    trách D.
-   **Mã lỗi quan trọng:** `400`, `401`, `403`, `409`, `500`.

#### `GET /courses/{id}`

-   **Vai trò:** Student/Instructor.
-   **Chức năng:** Chi tiết/outline course.
-   **Response:** Thông tin course và outline mà caller có quyền xem.
-   **Quy tắc:** Student chỉ được xem nội dung phù hợp với trạng thái
    publish; Instructor cần bị giới hạn theo quy tắc sở hữu/quản lý
    course mà nhóm thống nhất.

#### `PATCH /courses/{id}`

-   **Vai trò:** Instructor.
-   **Chức năng:** Sửa metadata course.
-   **Request:** Chỉ chứa trường metadata được phép sửa.
-   **Quy tắc:** Backend xác minh quyền của Instructor đối với course.

#### `POST /courses/{id}/publish`

-   **Vai trò:** Instructor.
-   **Chức năng:** Publish course.
-   **Request body:** Có thể không cần body nếu hành động chỉ đổi trạng
    thái; xác nhận với người phụ trách D.
-   **Quy tắc:** Backend kiểm tra điều kiện publish trước khi đổi trạng
    thái. Điều kiện cụ thể cần được nhóm định nghĩa.
-   **Mã lỗi:** Dùng `409` nếu trạng thái hiện tại không cho phép
    publish.

### 3.3. Sections và lessons

#### `POST /courses/{id}/sections`

-   **Vai trò:** Instructor.
-   **Chức năng:** Tạo section trong course.
-   **Request:** Cần chốt trường tối thiểu, chẳng hạn tiêu đề và thứ tự
    hiển thị.
-   **Quy tắc:** Xác minh quyền chỉnh sửa course.

#### `POST /sections/{id}/lessons`

-   **Vai trò:** Instructor.
-   **Chức năng:** Tạo lesson trong section.
-   **Request:** Cần chốt schema lesson và metadata video.
-   **Quy tắc:** Xác minh quyền chỉnh sửa section/course.

#### `GET /lessons/{id}`

-   **Vai trò:** Student/Instructor.
-   **Chức năng:** Lấy lesson có kiểm tra quyền/unlock.
-   **Quy tắc:** Backend tự xác định người dùng, enrollment và điều kiện
    unlock; không dựa vào một cờ `is_unlocked` do client gửi lên.
-   **Mã lỗi:** `401` chưa đăng nhập, `403` chưa unlock/thiếu quyền,
    `404` không tồn tại.

### 3.4. Upload và xử lý video

#### `POST /lessons/{id}/upload-url`

-   **Vai trò:** Instructor.
-   **Chức năng:** Cấp presigned URL.
-   **Request đề xuất (cần xác nhận):**

``` json
{
  "file_name": "lesson-video.mp4",
  "content_type": "video/mp4"
}
```

-   **Response đề xuất (cần xác nhận):**

``` json
{
  "upload_url": "<presigned-url>",
  "object_key": "<storage-object-key>",
  "expires_in": 900
}
```

-   **Bảo mật:** Presigned URL có thời hạn; không gửi AWS access
    key/secret key cho frontend. `expires_in` ở ví dụ chỉ là giá trị
    minh họa, cần cấu hình thực tế.

#### `GET /lessons/{id}/processing-status`

-   **Vai trò:** Instructor.
-   **Chức năng:** Xem pipeline status.
-   **Response:** Cần chốt enum trạng thái chính thức, ví dụ `PENDING`,
    `PROCESSING`, `COMPLETED`, `FAILED` nếu phù hợp với pipeline thực
    tế.
-   **Mã lỗi:** `401`, `403`, `404`, `500`.

#### `POST /lessons/{id}/retry`

-   **Vai trò:** Instructor/Admin.
-   **Chức năng:** Retry job lỗi.
-   **Quy tắc:** Chỉ cho retry khi job ở trạng thái cho phép; hành vi
    khi job đang chạy cần được định nghĩa.
-   **Mã lỗi:** `401`, `403`, `404`, `409`, `500`.

### 3.5. AI content review

#### `GET /lessons/{id}/ai-content`

-   **Vai trò:** Instructor.
-   **Chức năng:** Lấy transcript, summary, concepts và quiz nháp.
-   **Response:** Cần thống nhất schema của từng loại nội dung AI với
    người phụ trách C.

#### `PATCH /lessons/{id}/ai-content`

-   **Vai trò:** Instructor.
-   **Chức năng:** Sửa nội dung AI.
-   **Request:** Chỉ chứa trường được phép sửa theo schema đã thống
    nhất.
-   **Quy tắc:** Xác minh quyền Instructor và trạng thái review hiện
    tại.

#### `POST /lessons/{id}/approve`

-   **Vai trò:** Instructor.
-   **Chức năng:** Approve trước publish.
-   **Request body:** Cần chốt; có thể không cần body nếu chỉ xác nhận
    duyệt.
-   **Quy tắc:** Backend chỉ chấp nhận approve khi nội dung đáp ứng điều
    kiện review. Cần thống nhất approve có đồng thời publish nội dung
    hay chỉ chuyển sang trạng thái đã duyệt.

### 3.6. Enrollment

#### `POST /courses/{id}/enroll`

-   **Vai trò:** Student.
-   **Chức năng:** Đăng ký course.
-   **Request:** Không cần truyền danh tính Student trong body nếu
    backend lấy danh tính từ session/token.
-   **Response:** Cần chốt thông tin enrollment và hành vi khi đăng ký
    trùng.
-   **Mã lỗi:** `401`, `403`, `404`, `409`, `500`.

### 3.7. Learning progress

#### `PUT /lessons/{id}/progress`

-   **Vai trò:** Student.
-   **Chức năng:** Lưu tiến độ học.
-   **Request đề xuất --- cần xác nhận:**

``` json
{
  "progress_percent": 50,
  "last_position_seconds": 120
}
```

-   **Response:** Cần chốt schema xác nhận tiến độ đã lưu.
-   **Lưu ý:** Các trường trên là ví dụ thiết kế, chưa phải schema đã
    được nhóm xác nhận.

#### `GET /courses/{id}/progress`

-   **Vai trò:** Student.
-   **Chức năng:** Xem tiến độ của Student đối với course.
-   **Quy tắc:** Backend xác định Student từ thông tin xác thực và chỉ
    trả tiến độ của chính người đó, trừ khi nhóm có quy tắc quyền khác
    được phê duyệt.

### 3.8. Quiz và checkpoint

#### `GET /sections/{id}/quiz`

-   **Vai trò:** Student.
-   **Chức năng:** Lấy checkpoint đã duyệt và được mở.
-   **Quy tắc:** Chỉ trả quiz đã duyệt và section đã được mở cho
    Student. Không trả đáp án đúng trước khi nộp bài.
-   **Response:** Cần chốt schema quiz, question và option.

#### `POST /quizzes/{id}/attempts`

-   **Vai trò:** Student.
-   **Chức năng:** Nộp bài, backend chấm và lưu.
-   **Request đề xuất --- cần xác nhận:**

``` json
{
  "answers": [
    {
      "question_id": 1,
      "selected_option_id": 2
    }
  ]
}
```

-   **Response:** Cần chốt các trường điểm, kết quả đạt/trượt, số lần
    làm và trạng thái unlock tiếp theo.
-   **Quy tắc:** Backend tự chấm điểm; không tin điểm do client gửi lên.

#### `GET /students/me/quiz-history`

-   **Vai trò:** Student.
-   **Chức năng:** Lịch sử điểm của người dùng hiện tại.
-   **Quy tắc:** Lấy danh tính từ thông tin xác thực; không cho client
    chỉ định một Student khác bằng query/path parameter.

### 3.9. Tutor / remediation

#### `POST /tutor/sessions`

-   **Vai trò:** Student.
-   **Chức năng:** Tạo remediation từ attempt chưa đạt.
-   **Request:** Cần chốt cách tham chiếu attempt chưa đạt và ngữ cảnh
    remediation.
-   **Quy tắc:** Backend kiểm tra attempt thuộc Student hiện tại và thực
    sự chưa đạt.

#### `POST /tutor/sessions/{id}/messages`

-   **Vai trò:** Student.
-   **Chức năng:** Gửi câu hỏi tiếp theo.
-   **Request đề xuất --- cần xác nhận:**

``` json
{
  "message": "Can you explain this concept again?"
}
```

-   **Quy tắc:** Backend kiểm tra session thuộc Student hiện tại.
-   **Response:** Cần chốt schema tin nhắn và phản hồi của tutor.

### 3.10. Instructor analytics

#### `GET /instructor/courses/{id}/analytics`

-   **Vai trò:** Instructor.
-   **Chức năng:** Progress/pass-fail cơ bản.
-   **Response:** Cần chốt metric và cấu trúc tổng hợp, ví dụ số
    enrollment, tiến độ học và tỷ lệ pass/fail nếu các chỉ số này được
    nhóm chọn.
-   **Quy tắc:** Chỉ Instructor có quyền đối với course mới được xem
    analytics.

------------------------------------------------------------------------

## 4. Authentication và authorization

Bảng MVP không liệt kê endpoint đăng nhập/đăng ký, vì vậy tài liệu này
không tự thêm endpoint auth vào danh sách MVP. Tuy nhiên, các endpoint
yêu cầu vai trò phải có cơ chế xác thực được nhóm triển khai.

Nhóm cần thống nhất:

-   Cơ chế xác thực (session hoặc token).
-   Cách gửi thông tin xác thực trong request.
-   Cách backend ánh xạ danh tính thành vai trò `Student`, `Instructor`,
    `Admin`.
-   Quy tắc sở hữu course/lesson và quyền xem dữ liệu.
-   Quy tắc enrollment và unlock section.
-   Response khi chưa xác thực (`401`) hoặc thiếu quyền/chưa unlock
    (`403`).

Nếu dùng Bearer token, quy ước thường gặp là
`Authorization: Bearer <access-token>`, nhưng chỉ ghi thành yêu cầu
chính thức sau khi backend chọn cơ chế này.

------------------------------------------------------------------------

## 5. Quy trình cập nhật contract

1.  Người phụ trách endpoint thống nhất request schema, response schema
    và các mã lỗi với frontend.
2.  Cập nhật tài liệu này trước khi frontend phụ thuộc vào thay đổi.
3.  Triển khai route, validation, authorization và nghiệp vụ trong
    backend.
4.  Kiểm tra endpoint qua test và `/docs`.
5.  Chỉ sau khi test xác nhận mới đánh dấu endpoint là **Implemented**.
6.  Khi đổi method/path hoặc xóa field đã được frontend dùng, cần thông
    báo và cập nhật contract.

## 6. Checklist hoàn thiện

-   [ ] Xác nhận response đầy đủ của `GET /health`.
-   [ ] Chốt schema request/response cho Courses, Sections và Lessons.
-   [ ] Chốt authentication và authorization.
-   [ ] Chốt request/response cho presigned upload URL.
-   [ ] Chốt enum trạng thái pipeline và điều kiện retry.
-   [ ] Chốt schema AI content và quy tắc approve/publish.
-   [ ] Chốt schema enrollment và hành vi đăng ký trùng.
-   [ ] Chốt schema progress.
-   [ ] Chốt schema quiz, attempt, chấm điểm và unlock.
-   [ ] Chốt schema tutor session/message.
-   [ ] Chốt metric analytics.
-   [ ] Kiểm thử các mã lỗi tối thiểu `400`, `401`, `403`, `404`, `409`,
    `500`.
-   [ ] Đối chiếu route thực tế trong FastAPI với danh sách 24 endpoint
    ở mục 2.
