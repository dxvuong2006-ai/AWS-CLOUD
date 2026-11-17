# Hợp đồng API


## Quyền và mã lỗi

- `require_student`, `require_instructor` và `require_admin` buộc đúng vai trò; service/repository kiểm tra thêm ownership, enrollment, publish, unlock và trạng thái tài khoản.
- Nhóm `/instructor/**`, upload, review và quản lý course yêu cầu Instructor và quyền sở hữu tài nguyên. Nhóm học/quiz/progress/Tutor yêu cầu Student và các gate nghiệp vụ. Nhóm `/admin/**` yêu cầu Admin.
- `401` là thiếu/sai/hết hạn danh tính; `403` là đã xác thực nhưng không đủ quyền; `404` giữ kín tài nguyên không tồn tại/không truy cập được; `409` là xung đột trạng thái/idempotency; `422` là sai schema/validation. Các mã `5xx` phụ thuộc adapter dịch vụ ngoài.
- Cột phản hồi dưới đây chỉ liệt kê success schema. Danh sách status khai báo chi tiết xem trong OpenAPI runtime; business service có thể trả thêm lỗi thông qua exception handler chung.

## Tình trạng dịch vụ

| Method | Endpoint | Chức năng | Đầu vào | Phản hồi thành công | Xác thực |
|---|---|---|---|---|---|
| GET | `/health` | Kiểm tra trạng thái dịch vụ | Không có | 200 JSON object (schema chưa khai báo cụ thể) | Công khai |

## Xác thực và hồ sơ

