# API contract

Nguồn chuẩn là OpenAPI được FastAPI tạo từ `backend/app/main.py`. Mỗi hàng tương ứng một operation đang đăng ký, gồm method, endpoint, mục đích, đầu vào, phản hồi thành công và xác thực. Body liệt kê các trường cấp một; `*` đánh dấu trường bắt buộc. Kiểu phản hồi là schema thành công được OpenAPI khai báo. Có thể xem OpenAPI tại `/openapi.json` hoặc `/docs` khi backend chạy.

“Bearer bắt buộc” nghĩa là gửi access token qua `Authorization: Bearer <token>`. Route công khai không yêu cầu token. Backend vẫn áp dụng vai trò, ownership, enrollment và trạng thái dữ liệu theo từng operation. JSON object ghi chú “schema chưa khai báo cụ thể” khi route không khai báo response model trong OpenAPI.

## Health

| Method | Endpoint | Chức năng | Đầu vào | Phản hồi thành công | Xác thực |
|---|---|---|---|---|---|
| GET | `/health` | Health Check | Không có | 200 JSON object (schema chưa khai báo cụ thể) | Công khai |

## Authentication and profile

| Method | Endpoint | Chức năng | Đầu vào | Phản hồi thành công | Xác thực |
|---|---|---|---|---|---|
| POST | `/auth/change-password` | Change Password | JSON: ChangePasswordRequest (current_password*: string, new_password*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| POST | `/auth/forgot-password` | Forgot Password | JSON: ForgotPasswordRequest (email*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Công khai |
| POST | `/auth/local/change-password` | Change | JSON: ChangePasswordRequest (current_password*: string, new_password*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| POST | `/auth/local/forgot-password` | Forgot | JSON: ForgotPasswordRequest (email*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Công khai |
| POST | `/auth/local/login` | Login | JSON: LoginRequest (email*: string, password*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Công khai |
| POST | `/auth/local/logout` | Logout | Không có | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| POST | `/auth/local/register` | Register | JSON: RegisterRequest (name*: string, email*: string, password*: string) | 201 JSON object (schema chưa khai báo cụ thể) | Công khai |
| POST | `/auth/local/resend-verification` | Resend | JSON: ResendVerificationRequest (email*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Công khai |
| POST | `/auth/local/reset-password` | Reset | JSON: ResetPasswordRequest (email*: string, code*: string, password*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Công khai |
| POST | `/auth/local/verify-email` | Verify Email | JSON: VerifyEmailRequest (email*: string, code*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Công khai |
| GET | `/auth/me` | Me | Không có | 200 UserResponse | Bearer bắt buộc |
| PATCH | `/auth/me` | Update Profile | JSON: UpdateProfileRequest (name*: string) | 200 UserResponse | Bearer bắt buộc |
| POST | `/auth/register` | Register | JSON: RegisterRequest (name*: string, email*: string, password*: string) | 201 JSON object (schema chưa khai báo cụ thể) | Công khai |
| POST | `/auth/resend-verification` | Resend Verification | JSON: ResendVerificationRequest (email*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Công khai |
| POST | `/auth/reset-password` | Reset Password | JSON: ResetPasswordRequest (email*: string, code*: string, password*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Công khai |
| POST | `/auth/verify-email` | Verify Email | JSON: VerifyEmailRequest (email*: string, code*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Công khai |

## Courses, sections and enrollment

| Method | Endpoint | Chức năng | Đầu vào | Phản hồi thành công | Xác thực |
|---|---|---|---|---|---|
| GET | `/courses` | List Courses | Không có | 200 array[CourseResponse] | Công khai |
| POST | `/courses` | Create Course | JSON: CourseCreateRequest (cover_image: string \| null, title*: string, description: string \| null, learning_objectives: array[string]) | 201 CourseResponse | Bearer bắt buộc |
| GET | `/courses/instructor/me` | List Instructor Courses | Không có | 200 array[CourseResponse] | Bearer bắt buộc |
| GET | `/courses/{course_id}` | Get Course | course_id* (path, integer) | 200 CourseResponse | Công khai |
| PATCH | `/courses/{course_id}` | Update Course | course_id* (path, integer), JSON: CourseUpdateRequest (cover_image: string \| null, title: string \| null, description: string \| null, learning_objectives: array[string]) | 200 CourseResponse | Bearer bắt buộc |
| GET | `/courses/{course_id}/completion` | Completion | course_id* (path, integer) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| POST | `/courses/{course_id}/enroll` | Enroll Course | course_id* (path, integer) | 201 EnrollmentResponse | Bearer bắt buộc |
| POST | `/courses/{course_id}/publish` | Publish Course | course_id* (path, integer) | 200 CourseResponse | Bearer bắt buộc |
| GET | `/courses/{course_id}/sections` | List Course Sections | course_id* (path, integer) | 200 array[SectionResponse] | Bearer bắt buộc |
| POST | `/courses/{course_id}/sections` | Create Section | course_id* (path, integer), JSON: SectionCreateRequest (title*: string, position: integer) | 201 SectionResponse | Bearer bắt buộc |
| GET | `/courses/{course_id}/unlock-status` | Get Course Unlock Status | course_id* (path, integer) | 200 array[object] | Bearer bắt buộc |

## Lessons, uploads and video

| Method | Endpoint | Chức năng | Đầu vào | Phản hồi thành công | Xác thực |
|---|---|---|---|---|---|
| GET | `/lessons/{lesson_id}` | Get Lesson | lesson_id* (path, integer) | 200 LessonResponse | Bearer bắt buộc |
| PATCH | `/lessons/{lesson_id}` | Update Lesson | lesson_id* (path, integer), JSON: LessonUpdateRequest (title: string \| null, position: integer \| null) | 200 LessonResponse | Bearer bắt buộc |
| GET | `/lessons/{lesson_id}/ai-content` | Get Ai Content | lesson_id* (path, integer) | 200 object | Bearer bắt buộc |
| PATCH | `/lessons/{lesson_id}/ai-content` | Patch Ai Content | lesson_id* (path, integer), JSON: object | 200 ReviewResponse | Bearer bắt buộc |
| POST | `/lessons/{lesson_id}/approve` | Approve Ai Content | lesson_id* (path, integer), JSON: DraftApproval (expected_revision*: string) | 200 ReviewResponse | Bearer bắt buộc |
| POST | `/lessons/{lesson_id}/confirm-upload` | Confirm Upload | lesson_id* (path, integer), JSON: ConfirmUploadRequest (upload_id*: string) | 200 LessonProcessingStatusResponse | Bearer bắt buộc |
| GET | `/lessons/{lesson_id}/content` | Get Lesson Content | lesson_id* (path, integer) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/lessons/{lesson_id}/flashcards` | Get Lesson Flashcards | lesson_id* (path, integer) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| POST | `/lessons/{lesson_id}/flashcards` | Create Flashcard | lesson_id* (path, integer), JSON: FlashcardCreateRequest (front*: string, back*: string, position*: integer) | 201 FlashcardResponse | Bearer bắt buộc |
| DELETE | `/lessons/{lesson_id}/flashcards/{card_id}` | Delete Flashcard | lesson_id* (path, integer), card_id* (path, integer) | 204 No Content | Bearer bắt buộc |
| PUT | `/lessons/{lesson_id}/flashcards/{card_id}` | Update Flashcard | lesson_id* (path, integer), card_id* (path, integer), JSON: FlashcardUpdateRequest (front: string \| null, back: string \| null, position: integer \| null, is_approved: boolean \| null) | 200 FlashcardResponse | Bearer bắt buộc |
| GET | `/lessons/{lesson_id}/processing-status` | Get Processing Status | lesson_id* (path, integer) | 200 LessonProcessingStatusResponse | Bearer bắt buộc |
| PUT | `/lessons/{lesson_id}/progress` | Save Lesson Progress | lesson_id* (path, integer), JSON: ProgressUpdateRequest (last_position_seconds*: number, watched_ranges*: array[array[object]], playback_session_id*: string, sequence*: integer, request_id*: string) | 200 object | Bearer bắt buộc |
| POST | `/lessons/{lesson_id}/retry` | Retry Lesson | lesson_id* (path, integer) | 202 LessonProcessingStatusResponse | Bearer bắt buộc |
| GET | `/lessons/{lesson_id}/review-draft` | Get Draft | lesson_id* (path, integer) | 200 ReviewResponse | Bearer bắt buộc |
| PUT | `/lessons/{lesson_id}/review-draft` | Update Draft | lesson_id* (path, integer), JSON: DraftUpdate (title*: string, summary*: string, key_concepts*: array[KeyConcept], flashcards*: array[FlashcardDraft], quiz_title*: string, questions*: array[ReviewQuestion], expected_revision*: string) | 200 ReviewResponse | Bearer bắt buộc |
| POST | `/lessons/{lesson_id}/review-draft/approvals` | Approve Draft | lesson_id* (path, integer), JSON: DraftApproval (expected_revision*: string) | 200 ReviewResponse | Bearer bắt buộc |
| POST | `/lessons/{lesson_id}/review-drafts` | Generate Draft | lesson_id* (path, integer), JSON: DraftGeneration (transcript*: string, num_questions: integer, allow_fallback: boolean) | 201 ReviewResponse | Bearer bắt buộc |
| POST | `/lessons/{lesson_id}/upload-url` | Create Upload Url | lesson_id* (path, integer), JSON: UploadUrlRequest (filename*: string, content_type*: string, file_size*: integer) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/lessons/{lesson_id}/video-url` | Get Lesson Video Url | lesson_id* (path, integer) | 200 LessonVideoUrlResponse | Bearer bắt buộc |
| POST | `/lessons/{lesson_id}/viewing-sessions` | Start Viewing Session | lesson_id* (path, integer) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/sections/{section_id}/lessons` | List Lessons | section_id* (path, integer), skip (query, integer), limit (query, integer) | 200 array[LessonResponse] | Bearer bắt buộc |
| POST | `/sections/{section_id}/lessons` | Create Lesson | section_id* (path, integer), JSON: LessonCreateRequest (title*: string, position: integer) | 201 LessonResponse | Bearer bắt buộc |

## Quiz and checkpoint

| Method | Endpoint | Chức năng | Đầu vào | Phản hồi thành công | Xác thực |
|---|---|---|---|---|---|
| GET | `/quizzes/{quiz_id}/attempts` | Get Quiz Attempt History | quiz_id* (path, integer), limit (query, integer), offset (query, integer) | 200 array[QuizAttemptResultResponse] | Bearer bắt buộc |
| POST | `/quizzes/{quiz_id}/attempts` | Submit Quiz | quiz_id* (path, integer), JSON: QuizSubmitRequest (request_id*: string, lesson_id: integer \| null, answers: array[QuizAnswerSubmit]) | 200 QuizAttemptResultResponse | Bearer bắt buộc |
| GET | `/sections/{section_id}/quiz` | Get Section Quiz | section_id* (path, integer), lesson_id (query, integer \| null) | 200 QuizDetailResponse | Bearer bắt buộc |
| GET | `/student/quizzes/history` | Get Student Quiz History | skip (query, integer), limit (query, integer) | 200 array[QuizHistoryItemResponse] | Bearer bắt buộc |
| GET | `/students/me/checkpoint-history` | History | offset (query, integer), limit (query, integer) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |

## Learning progress and flashcards

| Method | Endpoint | Chức năng | Đầu vào | Phản hồi thành công | Xác thực |
|---|---|---|---|---|---|
| GET | `/courses/{course_id}/progress` | Get Course Progress | course_id* (path, integer) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/students/me/courses` | List My Courses | Không có | 200 array[MyCourseEnrollmentResponse] | Bearer bắt buộc |
| GET | `/students/me/learning-overview` | Overview | Không có | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |

## Tutor and remediation

| Method | Endpoint | Chức năng | Đầu vào | Phản hồi thành công | Xác thực |
|---|---|---|---|---|---|
| POST | `/student/remediation` | Start | JSON: Start (attempt_id*: integer, regenerate: boolean) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/student/remediation/{session_id}` | Session | session_id* (path, integer) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| POST | `/student/remediation/{session_id}/advance` | Advance | session_id* (path, integer), JSON: Advance (kind*: string, item_id*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| POST | `/student/remediation/{session_id}/practice` | Practice | session_id* (path, integer), JSON: Answers (answers*: array[string]) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| POST | `/tutor/remediations` | Remediate Question | JSON: QuestionRemediationRequest (attempt_id*: integer, lesson_id*: integer, question_id*: integer, selected_option*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| POST | `/tutor/sessions` | Create Session | JSON: TutorSessionCreateRequest (attempt_id*: integer) | 201 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| POST | `/tutor/sessions/{session_id}/messages` | Send Message | session_id* (path, integer), JSON: TutorMessageCreateRequest (message*: string) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| POST | `/tutor/sessions/{session_id}/practice-attempts` | Submit Practice | session_id* (path, integer), JSON: PracticeSubmission (answers*: array[string]) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |

## Instructor reports and analytics

| Method | Endpoint | Chức năng | Đầu vào | Phản hồi thành công | Xác thực |
|---|---|---|---|---|---|
| GET | `/analytics/quizzes/{quiz_id}` | Get Quiz Analytics | quiz_id* (path, integer) | 200 QuizAnalytics | Bearer bắt buộc |
| GET | `/instructor/courses` | Courses | Không có | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/instructor/courses/{course_id}` | Course | course_id* (path, integer) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/instructor/courses/{course_id}/analytics` | Get Course Analytics | course_id* (path, integer) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/instructor/dashboard` | Dashboard | Không có | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/instructor/review-queue` | List Review Queue | Không có | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/instructor/students` | Students | course_id (query, integer \| null) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/instructor/students/{student_id}` | Student | student_id* (path, integer) | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |

## Administration

| Method | Endpoint | Chức năng | Đầu vào | Phản hồi thành công | Xác thực |
|---|---|---|---|---|---|
| GET | `/admin/monitoring/jobs` | List Monitoring Jobs | Không có | 200 JSON object (schema chưa khai báo cụ thể) | Bearer bắt buộc |
| GET | `/admin/users` | List Users | search (query, string \| null) | 200 array[UserResponse] | Bearer bắt buộc |
| POST | `/admin/users` | Create User | JSON: AdminUserCreateRequest (name*: string, email*: string, role*: string, password*: string) | 201 UserResponse | Bearer bắt buộc |
| PATCH | `/admin/users/{user_id}` | Update User | user_id* (path, integer), JSON: AdminUserUpdateRequest (name: string \| null, email: string \| null, role: string \| null) | 200 UserResponse | Bearer bắt buộc |
| PATCH | `/admin/users/{user_id}/status` | Set User Status | user_id* (path, integer), JSON: AdminUserStatusRequest (enabled*: boolean) | 200 UserResponse | Bearer bắt buộc |
