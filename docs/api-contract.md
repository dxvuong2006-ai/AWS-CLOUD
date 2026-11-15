# LearnCloud — API Contract

**Quy ước:** Dấu `*` = trường bắt buộc theo OpenAPI; các trường không có dấu `*` là tùy chọn. `Bearer` = có khai báo HTTP Bearer trong OpenAPI; `—` = không có khai báo bảo mật cho route đó. “Chưa khai báo schema” nghĩa là OpenAPI không mô tả cấu trúc JSON trả về; không có nghĩa API không trả dữ liệu.

## Xác thực (8 API)

| STT | Method | Endpoint | Nội dung / chức năng | Đầu vào | Phản hồi | Auth |
|---:|---|---|---|---|---|---|
| 1 | `POST` | `/auth/register` | Đăng ký tài khoản | Body (`RegisterRequest`): `name*`, `email*`, `password*` | `201` — JSON, chưa khai báo schema | — |
| 2 | `POST` | `/auth/verify-email` | Xác minh email | Body (`VerifyEmailRequest`): `email*`, `code*` | `200` — JSON, chưa khai báo schema | — |
| 3 | `POST` | `/auth/resend-verification` | Gửi lại mã xác minh email | Body (`ResendVerificationRequest`): `email*` | `200` — JSON, chưa khai báo schema | — |
| 4 | `POST` | `/auth/forgot-password` | Yêu cầu đặt lại mật khẩu | Body (`ForgotPasswordRequest`): `email*` | `200` — JSON, chưa khai báo schema | — |
| 5 | `POST` | `/auth/reset-password` | Đặt lại mật khẩu bằng mã xác minh | Body (`ResetPasswordRequest`): `email*`, `code*`, `password*` | `200` — JSON, chưa khai báo schema | — |
| 6 | `GET` | `/auth/me` | Xem thông tin tài khoản hiện tại | Không có | `200` — `UserResponse` | Bearer |
| 7 | `PATCH` | `/auth/me` | Cập nhật hồ sơ cá nhân | Body (`UpdateProfileRequest`): `name*` | `200` — `UserResponse` | Bearer |
| 8 | `POST` | `/auth/change-password` | Đổi mật khẩu tài khoản | Body (`ChangePasswordRequest`): `current_password*`, `new_password*` | `200` — JSON, chưa khai báo schema | Bearer |

## Xác thực nội bộ (8 API)

| STT | Method | Endpoint | Nội dung / chức năng | Đầu vào | Phản hồi | Auth |
|---:|---|---|---|---|---|---|
| 9 | `POST` | `/auth/local/register` | Đăng ký tài khoản theo cơ chế nội bộ | Body (`RegisterRequest`): `name*`, `email*`, `password*` | `201` — JSON, chưa khai báo schema | — |
| 10 | `POST` | `/auth/local/verify-email` | Xác minh email theo cơ chế nội bộ | Body (`VerifyEmailRequest`): `email*`, `code*` | `200` — JSON, chưa khai báo schema | — |
| 11 | `POST` | `/auth/local/resend-verification` | Gửi lại mã xác minh nội bộ | Body (`ResendVerificationRequest`): `email*` | `200` — JSON, chưa khai báo schema | — |
| 12 | `POST` | `/auth/local/login` | Đăng nhập bằng cơ chế nội bộ | Body (`LoginRequest`): `email*`, `password*` | `200` — JSON, chưa khai báo schema | — |
| 13 | `POST` | `/auth/local/logout` | Đăng xuất phiên nội bộ | Không có | `200` — JSON, chưa khai báo schema | Bearer |
| 14 | `POST` | `/auth/local/forgot-password` | Yêu cầu khôi phục mật khẩu nội bộ | Body (`ForgotPasswordRequest`): `email*` | `200` — JSON, chưa khai báo schema | — |
| 15 | `POST` | `/auth/local/reset-password` | Đặt lại mật khẩu nội bộ | Body (`ResetPasswordRequest`): `email*`, `code*`, `password*` | `200` — JSON, chưa khai báo schema | — |
| 16 | `POST` | `/auth/local/change-password` | Đổi mật khẩu nội bộ | Body (`ChangePasswordRequest`): `current_password*`, `new_password*` | `200` — JSON, chưa khai báo schema | Bearer |

## Khóa học (6 API)

