# LearnCloud — Kiến trúc phần mềm và phân công tệp

> Tài liệu mô tả kiến trúc MVP và quyền sở hữu các tệp theo kế hoạch LearnCloud v3. Cây thư mục đã được tạo làm khung; một số tệp có thể chưa có nội dung triển khai. Khi thay đổi API hoặc schema, cập nhật contract/schema trước và thông báo các thành viên liên quan.

## 1. Mục tiêu và phạm vi

LearnCloud là LMS video-first. Giảng viên tạo khóa học, tải video, xem lại nội dung AI sinh và duyệt trước khi xuất bản. Học viên đăng ký khóa học, học theo section/lesson, lưu tiến độ và làm quiz checkpoint. Tutor chỉ hỗ trợ ôn tập dựa trên câu trả lời sai và nội dung bài học.

MVP tập trung vào course/section/lesson, upload video, transcript, summary, key concepts, quiz nháp, instructor review, enrollment, progress, chấm quiz, mở khóa section và Tutor remediation. Chưa bao gồm thanh toán, diễn đàn, livestream, ứng dụng di động, DRM, RAG/vector database phức tạp hoặc analytics nâng cao.

## 2. Sơ đồ kiến trúc

### Chạy local trước

```text
Browser
  └── React + Vite (frontend/)
        └── REST/JSON
              └── FastAPI (backend/)
                    ├── PostgreSQL (database/)
                    ├── Storage adapter: local filesystem
                    ├── AI adapter: mock
                    ├── Transcription adapter: mock
                    └── Video adapter: local processor
```

### Đích triển khai AWS

```text
Browser → CloudFront → API Gateway → Lambda → FastAPI/application → RDS
Browser ── presigned URL ──> S3
S3 event → EventBridge → Step Functions
                      ├── MediaConvert
                      ├── Transcribe
                      └── Bedrock
CloudWatch ← logs, errors, metrics
```

FastAPI là môi trường phát triển local; thử một endpoint Lambda/API Gateway đơn giản sớm để kiểm tra phương án đóng gói. Nghiệp vụ không phụ thuộc SDK của nhà cung cấp: service gọi interface adapter, còn adapter thực hiện thao tác local hoặc AWS.

## 3. Các lớp và luồng nghiệp vụ

1. **Frontend (`frontend/src`)** hiển thị trang, component và trạng thái giao diện; gọi backend qua REST client trong `api/`. Frontend không truy cập database/S3 bằng credential, không quyết định quyền truy cập bảo mật và không tự chấm điểm quiz.
2. **API (`backend/app/api`)** nhận request, xác định dependency, validate bằng schema, gọi service và trả response theo `docs/api-contract.md`. Route không chứa nghiệp vụ dài hoặc truy vấn SQL trực tiếp.
3. **Schema (`backend/app/schemas`)** kiểm tra dữ liệu request/response. Không trả `correct_answer` cho client trước khi học viên nộp bài.
4. **Service (`backend/app/services`)** thực hiện quy tắc nghiệp vụ: course, upload/review, quiz, unlock, progress và Tutor. Service không gọi boto3/AWS SDK trực tiếp.
5. **Repository (`backend/app/repositories`)** chịu trách nhiệm đọc/ghi PostgreSQL; không chứa quy tắc phân quyền hoặc unlock.
6. **Model (`backend/app/models`)** biểu diễn dữ liệu lưu trữ; không trả nguyên ORM object cho client.
7. **Adapter (`backend/app/adapters`)** cung cấp các implementation cùng vai trò cho local và AWS. Chọn implementation qua cấu hình/dependency thay vì để service phụ thuộc provider.
8. **AI pipeline (`ai_pipeline`)** quản lý prompt, fixture, chuẩn hóa và kiểm tra output AI; prompt không rải trong route hoặc service.
9. **Infrastructure (`infrastructure`)** mô tả tài nguyên, workflow và cách triển khai AWS; không lưu access key/secret trong repository.

Luồng chính: instructor tạo course → section → lesson → upload video → xử lý video/transcript → tạo summary, key concepts và quiz nháp → instructor review/approve → publish → student enroll/học/lưu progress → submit quiz → backend chấm và quyết định mở khóa hoặc remediation.

Ngưỡng quiz phía backend:

| Điểm | Kết quả |
| --- | --- |
| ≥ 80% | Đạt checkpoint, có thể mở section tiếp theo |
| 50–79% | Gợi ý review nội dung và Tutor |
| < 50% | Remediation/practice rồi cho phép retry |