| Method | Endpoint | Chức năng | Đầu vào | Phản hồi thành công | Xác thực |
|---|---|---|---|---|---|
| POST | `/auth/change-password` | Đổi mật khẩu | JSON: ChangePasswordRequest (current_password*: string, new_password*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| POST | `/auth/forgot-password` | Khôi phục mật khẩu | JSON: ForgotPasswordRequest (email*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Công khai |
| POST | `/auth/local/change-password` | Đổi mật khẩu local | JSON: ChangePasswordRequest (current_password*: string, new_password*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| POST | `/auth/local/forgot-password` | Khôi phục mật khẩu local | JSON: ForgotPasswordRequest (email*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Công khai |
| POST | `/auth/local/login` | Đăng nhập local | JSON: LoginRequest (email*: string, password*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Công khai |
| POST | `/auth/local/logout` | Đăng xuất local | Không có | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| POST | `/auth/local/register` | Đăng ký tài khoản | JSON: RegisterRequest (name*: string, email*: string, password*: string) | 201 JSON object (schema chưa khai báo cụ thể) | Công khai |
| POST | `/auth/local/resend-verification` | Gửi lại mã xác minh | JSON: ResendVerificationRequest (email*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Công khai |
| POST | `/auth/local/reset-password` | Đặt lại mật khẩu | JSON: ResetPasswordRequest (email*: string, code*: string, password*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Công khai |
| POST | `/auth/local/verify-email` | Xác minh email | JSON: VerifyEmailRequest (email*: string, code*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Công khai |
| GET | `/auth/me` | Lấy hồ sơ của tôi | Không có | 200 UserResponse | Bearer bắt buộc |
| PATCH | `/auth/me` | Cập nhật hồ sơ | JSON: UpdateProfileRequest (name*: string) | 200 UserResponse | Bearer bắt buộc |
| POST | `/auth/register` | Đăng ký tài khoản | JSON: RegisterRequest (name*: string, email*: string, password*: string) | 201 JSON object (schema chưa khai báo cụ thể) | Công khai |
| POST | `/auth/resend-verification` | Gửi lại mã xác minh | JSON: ResendVerificationRequest (email*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Công khai |
| POST | `/auth/reset-password` | Đặt lại mật khẩu | JSON: ResetPasswordRequest (email*: string, code*: string, password*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Công khai |
| POST | `/auth/verify-email` | Xác minh email | JSON: VerifyEmailRequest (email*: string, code*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Công khai |

## Khóa học, chương, đăng ký

| Method | Endpoint | Chức năng | Đầu vào | Phản hồi thành công | Xác thực |
|---|---|---|---|---|---|
| GET | `/courses` | Liệt kê khóa học | Không có | 200 array[CourseResponse] | Công khai |
| POST | `/courses` | Tạo khóa học | JSON: CourseCreateRequest (cover_image: string \| null, title*: string, description: string \| null, learning_objectives: array[string]) | 201 CourseResponse | Bearer bắt buộc |
| GET | `/courses/instructor/me` | Liệt kê khóa học của Instructor | Không có | 200 array[CourseResponse] | Bearer bắt buộc |
| GET | `/courses/{course_id}` | Lấy thông tin khóa học | course_id* (path, integer) | 200 CourseResponse | Công khai |
| PATCH | `/courses/{course_id}` | Cập nhật khóa học | course_id* (path, integer), JSON: CourseUpdateRequest (cover_image: string \| null, title: string \| null, description: string \| null, learning_objectives: array[string]) | 200 CourseResponse | Bearer bắt buộc |
| GET | `/courses/{course_id}/completion` | Lấy trạng thái hoàn thành | course_id* (path, integer) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| POST | `/courses/{course_id}/enroll` | Đăng ký khóa học | course_id* (path, integer) | 201 EnrollmentResponse | Bearer bắt buộc |
| POST | `/courses/{course_id}/publish` | Xuất bản khóa học | course_id* (path, integer) | 200 CourseResponse | Bearer bắt buộc |
| GET | `/courses/{course_id}/sections` | Liệt kê chương của khóa học | course_id* (path, integer) | 200 array[SectionResponse] | Bearer bắt buộc |
| POST | `/courses/{course_id}/sections` | Tạo chương | course_id* (path, integer), JSON: SectionCreateRequest (title*: string, position: integer) | 201 SectionResponse | Bearer bắt buộc |
| GET | `/courses/{course_id}/unlock-status` | Lấy trạng thái mở khóa khóa học | course_id* (path, integer) | 200 array[object] | Bearer bắt buộc |

## Bài học, tải lên và video

| Method | Endpoint | Chức năng | Đầu vào | Phản hồi thành công | Xác thực |
|---|---|---|---|---|---|
| GET | `/lessons/{lesson_id}` | Lấy bài học | lesson_id* (path, integer) | 200 LessonResponse | Bearer bắt buộc |
| PATCH | `/lessons/{lesson_id}` | Cập nhật bài học | lesson_id* (path, integer), JSON: LessonUpdateRequest (title: string \| null, position: integer \| null) | 200 LessonResponse | Bearer bắt buộc |
| GET | `/lessons/{lesson_id}/ai-content` | Lấy nội dung AI | lesson_id* (path, integer) | 200 object | Bearer bắt buộc |
| PATCH | `/lessons/{lesson_id}/ai-content` | Cập nhật một phần nội dung AI | lesson_id* (path, integer), JSON: object | 200 ReviewResponse | Bearer bắt buộc |
| POST | `/lessons/{lesson_id}/approve` | Duyệt nội dung AI | lesson_id* (path, integer), JSON: DraftApproval (expected_revision*: string) | 200 ReviewResponse | Bearer bắt buộc |
| POST | `/lessons/{lesson_id}/confirm-upload` | Xác nhận tải lên | lesson_id* (path, integer), JSON: ConfirmUploadRequest (upload_id*: string) | 200 LessonProcessingStatusResponse | Bearer bắt buộc |
| GET | `/lessons/{lesson_id}/content` | Lấy nội dung bài học | lesson_id* (path, integer) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/lessons/{lesson_id}/flashcards` | Lấy flashcard của bài học | lesson_id* (path, integer) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| POST | `/lessons/{lesson_id}/flashcards` | Tạo flashcard | lesson_id* (path, integer), JSON: FlashcardCreateRequest (front*: string, back*: string, position*: integer) | 201 FlashcardResponse | Bearer bắt buộc |
| DELETE | `/lessons/{lesson_id}/flashcards/{card_id}` | Xóa flashcard | lesson_id* (path, integer), card_id* (path, integer) | 204 No Content | Bearer bắt buộc |
| PUT | `/lessons/{lesson_id}/flashcards/{card_id}` | Cập nhật flashcard | lesson_id* (path, integer), card_id* (path, integer), JSON: FlashcardUpdateRequest (front: string \| null, back: string \| null, position: integer \| null, is_approved: boolean \| null) | 200 FlashcardResponse | Bearer bắt buộc |
| GET | `/lessons/{lesson_id}/processing-status` | Lấy trạng thái xử lý | lesson_id* (path, integer) | 200 LessonProcessingStatusResponse | Bearer bắt buộc |
| PUT | `/lessons/{lesson_id}/progress` | Lưu tiến độ bài học | lesson_id* (path, integer), JSON: ProgressUpdateRequest (last_position_seconds*: number, watched_ranges*: array[array[object]], playback_session_id*: string, sequence*: integer, request_id*: string) | 200 object | Bearer bắt buộc |
| POST | `/lessons/{lesson_id}/retry` | Thử xử lý lại bài học | lesson_id* (path, integer) | 202 LessonProcessingStatusResponse | Bearer bắt buộc |
| GET | `/lessons/{lesson_id}/review-draft` | Lấy bản nháp | lesson_id* (path, integer) | 200 ReviewResponse | Bearer bắt buộc |
| PUT | `/lessons/{lesson_id}/review-draft` | Cập nhật bản nháp | lesson_id* (path, integer), JSON: DraftUpdate (title*: string, summary*: string, key_concepts*: array[KeyConcept], flashcards*: array[FlashcardDraft], quiz_title*: string, questions*: array[ReviewQuestion], expected_revision*: string) | 200 ReviewResponse | Bearer bắt buộc |
| POST | `/lessons/{lesson_id}/review-draft/approvals` | Duyệt bản nháp | lesson_id* (path, integer), JSON: DraftApproval (expected_revision*: string) | 200 ReviewResponse | Bearer bắt buộc |
| POST | `/lessons/{lesson_id}/review-drafts` | Tạo bản nháp | lesson_id* (path, integer), JSON: DraftGeneration (transcript*: string, num_questions: integer, allow_fallback: boolean) | 201 ReviewResponse | Bearer bắt buộc |
| POST | `/lessons/{lesson_id}/upload-url` | Tạo URL tải lên | lesson_id* (path, integer), JSON: UploadUrlRequest (filename*: string, content_type*: string, file_size*: integer) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/lessons/{lesson_id}/video-url` | Lấy URL video bài học | lesson_id* (path, integer) | 200 LessonVideoUrlResponse | Bearer bắt buộc |
| POST | `/lessons/{lesson_id}/viewing-sessions` | Bắt đầu phiên xem | lesson_id* (path, integer) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/sections/{section_id}/lessons` | Liệt kê bài học | section_id* (path, integer), skip (query, integer), limit (query, integer) | 200 array[LessonResponse] | Bearer bắt buộc |
| POST | `/sections/{section_id}/lessons` | Tạo bài học | section_id* (path, integer), JSON: LessonCreateRequest (title*: string, position: integer) | 201 LessonResponse | Bearer bắt buộc |

## Quiz và checkpoint

| Method | Endpoint | Chức năng | Đầu vào | Phản hồi thành công | Xác thực |
|---|---|---|---|---|---|
| GET | `/quizzes/{quiz_id}/attempts` | Lấy lịch sử lượt làm quiz | quiz_id* (path, integer), limit (query, integer), offset (query, integer) | 200 array[QuizAttemptResultResponse] | Bearer bắt buộc |
| POST | `/quizzes/{quiz_id}/attempts` | Nộp quiz | quiz_id* (path, integer), JSON: QuizSubmitRequest (request_id*: string, lesson_id: integer \| null, answers: array[QuizAnswerSubmit]) | 200 QuizAttemptResultResponse | Bearer bắt buộc |
| GET | `/sections/{section_id}/quiz` | Lấy quiz của chương | section_id* (path, integer), lesson_id (query, integer \| null) | 200 QuizDetailResponse | Bearer bắt buộc |
| GET | `/student/quizzes/history` | Lấy lịch sử quiz của student | skip (query, integer), limit (query, integer) | 200 array[QuizHistoryItemResponse] | Bearer bắt buộc |
| GET | `/students/me/checkpoint-history` | Lấy lịch sử checkpoint | offset (query, integer), limit (query, integer) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |

## Tiến độ học và flashcard

| Method | Endpoint | Chức năng | Đầu vào | Phản hồi thành công | Xác thực |
|---|---|---|---|---|---|
| GET | `/courses/{course_id}/progress` | Lấy tiến độ khóa học | course_id* (path, integer) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/students/me/courses` | Liệt kê khóa học của tôi | Không có | 200 array[MyCourseEnrollmentResponse] | Bearer bắt buộc |
| GET | `/students/me/learning-overview` | Lấy tổng quan quá trình học | Không có | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |

## Tutor và học bù

| Method | Endpoint | Chức năng | Đầu vào | Phản hồi thành công | Xác thực |
|---|---|---|---|---|---|
| POST | `/student/remediation` | Bắt đầu phiên học bù | JSON: Start (attempt_id*: integer, regenerate: boolean) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/student/remediation/{session_id}` | Lấy phiên học bù | session_id* (path, integer) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| POST | `/student/remediation/{session_id}/advance` | Chuyển sang bước tiếp theo | session_id* (path, integer), JSON: Advance (kind*: string, item_id*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| POST | `/student/remediation/{session_id}/practice` | Nộp câu trả lời luyện tập | session_id* (path, integer), JSON: Answers (answers*: array[string]) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| POST | `/tutor/remediations` | Tạo nội dung học bù cho câu hỏi | JSON: QuestionRemediationRequest (attempt_id*: integer, lesson_id*: integer, question_id*: integer, selected_option*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| POST | `/tutor/sessions` | Tạo phiên Tutor | JSON: TutorSessionCreateRequest (attempt_id*: integer) | 201 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| POST | `/tutor/sessions/{session_id}/messages` | Gửi tin nhắn | session_id* (path, integer), JSON: TutorMessageCreateRequest (message*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| POST | `/tutor/sessions/{session_id}/practice-attempts` | Nộp bài luyện tập | session_id* (path, integer), JSON: PracticeSubmission (answers*: array[string]) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |

## Báo cáo và phân tích cho Instructor

| Method | Endpoint | Chức năng | Đầu vào | Phản hồi thành công | Xác thực |
|---|---|---|---|---|---|
| GET | `/analytics/quizzes/{quiz_id}` | Lấy phân tích quiz | quiz_id* (path, integer) | 200 QuizAnalytics | Bearer bắt buộc |
| GET | `/instructor/courses` | Liệt kê khóa học của Instructor | Không có | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/instructor/courses/{course_id}` | Lấy khóa học của Instructor | course_id* (path, integer) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/instructor/courses/{course_id}/analytics` | Lấy phân tích khóa học | course_id* (path, integer) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/instructor/dashboard` | Lấy bảng điều khiển Instructor | Không có | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/instructor/review-queue` | Liệt kê hàng đợi review | Không có | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/instructor/students` | Liệt kê student | course_id (query, integer \| null) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/instructor/students/{student_id}` | Lấy hồ sơ student | student_id* (path, integer) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |

## Quản trị

| Method | Endpoint | Chức năng | Đầu vào | Phản hồi thành công | Xác thực |
|---|---|---|---|---|---|
| GET | `/admin/monitoring/jobs` | Liệt kê job giám sát | Không có | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/admin/users` | Liệt kê người dùng | search (query, string \| null) | 200 array[UserResponse] | Bearer bắt buộc |
| POST | `/admin/users` | Tạo người dùng | JSON: AdminUserCreateRequest (name*: string, email*: string, role*: string, password*: string) | 201 UserResponse | Bearer bắt buộc |
| PATCH | `/admin/users/{user_id}` | Cập nhật người dùng | user_id* (path, integer), JSON: AdminUserUpdateRequest (name: string \| null, email: string \| null, role: string \| null) | 200 UserResponse | Bearer bắt buộc |
| PATCH | `/admin/users/{user_id}/status` | Đặt trạng thái người dùng | user_id* (path, integer), JSON: AdminUserStatusRequest (enabled*: boolean) | 200 UserResponse | Bearer bắt buộc |