| STT | Method | Endpoint | Nội dung / chức năng | Đầu vào | Phản hồi | Auth |
|---:|---|---|---|---|---|---|
| 17 | `POST` | `/courses/{course_id}/publish` | Xuất bản khóa học | Path: `course_id*` | `200` — `CourseResponse`; Lỗi: `401`, `403`, `404`, `409` | Bearer |
| 18 | `GET` | `/courses` | Danh sách khóa học | Không có | `200` — `Array<CourseResponse>` | — |
| 19 | `POST` | `/courses` | Tạo khóa học | Body (`CourseCreateRequest`): `cover_image`, `title*`, `description`, `learning_objectives` | `201` — `CourseResponse` | Bearer |
| 20 | `GET` | `/courses/instructor/me` | Danh sách khóa học do tôi giảng dạy | Không có | `200` — `Array<CourseResponse>` | Bearer |
| 21 | `GET` | `/courses/{course_id}` | Chi tiết khóa học | Path: `course_id*` | `200` — `CourseResponse` | — |
| 22 | `PATCH` | `/courses/{course_id}` | Cập nhật thông tin khóa học | Path: `course_id*`; Body (`CourseUpdateRequest`): `cover_image`, `title`, `description`, `learning_objectives` | `200` — `CourseResponse` | Bearer |

## Chương học (2 API)

| STT | Method | Endpoint | Nội dung / chức năng | Đầu vào | Phản hồi | Auth |
|---:|---|---|---|---|---|---|
| 23 | `POST` | `/courses/{course_id}/sections` | Tạo chương trong khóa học | Path: `course_id*`; Body (`SectionCreateRequest`): `title*`, `position` | `201` — `SectionResponse` | Bearer |
| 24 | `GET` | `/courses/{course_id}/sections` | Danh sách chương của khóa học | Path: `course_id*` | `200` — `Array<SectionResponse>` | Bearer |

## Bài học (8 API)

| STT | Method | Endpoint | Nội dung / chức năng | Đầu vào | Phản hồi | Auth |
|---:|---|---|---|---|---|---|
| 25 | `GET` | `/lessons/{lesson_id}/content` | Xem nội dung bài học | Path: `lesson_id*` | `200` — JSON, chưa khai báo schema | Bearer |
| 26 | `GET` | `/lessons/{lesson_id}/processing-status` | Kiểm tra trạng thái xử lý video/AI | Path: `lesson_id*` | `200` — `LessonProcessingStatusResponse`; Lỗi: `401`, `403`, `404` | Bearer |
| 27 | `POST` | `/lessons/{lesson_id}/retry` | Yêu cầu xử lý lại bài học lỗi | Path: `lesson_id*` | `202` — `LessonProcessingStatusResponse`; Lỗi: `401`, `403`, `404`, `409`, `502`, `503` | Bearer |
| 28 | `POST` | `/sections/{section_id}/lessons` | Tạo bài học trong chương | Path: `section_id*`; Body (`LessonCreateRequest`): `title*`, `position` | `201` — `LessonResponse` | Bearer |
| 29 | `GET` | `/sections/{section_id}/lessons` | Danh sách bài học trong chương | Path: `section_id*`; Query: `skip`=0, `limit`=100 | `200` — `Array<LessonResponse>` | Bearer |
| 30 | `GET` | `/lessons/{lesson_id}` | Chi tiết bài học | Path: `lesson_id*` | `200` — `LessonResponse` | Bearer |
| 31 | `PATCH` | `/lessons/{lesson_id}` | Cập nhật thông tin bài học | Path: `lesson_id*`; Body (`LessonUpdateRequest`): `title`, `position` | `200` — `LessonResponse` | Bearer |
| 32 | `GET` | `/lessons/{lesson_id}/video-url` | Lấy đường dẫn phát video bài học | Path: `lesson_id*` | `200` — `LessonVideoUrlResponse`; Lỗi: `401`, `403`, `404`, `409`, `502` | Bearer |

## Tải video lên (2 API)