## 4. Quy ước phân công

- **Dũng — Trưởng nhóm, hỗ trợ và review:** không sở hữu module nghiệp vụ chính. Chuẩn bị nền tảng dùng chung, hỗ trợ file nhỏ của Hùng/Tuấn/Huy và review PR trước khi merge.
- **Hùng — Frontend và tiến độ học:** sở hữu frontend (trừ các tệp Dũng hỗ trợ) và module progress backend. Không làm logic chấm quiz, không gọi AWS trực tiếp.
- **Tuấn — AI pipeline, quiz và Tutor:** sở hữu pipeline AI, quiz/unlock, review nội dung AI, Tutor và analytics MVP. Không sửa API course/upload hoặc đổi JSON output khi chưa thông báo nhóm.
- **Huy — Backend course và Cloud/DevOps:** sở hữu backend course/section/lesson/upload/enrollment, storage/video adapter, infrastructure và hướng dẫn triển khai AWS. Không tự đổi upload contract hoặc sửa logic quiz.

Trong bảng dưới đây, ký hiệu `Dũng → Hùng` nghĩa là Dũng tạo/hỗ trợ tệp cho Hùng; chủ sở hữu module vẫn là Hùng. Với các test quiz/unlock, Tuấn là người thực hiện và Dũng hỗ trợ/review.

## 5. Cây tệp và trách nhiệm

### Tệp gốc

| Tệp | Phụ trách | Vai trò |
| --- | --- | --- |
| `README.md` | Dũng | Giới thiệu dự án, phạm vi, cách điều hướng tài liệu và lệnh bắt đầu. |
| `.gitignore` | Dũng | Loại trừ môi trường ảo, build output, cache, file local và secret. |
| `.env.example` | Dũng | Danh sách biến môi trường mẫu, không chứa giá trị bí mật. |
| `docker-compose.yml` | Dũng | Khởi chạy dịch vụ local, tối thiểu gồm PostgreSQL và backend theo cấu hình dự án. |

### Frontend — `frontend/` (Hùng; các file hỗ trợ được ghi riêng)

| Tệp/thư mục | Phụ trách | Vai trò |
| --- | --- | --- |
| `package.json`, `vite.config.js` | Hùng | Dependency và cấu hình phát triển/build Vite. |
| `src/main.jsx`, `src/App.jsx` | Hùng | Điểm vào React và component gốc. |
| `src/routes/AppRoutes.jsx` | Hùng | Khai báo điều hướng giữa các trang. |
| `src/api/client.js` | Hùng | HTTP client chung, base URL, header demo và xử lý lỗi HTTP. |
| `src/api/courses.api.js` | Hùng | Request liên quan danh sách/chi tiết course. |
| `src/api/lessons.api.js` | Hùng | Request lesson và nội dung học. |
| `src/api/quizzes.api.js` | Hùng | Gửi câu trả lời và nhận kết quả quiz từ backend. |
| `src/api/progress.api.js` | Hùng | Đọc/cập nhật tiến độ học. |
| `src/api/uploads.api.js` | Hùng | Luồng request upload/presigned URL theo API contract. |
| `src/api/tutor.api.js` | Hùng | Gọi endpoint Tutor. |
| `src/components/layout/Navbar.jsx` | Dũng → Hùng | Điều hướng/layout dùng chung. |
| `src/components/courses/CourseCard.jsx` | Dũng → Hùng | Thẻ tóm tắt course trong danh sách. |
| `src/components/courses/CourseOutline.jsx` | Hùng | Outline section/lesson của course. |
| `src/components/learning/VideoPlayer.jsx` | Hùng | Phát nội dung video của lesson. |
| `src/components/learning/TranscriptPanel.jsx` | Hùng | Hiển thị transcript, có thể gắn timestamp. |
| `src/components/learning/SummaryPanel.jsx` | Hùng | Hiển thị summary và key concepts. |
| `src/components/quiz/QuizForm.jsx` | Hùng | Thu thập câu trả lời; không tự chấm hoặc làm lộ đáp án. |
| `src/components/quiz/QuizResult.jsx` | Hùng | Hiển thị kết quả do backend chấm và hành động tiếp theo. |
| `src/components/progress/ProgressBar.jsx` | Dũng → Hùng | Hiển thị tiến độ học. |
| `src/components/instructor/VideoUploadForm.jsx` | Hùng | UI upload video theo contract. |
| `src/components/instructor/AIContentReview.jsx` | Hùng | UI review/approve nội dung AI. |
| `src/components/tutor/TutorPanel.jsx` | Hùng | UI Tutor remediation. |
| `src/pages/LoginPage.jsx` | Hùng | Chọn user mẫu trong MVP; chưa tích hợp Cognito. |
| `src/pages/CourseListPage.jsx` | Hùng | Trang danh sách course. |
| `src/pages/CourseDetailPage.jsx` | Hùng | Trang chi tiết và outline course. |
| `src/pages/LearningPage.jsx` | Hùng | Trang học lesson, video, progress và checkpoint. |
| `src/pages/InstructorDashboardPage.jsx` | Hùng | Trang quản lý course dành cho instructor. |
| `src/pages/LessonReviewPage.jsx` | Hùng | Trang duyệt nội dung lesson/AI. |
| `src/hooks/useCourses.js` | Hùng | Đóng gói trạng thái và thao tác tải course. |
| `src/hooks/useLessonProgress.js` | Hùng | Đóng gói thao tác progress của lesson. |
| `src/context/AuthContext.jsx` | Hùng | Lưu user/role demo và trạng thái phiên giao diện. |
| `src/utils/scoreBand.js` | Dũng → Hùng | Ánh xạ band điểm sang thông điệp giao diện; backend vẫn là nơi quyết định quyền. |
| `src/mocks/courses.mock.json` | Hùng | Dữ liệu giả cho UI trước khi API course hoàn thiện. |