| STT | Method | Endpoint | Nội dung / chức năng | Đầu vào | Phản hồi | Auth |
|---:|---|---|---|---|---|---|
| 33 | `POST` | `/lessons/{lesson_id}/confirm-upload` | Xác nhận video đã tải lên | Path: `lesson_id*`; Body (`ConfirmUploadRequest`): `upload_id*` | `200` — `LessonProcessingStatusResponse` | Bearer |
| 34 | `POST` | `/lessons/{lesson_id}/upload-url` | Xin URL tạm để tải video lên | Path: `lesson_id*`; Body (`UploadUrlRequest`): `filename*`, `content_type*`, `file_size*` | `200` — JSON, chưa khai báo schema | Bearer |

## Duyệt nội dung AI (8 API)

| STT | Method | Endpoint | Nội dung / chức năng | Đầu vào | Phản hồi | Auth |
|---:|---|---|---|---|---|---|
| 35 | `GET` | `/instructor/review-queue` | Danh sách học liệu chờ giảng viên duyệt | Không có | `200` — JSON, chưa khai báo schema | Bearer |
| 36 | `POST` | `/lessons/{lesson_id}/review-drafts` | Sinh bản nháp nội dung AI để duyệt | Path: `lesson_id*`; Body (`DraftGeneration`): `transcript*`, `num_questions`, `allow_fallback` | `201` — `ReviewResponse` | Bearer |
| 37 | `GET` | `/lessons/{lesson_id}/review-draft` | Xem bản nháp nội dung AI | Path: `lesson_id*` | `200` — `ReviewResponse` | Bearer |
| 38 | `PUT` | `/lessons/{lesson_id}/review-draft` | Thay thế bản nháp nội dung AI | Path: `lesson_id*`; Body (`DraftUpdate`): `title*`, `summary*`, `key_concepts*`, `flashcards*`, `quiz_title*`, `questions*`, `expected_revision*` | `200` — `ReviewResponse` | Bearer |
| 39 | `POST` | `/lessons/{lesson_id}/review-draft/approvals` | Phê duyệt bản nháp AI | Path: `lesson_id*`; Body (`DraftApproval`): `expected_revision*` | `200` — `ReviewResponse` | Bearer |
| 40 | `GET` | `/lessons/{lesson_id}/ai-content` | Xem nội dung AI của bài học | Path: `lesson_id*` | `200` — JSON object, chưa khai báo cấu trúc | Bearer |
| 41 | `PATCH` | `/lessons/{lesson_id}/ai-content` | Chỉnh sửa một phần nội dung AI | Path: `lesson_id*`; Body: JSON object (không khai báo trường) | `200` — `ReviewResponse` | Bearer |
| 42 | `POST` | `/lessons/{lesson_id}/approve` | Phê duyệt nội dung AI của bài học | Path: `lesson_id*`; Body (`DraftApproval`): `expected_revision*` | `200` — `ReviewResponse` | Bearer |

## Quiz / Checkpoint (5 API)

| STT | Method | Endpoint | Nội dung / chức năng | Đầu vào | Phản hồi | Auth |
|---:|---|---|---|---|---|---|
| 43 | `GET` | `/sections/{section_id}/quiz` | Lấy checkpoint quiz của chương | Path: `section_id*`; Query: `lesson_id` | `200` — `QuizDetailResponse`; Lỗi: `403`, `404` | Bearer |
| 44 | `POST` | `/quizzes/{quiz_id}/attempts` | Nộp bài quiz / checkpoint | Path: `quiz_id*`; Body (`QuizSubmitRequest`): `request_id*`, `lesson_id`, `answers` | `200` — `QuizAttemptResultResponse`; Lỗi: `403`, `404`, `409` | Bearer |
| 45 | `GET` | `/quizzes/{quiz_id}/attempts` | Lịch sử các lần làm một quiz | Path: `quiz_id*`; Query: `limit`=20, `offset`=0 | `200` — `Array<QuizAttemptResultResponse>` | Bearer |
| 46 | `GET` | `/student/quizzes/history` | Lịch sử quiz của học viên | Query: `skip`=0, `limit`=50 | `200` — `Array<QuizHistoryItemResponse>` | Bearer |
| 47 | `GET` | `/courses/{course_id}/unlock-status` | Trạng thái mở khóa các chương | Path: `course_id*` | `200` — `Array<object>` | Bearer |

## AI Tutor (4 API)

| STT | Method | Endpoint | Nội dung / chức năng | Đầu vào | Phản hồi | Auth |
|---:|---|---|---|---|---|---|
| 48 | `POST` | `/tutor/sessions` | Tạo phiên AI Tutor | Body (`TutorSessionCreateRequest`): `attempt_id*` | `201` — JSON, chưa khai báo schema | Bearer |
| 49 | `POST` | `/tutor/sessions/{session_id}/messages` | Gửi câu hỏi cho AI Tutor | Path: `session_id*`; Body (`TutorMessageCreateRequest`): `message*` | `200` — JSON, chưa khai báo schema | Bearer |
| 50 | `POST` | `/tutor/sessions/{session_id}/practice-attempts` | Nộp bài luyện tập AI Tutor | Path: `session_id*`; Body (`PracticeSubmission`): `answers*` | `200` — JSON, chưa khai báo schema | Bearer |
| 51 | `POST` | `/tutor/remediations` | Giải thích một câu trả lời sai | Body (`QuestionRemediationRequest`): `attempt_id*`, `lesson_id*`, `question_id*`, `selected_option*` | `200` — JSON, chưa khai báo schema | Bearer |

## Tiến độ học (3 API)

| STT | Method | Endpoint | Nội dung / chức năng | Đầu vào | Phản hồi | Auth |
|---:|---|---|---|---|---|---|
| 52 | `POST` | `/lessons/{lesson_id}/viewing-sessions` | Khởi tạo phiên xem video | Path: `lesson_id*` | `200` — JSON, chưa khai báo schema | Bearer |
| 53 | `PUT` | `/lessons/{lesson_id}/progress` | Lưu tiến độ xem video/bài học | Path: `lesson_id*`; Body (`ProgressUpdateRequest`): `last_position_seconds*`, `watched_ranges*`, `playback_session_id*`, `sequence*`, `request_id*` | `200` — JSON object, chưa khai báo cấu trúc | Bearer |
| 54 | `GET` | `/courses/{course_id}/progress` | Xem tiến độ khóa học | Path: `course_id*` | `200` — JSON, chưa khai báo schema | Bearer |

## Flashcard (4 API)

| STT | Method | Endpoint | Nội dung / chức năng | Đầu vào | Phản hồi | Auth |
|---:|---|---|---|---|---|---|
| 55 | `GET` | `/lessons/{lesson_id}/flashcards` | Danh sách flashcard bài học | Path: `lesson_id*` | `200` — JSON, chưa khai báo schema | Bearer |
| 56 | `POST` | `/lessons/{lesson_id}/flashcards` | Tạo flashcard cho bài học | Path: `lesson_id*`; Body (`FlashcardCreateRequest`): `front*`, `back*`, `position*` | `201` — `FlashcardResponse` | Bearer |
| 57 | `PUT` | `/lessons/{lesson_id}/flashcards/{card_id}` | Cập nhật flashcard | Path: `lesson_id*`, `card_id*`; Body (`FlashcardUpdateRequest`): `front`, `back`, `position`, `is_approved` | `200` — `FlashcardResponse` | Bearer |
| 58 | `DELETE` | `/lessons/{lesson_id}/flashcards/{card_id}` | Xóa flashcard | Path: `lesson_id*`, `card_id*` | `204` — không có body | Bearer |

## Đăng ký khóa học (2 API)

| STT | Method | Endpoint | Nội dung / chức năng | Đầu vào | Phản hồi | Auth |
|---:|---|---|---|---|---|---|
| 59 | `GET` | `/students/me/courses` | Danh sách khóa học đã đăng ký | Không có | `200` — `Array<MyCourseEnrollmentResponse>` | Bearer |
| 60 | `POST` | `/courses/{course_id}/enroll` | Đăng ký tham gia khóa học | Path: `course_id*` | `201` — `EnrollmentResponse` | Bearer |

## Thống kê (2 API)

| STT | Method | Endpoint | Nội dung / chức năng | Đầu vào | Phản hồi | Auth |
|---:|---|---|---|---|---|---|
| 61 | `GET` | `/instructor/courses/{course_id}/analytics` | Thống kê học tập của khóa học | Path: `course_id*` | `200` — JSON, chưa khai báo schema | Bearer |
| 62 | `GET` | `/analytics/quizzes/{quiz_id}` | Thống kê kết quả của quiz | Path: `quiz_id*` | `200` — `QuizAnalytics` | Bearer |

## Quản trị (5 API)