### Backend — `backend/` (Huy, trừ progress/quiz/Tutor/review)

| Tệp/thư mục | Phụ trách | Vai trò |
| --- | --- | --- |
| `requirements.txt` | Huy | Dependency Python của backend. |
| `app/main.py` | Huy | Khởi tạo FastAPI, đăng ký router và middleware cần thiết. |
| `app/config.py` | Huy | Đọc và kiểm tra cấu hình môi trường. |
| `app/dependencies.py` | Huy | Khởi tạo/chia sẻ dependency như repository và adapter. |
| `app/api/health.py` | Dũng → Huy | Endpoint health check. |
| `app/api/courses.py` | Huy | API tạo, đọc, cập nhật và publish course. |
| `app/api/sections.py` | Huy | API quản lý section. |
| `app/api/lessons.py` | Huy | API quản lý lesson và nội dung lesson. |
| `app/api/uploads.py` | Huy | Khởi tạo upload và cập nhật trạng thái xử lý video. |
| `app/api/enrollments.py` | Huy | API đăng ký học course. |
| `app/schemas/course.py`, `app/schemas/section.py` | Dũng → Huy | Schema contract cho course và section. |
| `app/schemas/lesson.py` | Huy | Schema request/response cho lesson. |
| `app/models/user.py`, `course.py`, `section.py`, `lesson.py` | Huy | Model người dùng và cấu trúc khóa học/nội dung. |
| `app/models/enrollment.py` | Huy | Model đăng ký khóa học. |
| `app/repositories/courses_repo.py` | Huy | Truy vấn/ghi dữ liệu course và section. |
| `app/repositories/lessons_repo.py` | Huy | Truy vấn/ghi lesson và trạng thái xử lý. |
| `app/services/course_service.py` | Huy | Quy tắc tạo, cập nhật, publish course/section. |
| `app/services/lesson_service.py` | Huy | Nghiệp vụ lesson và chuyển trạng thái xử lý. |
| `app/services/upload_service.py` | Huy | Điều phối upload qua storage adapter, không gọi SDK trực tiếp. |
| `app/adapters/storage/base.py` | Huy | Interface cho lưu trữ video. |
| `app/adapters/storage/local_storage.py` | Huy | Storage implementation chạy local. |
| `app/adapters/storage/s3_storage.py` | Huy | Storage implementation trên S3/presigned URL. |
| `app/adapters/video/local_processor.py` | Huy | Xử lý video local/mock cho luồng phát triển. |
| `app/adapters/video/mediaconvert.py` | Huy | Adapter tích hợp AWS MediaConvert. |
| `app/utils/errors.py`, `app/utils/logging.py` | Dũng → all | Quy ước lỗi và logging dùng chung. |

#### Backend progress — Hùng