| STT | Method | Endpoint | Nội dung / chức năng | Đầu vào | Phản hồi | Auth |
|---:|---|---|---|---|---|---|
| 63 | `GET` | `/admin/users` | Danh sách và tìm kiếm tài khoản | Query: `search` | `200` — `Array<UserResponse>` | Bearer |
| 64 | `POST` | `/admin/users` | Tạo tài khoản bởi quản trị viên | Body (`AdminUserCreateRequest`): `name*`, `email*`, `role*`, `password*` | `201` — `UserResponse` | Bearer |
| 65 | `PATCH` | `/admin/users/{user_id}` | Cập nhật thông tin/vai trò tài khoản | Path: `user_id*`; Body (`AdminUserUpdateRequest`): `name`, `email`, `role` | `200` — `UserResponse` | Bearer |
| 66 | `PATCH` | `/admin/users/{user_id}/status` | Bật hoặc khóa tài khoản | Path: `user_id*`; Body (`AdminUserStatusRequest`): `enabled*` | `200` — `UserResponse` | Bearer |
| 67 | `GET` | `/admin/monitoring/jobs` | Theo dõi công việc xử lý hệ thống | Không có | `200` — JSON, chưa khai báo schema | Bearer |

## Luồng giao diện (12 API)

| STT | Method | Endpoint | Nội dung / chức năng | Đầu vào | Phản hồi | Auth |
|---:|---|---|---|---|---|---|
| 68 | `GET` | `/instructor/courses` | Danh sách khóa học của giảng viên | Không có | `200` — JSON, chưa khai báo schema | Bearer |
| 69 | `GET` | `/instructor/courses/{course_id}` | Chi tiết khóa học phía giảng viên | Path: `course_id*` | `200` — JSON, chưa khai báo schema | Bearer |
| 70 | `GET` | `/instructor/dashboard` | Tổng quan dashboard giảng viên | Không có | `200` — JSON, chưa khai báo schema | Bearer |
| 71 | `GET` | `/instructor/students` | Danh sách học viên của giảng viên | Query: `course_id` | `200` — JSON, chưa khai báo schema | Bearer |
| 72 | `GET` | `/instructor/students/{student_id}` | Chi tiết học viên phía giảng viên | Path: `student_id*` | `200` — JSON, chưa khai báo schema | Bearer |
| 73 | `GET` | `/students/me/checkpoint-history` | Lịch sử checkpoint của học viên | Query: `offset`=0, `limit`=20 | `200` — JSON, chưa khai báo schema | Bearer |
| 74 | `GET` | `/courses/{course_id}/completion` | Trạng thái hoàn thành khóa học | Path: `course_id*` | `200` — JSON, chưa khai báo schema | Bearer |
| 75 | `POST` | `/student/remediation` | Bắt đầu phiên học bổ trợ | Body (`Start`): `attempt_id*`, `regenerate` | `200` — JSON, chưa khai báo schema | Bearer |
| 76 | `GET` | `/student/remediation/{session_id}` | Xem phiên học bổ trợ | Path: `session_id*` | `200` — JSON, chưa khai báo schema | Bearer |
| 77 | `POST` | `/student/remediation/{session_id}/advance` | Chuyển bước trong phiên bổ trợ | Path: `session_id*`; Body (`Advance`): `kind*`, `item_id*` | `200` — JSON, chưa khai báo schema | Bearer |
| 78 | `POST` | `/student/remediation/{session_id}/practice` | Nộp bài luyện tập bổ trợ | Path: `session_id*`; Body (`Answers`): `answers*` | `200` — JSON, chưa khai báo schema | Bearer |
| 79 | `GET` | `/students/me/learning-overview` | Tổng quan học tập của học viên | Không có | `200` — JSON, chưa khai báo schema | Bearer |

## Hệ thống (1 API)

| STT | Method | Endpoint | Nội dung / chức năng | Đầu vào | Phản hồi | Auth |
|---:|---|---|---|---|---|---|
| 80 | `GET` | `/health` | Kiểm tra trạng thái Backend | Không có | `200` — JSON, chưa khai báo schema | — |

**Ghi chú về phạm vi:** Đây là hợp đồng HTTP được công bố trong OpenAPI, không phải kết quả chạy thử từng endpoint trên AWS. Cột Auth thể hiện khai báo trong OpenAPI, không thay thế việc kiểm tra phân quyền thực tế.