| Tệp | Vai trò |
| --- | --- |
| `app/api/progress.py` | Endpoint đọc/cập nhật tiến độ lesson. |
| `app/schemas/progress.py` | Validate dữ liệu progress request/response. |
| `app/models/progress.py` | Model tiến độ học. |
| `app/repositories/progress_repo.py` | Lưu/đọc progress trong PostgreSQL. |
| `app/services/progress_service.py` | Quy tắc cập nhật watched time/completion. |

#### Backend AI review, quiz, unlock, Tutor và analytics — Tuấn

| Tệp | Vai trò |
| --- | --- |
| `app/api/review.py`, `app/services/review_service.py` | Review/approve nội dung AI trước publish. |
| `app/api/quizzes.py`, `app/schemas/quiz.py`, `app/models/quiz.py` | Contract và model quiz/question/attempt. |
| `app/repositories/quizzes_repo.py` | Truy vấn quiz và lưu attempts/answers. |
| `app/services/quiz_service.py` | Chấm điểm server-side; không tin điểm từ frontend. |
| `app/services/unlock_service.py` | Quyết định quyền truy cập section dựa trên kết quả checkpoint. |
| `app/api/tutor.py`, `app/schemas/tutor.py`, `app/models/tutor.py` | Contract/model cho Tutor và ngữ cảnh remediation. |
| `app/services/tutor_service.py` | Tạo hướng dẫn ôn tập gắn với lỗi và nội dung lesson. |
| `app/api/analytics.py` | Endpoint analytics cơ bản trong phạm vi MVP. |

#### Test backend — Tuấn thực hiện, Dũng hỗ trợ

| Tệp | Vai trò |
| --- | --- |
| `tests/unit/test_quiz_service.py` | Kiểm thử quy tắc chấm quiz. |
| `tests/unit/test_unlock_service.py` | Kiểm thử ngưỡng điểm và điều kiện mở khóa. |
| `tests/integration/test_quiz_flow.py` | Kiểm thử luồng tích hợp từ submit quiz tới kết quả/unlock. |

### AI pipeline — `ai_pipeline/` (Tuấn)

| Tệp/thư mục | Vai trò |
| --- | --- |
| `README.md` | Cách chạy pipeline, fixture và quy ước output. |
| `prompts/summary.txt` | Prompt tạo summary. |
| `prompts/key_concepts.txt` | Prompt trích xuất key concepts. |
| `prompts/quiz_generation.txt` | Prompt tạo quiz nháp. |
| `prompts/tutor_remediation.txt` | Prompt tạo nội dung remediation có phạm vi. |
| `schemas/summary.schema.json`, `schemas/quiz.schema.json` | Ràng buộc output có cấu trúc. |
| `processors/normalize_transcript.py` | Chuẩn hóa transcript và timestamp. |
| `processors/build_summary.py` | Tạo/chuẩn hóa summary. |
| `processors/build_key_concepts.py` | Tạo/chuẩn hóa key concepts. |
| `processors/build_quiz.py` | Tạo quiz nháp theo schema. |
| `processors/build_tutor_context.py` | Tạo ngữ cảnh Tutor từ câu sai và nội dung liên quan. |
| `fixtures/transcript_sample.json`, `summary_sample.json`, `quiz_sample.json` | Dữ liệu mẫu để phát triển/kiểm thử ổn định. |

### Database — `database/` (Dũng)

| Tệp | Vai trò |
| --- | --- |
| `schema.sql` | Schema PostgreSQL MVP; UUID primary key, thời gian UTC, JSONB phù hợp cho transcript/key concepts. |
| `seed.sql` | User mẫu và dữ liệu demo; tuần 1–2 dùng header `X-Demo-User`, không cần Cognito. |
| `migrations/README.md` | Quy ước lưu lịch sử migration; thay đổi DB phải có migration tương ứng. |

Các nhóm bảng chính: `users`, `courses`, `sections`, `lessons`, `enrollments`, `lesson_progress`, `quizzes`, `questions`, `quiz_attempts`, `quiz_answers`. `questions.correct_answer` chỉ được backend dùng để chấm; không trả về trước khi submit. Enrollment và progress có ràng buộc duy nhất theo cặp student/course hoặc student/lesson.

### Infrastructure — `infrastructure/`

| Tệp/thư mục | Phụ trách | Vai trò |
| --- | --- | --- |
| `lambda/README.md`, `lambda/hello_handler.py` | Huy | Lambda tối thiểu để thử sớm cách đóng gói/deploy. |
| `api-gateway/README.md` | Huy | Ghi chú cấu hình API Gateway. |
| `s3/README.md` | Huy | Bucket, upload và presigned URL. |
| `iam/README.md` | Huy | Quyền IAM tối thiểu theo dịch vụ. |
| `step-functions/video_pipeline.asl.json` | Huy | Định nghĩa workflow xử lý video. |
| `eventbridge/README.md` | Huy | Sự kiện kích hoạt pipeline. |
| `cloudwatch/README.md` | Huy | Logging, lỗi và metrics cơ bản. |
| `deployment/deploy-checklist.md` | Huy | Checklist triển khai và xác minh môi trường AWS. |

### Tài liệu — `docs/`

| Tệp | Phụ trách | Vai trò |
| --- | --- | --- |
| `architecture.md` | Dũng | Tài liệu kiến trúc và phân công hiện tại. |
| `api-contract.md` | Dũng | Endpoint, payload, response và mã lỗi; là nguồn thống nhất cho frontend/backend. |
| `database.md` | Dũng | Mô tả bảng, quan hệ và quy tắc dữ liệu. |
| `local-setup.md` | Dũng | Hướng dẫn clone/chạy local với Docker và dữ liệu mẫu. |
| `aws-deployment.md` | Huy | Cách triển khai các tài nguyên AWS. |
| `demo-script.md` | Dũng | Kịch bản demo MVP. |

## 6. Mô hình dữ liệu và quy tắc bảo vệ nghiệp vụ

- Người dùng có role `STUDENT`, `INSTRUCTOR` hoặc `ADMIN`; MVP không lưu password và chưa tích hợp Cognito.
- Course có trạng thái `DRAFT`/`PUBLISHED`; nội dung AI chưa được instructor approve không được publish.
- Lesson đi qua các trạng thái `DRAFT`, `UPLOADED`, `PROCESSING`, `TRANSCRIBING`, `AI_PROCESSING`, `REVIEW_REQUIRED`, `PUBLISHED` hoặc `FAILED`.
- Quiz gắn với section; mỗi lần làm được lưu thành attempt và answer riêng.
- Backend tự tính điểm từ đáp án được lưu server-side. Client không thể chỉ gửi score để đạt điều kiện unlock.
- Kiểm tra role, enrollment và quyền unlock tại backend; giao diện chỉ phản ánh kết quả backend.
- Mã lỗi API tối thiểu: `400` input sai, `401` chưa xác thực, `403` thiếu quyền/chưa unlock, `404` không tồn tại, `409` trạng thái không hợp lệ, `500` lỗi server.
- Không commit credential, access key hoặc secret. Local config dùng `.env` cá nhân dựa trên `.env.example`.

## 7. Quy trình phối hợp và review

1. Mỗi thành viên làm trên nhánh riêng theo dạng `feature/<chữ-cái>-<việc>`.
2. Thay đổi API/schema phải cập nhật `docs/api-contract.md` hoặc `database/schema.sql` trước, rồi báo các owner bị ảnh hưởng.
3. Giữ PR nhỏ, mục tiêu khoảng 10 tệp trở xuống; owner module chịu trách nhiệm sửa code của mình.
4. Dũng review trước khi merge, tập trung vào: service không gọi AWS SDK trực tiếp; quyền/chấm điểm nằm ở backend; không có secret; response đúng API contract; có cách chạy hoặc test.
5. Hùng/Tuấn/Huy không tự sửa module của nhau nếu chưa phối hợp với owner. Dũng hỗ trợ và review nhưng không thay thế ownership module.

## 8. Thứ tự tích hợp

- **Tuần 1:** thống nhất API contract và database schema; chạy Docker/PostgreSQL/seed; Huy dựng course API, Hùng dựng UI và fixture mock, Tuấn chuẩn bị fixture/schema AI; thử Lambda/API Gateway tối thiểu.
- **Tuần 2:** hoàn thiện LMS core, upload adapter, progress, quiz và unlock; kiểm tra quyền/chấm điểm ở backend.
- **Tuần 3:** nối AI pipeline, instructor review và workflow AWS; login vẫn chọn user mẫu.
- **Tuần 4:** hoàn thiện Tutor remediation, hardening, tích hợp end-to-end và demo.

Mỗi tuần cần có ít nhất một luồng tích hợp chạy được. Chi tiết tiêu chí nghiệm thu và endpoint theo owner được quản lý trong tài liệu contract, checklist và kế hoạch triển khai của dự án.