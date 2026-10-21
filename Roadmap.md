# Roadmap LearnCloud

## Mục đích

Tài liệu này chuyển lộ trình 4 tuần trong LearnCloud Kien truc va lo trinh 4 tuan v3 thành kế hoạch thực hiện theo trạng thái tệp hiện tại của repository. Mục tiêu MVP không đổi: một LMS video-first, trong đó giảng viên tạo nội dung và duyệt nội dung AI trước khi publish; học viên đăng ký khóa học, học theo section, làm quiz checkpoint và dùng Tutor remediation khi chưa đạt.

Ngày đối chiếu: 17/10/2026.

## Kiến trúc đích

```text
Browser
  └─ React và Vite
       └─ REST JSON
            └─ FastAPI
                 ├─ PostgreSQL local, sau đó Amazon RDS
                 ├─ Storage adapter: local, sau đó S3
                 ├─ AI adapter: mock, sau đó Bedrock
                 └─ Processing adapter: local job, sau đó AWS workflow

CloudFront → API Gateway → Lambda → application → RDS
Browser ── presigned URL ──> S3
S3 event → EventBridge → Step Functions
                         ├─ MediaConvert
                         ├─ Transcribe
                         └─ Bedrock
CloudWatch ← logs, errors và metrics
```

Service không được gọi boto3 hoặc AWS SDK trực tiếp. Service chỉ gọi interface adapter; cấu hình và dependency chọn implementation local hoặc AWS.

## Tuần 1 — Chốt contract và dựng luồng course local

### Mục tiêu

Chạy được database local và backend; GET /courses trả course đã publish; frontend hiển thị danh sách và chi tiết course; fixture AI đọc được; có một endpoint AWS tối thiểu trả 200.

### Việc theo người

| Người | Việc thực hiện                                                                                                              | Tệp trọng tâm                                                                                                                           | Điều kiện xong                                                                  |
| ----- | --------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| A     | Chốt API contract, mở rộng schema/seed tối thiểu, hoàn thiện local setup và docker compose.                                 | docs/api-contract.md, database/schema.sql, database/seed.sql, docker-compose.yml, docs/local-setup.md                                   | Máy mới clone có thể khởi động PostgreSQL và backend theo hướng dẫn.            |
| B     | Khôi phục Vite/React và luồng list/detail; dựng UI bằng courses.mock.json, cuối tuần nối GET /courses và GET /courses/{id}. | frontend package/config, main/App/routes, api client/courses, CourseCard, CourseOutline, CourseListPage, CourseDetailPage, useCourses   | Từ danh sách bấm được vào chi tiết; UI hiện loading/error/empty cơ bản.         |
| C     | Xác nhận transcript, summary, concepts và quiz fixture khớp JSON Schema; giữ MockAIAdapter dùng fixture.                    | ai_pipeline fixtures, schemas, prompts; adapters/ai/base.py, mock_ai.py                                                                 | Fixture parse và validate được; mock trả summary, concepts và quiz nhất quán.   |
| D     | Hoàn thiện vertical slice course local và thử một Lambda/API Gateway tối thiểu.                                             | backend main/config/database, api/courses.py, courses_repo.py, course_service.py, models User/Course; infrastructure lambda/api-gateway | Health, GET /courses và GET /courses/{id} chạy local; endpoint AWS thử trả 200. |

### Thứ tự hoàn thành và tệp bàn giao

| Thứ tự | Thời điểm | Người | Tệp phải hoàn thành trong bước này | Bàn giao cho |
| --- | --- | --- | --- | --- |
| 1 | Ngày 1 | A | .env.example, docker-compose.yml, database/schema.sql, database/seed.sql, docs/api-contract.md, docs/local-setup.md | D dùng database và contract; B dùng contract để dựng UI. |
| 2 | Ngày 1-2 | D | backend/requirements.txt, backend/app/config.py, backend/app/database.py, backend/app/dependencies.py, backend/app/models/user.py, backend/app/models/course.py, backend/app/repositories/courses_repo.py, backend/app/services/course_service.py, backend/app/schemas/course.py, backend/app/api/courses.py, backend/app/main.py | B thay mock bằng GET /courses và GET /courses/{id}. |
| 3 | Ngày 1-2, song song bước 2 | C | ai_pipeline/schemas/summary.schema.json, ai_pipeline/schemas/quiz.schema.json, ai_pipeline/fixtures/transcript_sample.json, ai_pipeline/fixtures/summary_sample.json, ai_pipeline/fixtures/quiz_sample.json, ai_pipeline/prompts/summary.txt, ai_pipeline/prompts/key_concepts.txt, ai_pipeline/prompts/quiz_generation.txt, backend/app/adapters/ai/base.py, backend/app/adapters/ai/mock_ai.py | B có fixture chuẩn để thiết kế phần nội dung học. |
| 4 | Ngày 2-3 | B | frontend/package.json, frontend/vite.config.js, frontend/src/main.jsx, frontend/src/App.jsx, frontend/src/index.css, frontend/src/routes/AppRoutes.jsx, frontend/src/api/client.js, frontend/src/api/courses.api.js, frontend/src/components/courses/CourseCard.jsx, frontend/src/components/courses/CourseOutline.jsx, frontend/src/pages/CourseListPage.jsx, frontend/src/pages/CourseDetailPage.jsx, frontend/src/hooks/useCourses.js, frontend/src/mocks/courses.mock.json | A review; D xác nhận response thực tế hiển thị được. |
| 5 | Ngày 3-4 | A và D | infrastructure/lambda/hello_handler.py, infrastructure/lambda/README.md, infrastructure/api-gateway/README.md; A review toàn bộ tệp ở bước 1-4 | Cả nhóm có local flow và endpoint AWS thử nghiệm. |

### Thứ tự phụ thuộc

1. A chốt contract và schema trước.
2. D xác nhận field CourseResponse, B dựng mock UI song song.
3. C chốt fixture độc lập với UI.
4. Khi D có API local, B thay mock ở list/detail bằng API thật.

### Nghiệm thu tuần 1

- docker compose khởi động được database; hướng dẫn local không cần sửa tay.
- GET /health, GET /courses và GET /courses/{id} có response khớp contract.
- Frontend được khôi phục và hiển thị list/detail bằng API hoặc mock có kiểm soát.
- Fixture AI hợp lệ.
- Có bằng chứng một endpoint AWS tối thiểu hoạt động.

## Tuần 2 — LMS core, quiz và unlock

### Mục tiêu

Học viên đăng ký course, mở lesson được phép, lưu tiến độ, làm checkpoint; backend chấm điểm và chỉ mở section kế khi đạt từ 80 phần trăm. Upload thử S3 hoạt động qua presigned URL.

### Việc theo người

| Người | Việc thực hiện                                                                                                       | Tệp trọng tâm                                                                                                                         | Điều kiện xong                                                                                         |
| ----- | -------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| A     | Bổ sung migration hướng dẫn, lỗi/log dùng chung; hỗ trợ test unit quiz/unlock và review security.                    | backend/app/utils, database/migrations, backend/tests/unit                                                                            | Test thể hiện rõ ngưỡng 80 phần trăm và không bypass được unlock.                                      |
| B     | Hoàn thiện trang học, player, progress, quiz form/result và API client. Viết backend progress theo phân công.        | lessons/quizzes/progress APIs ở frontend; LearningPage; VideoPlayer; QuizForm; QuizResult; useLessonProgress; backend progress module | Student xem lesson, lưu tiến độ, submit quiz và thấy result từ API.                                    |
| C     | Triển khai quiz, attempt, chấm điểm, unlock và processor local từ transcript/fixture.                                | api/quizzes.py; schemas/models/repositories/services quiz; unlock_service.py; mock_transcriber; ai_pipeline/processors                | Đáp án đúng không rời server trước submit; đạt 80 phần trăm mở section kế; dưới 80 phần trăm không mở. |
| D     | Triển khai create/update course, section, lesson, enrollment, dependencies demo user, storage adapter và upload URL. | api sections/lessons/uploads/enrollments; models/repo/service liên quan; adapters/storage; infrastructure s3/iam                      | Instructor tạo course/section/lesson; curl hoặc script upload được file thử qua presigned URL.         |

### Thứ tự hoàn thành và tệp bàn giao

| Thứ tự | Thời điểm | Người | Tệp phải hoàn thành trong bước này | Bàn giao cho |
| --- | --- | --- | --- | --- |
| 1 | Ngày 1 | A | backend/app/utils/errors.py, backend/app/utils/logging.py, database/migrations/README.md, backend/tests/unit/test_quiz_service.py, backend/tests/unit/test_unlock_service.py | C dùng test làm tiêu chí quiz/unlock; D dùng migration guide. |
| 2 | Ngày 1-2 | D | database/schema.sql và migration tương ứng; backend/app/models/enrollment.py, backend/app/models/section.py, backend/app/models/lesson.py, backend/app/repositories/lessons_repo.py, backend/app/services/lesson_service.py, backend/app/api/sections.py, backend/app/api/lessons.py, backend/app/api/enrollments.py, backend/app/dependencies.py | B và C có section, lesson, enrollment và demo user để tích hợp. |
| 3 | Ngày 2 | C | backend/app/models/quiz.py, backend/app/schemas/quiz.py, backend/app/repositories/quizzes_repo.py, backend/app/services/quiz_service.py, backend/app/services/unlock_service.py, backend/app/api/quizzes.py, backend/app/adapters/transcription/mock_transcriber.py, ai_pipeline/processors/normalize_transcript.py, ai_pipeline/processors/build_summary.py, ai_pipeline/processors/build_key_concepts.py, ai_pipeline/processors/build_quiz.py | B gọi quiz API; A chạy unit test. |
| 4 | Ngày 2-3 | B | backend/app/models/progress.py, backend/app/schemas/progress.py, backend/app/repositories/progress_repo.py, backend/app/services/progress_service.py, backend/app/api/progress.py, frontend/src/api/lessons.api.js, frontend/src/api/quizzes.api.js, frontend/src/api/progress.api.js, frontend/src/components/learning/VideoPlayer.jsx, frontend/src/components/quiz/QuizForm.jsx, frontend/src/components/quiz/QuizResult.jsx, frontend/src/components/progress/ProgressBar.jsx, frontend/src/pages/LearningPage.jsx, frontend/src/hooks/useLessonProgress.js, frontend/src/utils/scoreBand.js | C xác nhận API attempt; D xác nhận lesson authorization. |
| 5 | Ngày 3-4 | D, sau đó B | backend/app/adapters/storage/base.py, backend/app/adapters/storage/local_storage.py, backend/app/adapters/storage/s3_storage.py, backend/app/services/upload_service.py, backend/app/api/uploads.py, infrastructure/s3/README.md, infrastructure/iam/README.md; sau đó B kiểm tra frontend/src/api/uploads.api.js | Upload test qua presigned URL; không cần UI form hoàn chỉnh. |
| 6 | Cuối tuần | A | Review các tệp bước 2-5 và chạy backend/tests/unit/test_quiz_service.py, backend/tests/unit/test_unlock_service.py | Khóa được student flow local. |

### Dữ liệu và bảo mật phải hoàn tất

- Database có bảng sections, lessons, enrollments, lesson_progress, quizzes, questions, quiz_attempts và quiz_answers, với các UNIQUE constraint trong tài liệu kiến trúc.
- dependencies.py lấy user mẫu từ X-Demo-User và kiểm tra role ở backend.
- Student chỉ thấy course đã publish, lesson được enrollment/unlock và quiz đã approve.
- Chỉ backend chấm điểm; request client không được mang score quyết định kết quả.
- Presigned URL có expiry và IAM tối thiểu; video không đi qua Lambda.

### Nghiệm thu tuần 2

Student flow local chạy được: enroll → lesson → progress → quiz → score. Tạo attempt dưới 80 phần trăm không thể gọi API để xem section kế; đạt từ 80 phần trăm thì API cho phép tiếp tục.

## Tuần 3 — Pipeline AI, review instructor và workflow AWS

### Mục tiêu

Một video mẫu tạo được transcript, summary, key concepts và quiz nháp; nội dung dừng ở REVIEW_REQUIRED; instructor sửa/approve trước khi publish. AWS chứng minh một workflow hẹp từ S3 event tới xử lý.

### Việc theo người

| Người | Việc thực hiện                                                                                                  | Tệp trọng tâm                                                                                                                                                            | Điều kiện xong                                                                                           |
| ----- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| A     | Cập nhật architecture.md theo code, hỗ trợ integration test quiz flow và review contract mới.                   | architecture.md, backend/tests/integration/test_quiz_flow.py                                                                                                             | Tài liệu phản ánh local/AWS adapter và integration test chạy xanh.                                       |
| B     | Khôi phục/hoàn thiện upload, status, transcript/summary, review UI, LoginPage demo và dashboard instructor.     | uploads.api.js, review.api.js, VideoUploadForm, AIContentReview, TranscriptPanel, SummaryPanel, ProcessingStatus, LessonReviewPage, InstructorDashboardPage, AuthContext | Instructor nhìn thấy status, lỗi/retry, sửa và approve bằng API thật.                                    |
| C     | Hoàn thiện processor, validation output, Bedrock/Transcribe adapter, review service và trạng thái quiz nháp.    | processors; adapters/ai/bedrock_ai.py; adapters/transcription/aws_transcribe.py; api/review.py; review_service.py                                                        | Một transcript/video mẫu tạo JSON hợp lệ; lỗi provider có fallback; nội dung chưa approve không publish. |
| D     | Dựng local processor, MediaConvert adapter, Step Functions, EventBridge, CloudWatch và state transition lesson. | adapters/video; api/lessons.py; lesson_service.py; step-functions; eventbridge; cloudwatch                                                                               | S3 event khởi chạy workflow hẹp; COMPLETED/FAILED lưu được; FAILED có log và retry.                      |

### Thứ tự hoàn thành và tệp bàn giao

| Thứ tự | Thời điểm | Người | Tệp phải hoàn thành trong bước này | Bàn giao cho |
| --- | --- | --- | --- | --- |
| 1 | Ngày 1 | C | ai_pipeline/processors/normalize_transcript.py, ai_pipeline/processors/build_summary.py, ai_pipeline/processors/build_key_concepts.py, ai_pipeline/processors/build_quiz.py, ai_pipeline/schemas/summary.schema.json, ai_pipeline/schemas/quiz.schema.json | D dùng output/schema để lưu state và nối workflow; B dùng response để dựng review UI. |
| 2 | Ngày 1-2 | D | backend/app/adapters/video/local_processor.py, backend/app/adapters/video/mediaconvert.py, backend/app/services/lesson_service.py, backend/app/api/lessons.py, infrastructure/step-functions/video_pipeline.asl.json, infrastructure/eventbridge/README.md, infrastructure/cloudwatch/README.md | C có lifecycle lesson để ghi content; B có processing status và retry API. |
| 3 | Ngày 2 | C | backend/app/adapters/ai/bedrock_ai.py, backend/app/adapters/transcription/aws_transcribe.py, backend/app/services/review_service.py, backend/app/api/review.py, backend/app/repositories/quizzes_repo.py | D lưu trạng thái REVIEW_REQUIRED; B kết nối review API. |
| 4 | Ngày 2-3 | B | frontend/src/api/uploads.api.js, frontend/src/api/review.api.js, frontend/src/components/instructor/VideoUploadForm.jsx, frontend/src/components/instructor/AIContentReview.jsx, frontend/src/components/instructor/ProcessingStatus.jsx, frontend/src/components/learning/TranscriptPanel.jsx, frontend/src/components/learning/SummaryPanel.jsx, frontend/src/pages/LoginPage.jsx, frontend/src/pages/InstructorDashboardPage.jsx, frontend/src/pages/LessonReviewPage.jsx, frontend/src/context/AuthContext.jsx, frontend/src/hooks/useProcessingStatus.js | A review UI states; C/D xác nhận request và state transition. |
| 5 | Ngày 3 | D | backend/app/api/courses.py, backend/app/services/course_service.py để thêm publish; infrastructure/deployment/deploy-checklist.md bản nháp | B xác nhận publish/review flow; A kiểm tra contract thay đổi. |
| 6 | Cuối tuần | A | architecture.md, backend/tests/integration/test_quiz_flow.py và review các tệp bước 1-5 | Pipeline demo có log, failure và retry. |

### Quy tắc trạng thái lesson

DRAFT → UPLOADED → PROCESSING → TRANSCRIBING → AI_PROCESSING → REVIEW_REQUIRED → PUBLISHED.

FAILED có thể xuất hiện tại bước xử lý; retry chỉ được chấp nhận từ trạng thái hợp lệ. Instructor approve AI content trước khi course/lesson được publish cho student.

### Phương án dự phòng

Nếu MediaConvert hoặc Transcribe chưa sẵn sàng, dùng video và transcript chuẩn bị sẵn để giữ luồng LMS. Tuy vậy vẫn phải chứng minh ít nhất một bước workflow hoặc provider AWS thật; không bỏ luồng course/quiz để mở rộng pipeline.

### Nghiệm thu tuần 3

Video mẫu hoặc transcript chuẩn bị sẵn chạy qua pipeline; instructor sửa/approve; content đã approve có thể publish. Trang UI không tự suy đoán thành công mà đọc trạng thái do API trả về.

## Tuần 4 — Tutor, bảo mật, tích hợp và demo

### Mục tiêu

Hoàn tất remediation Tutor, kiểm tra toàn bộ quyền truy cập, thực hiện demo ổn định 5-7 phút, có hướng dẫn cleanup AWS.

### Việc theo người

| Người | Việc thực hiện                                                                                                                     | Tệp trọng tâm                                                                         | Điều kiện xong                                                                                             |
| ----- | ---------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| A     | Điều phối integration, review bảo mật, hoàn thiện demo script và migration guide.                                                  | docs/demo-script.md, database/migrations/README.md                                    | Người ngoài chạy được demo theo tài liệu; danh sách bug và quyết định cắt scope được chốt.                 |
| B     | Hoàn thiện TutorPanel, QuizResult/LearningPage, loading/error/empty toàn cục. Chỉ sau khi MVP ổn định mới xét các trang extension. | tutor.api.js, TutorPanel, QuizResult, LearningPage, UI shared                         | Học viên thấy pass/fail, retry, thông báo unlock; UI không lộ correct answer.                              |
| C     | Triển khai Tutor session/message, context từ câu sai, practice question và analytics cơ bản.                                       | api/tutor.py, api/analytics.py, schemas/models/services tutor; tutor prompt/processor | Tutor chỉ truy cập attempt của student hiện tại, giải thích câu sai và tạo practice; có fallback provider. |
| D     | Rà dependencies/lesson permissions, IAM, budget, cleanup và triển khai AWS.                                                        | dependencies.py, lesson_service.py, deployment checklist, docs/aws-deployment.md      | Không còn tài nguyên thử nghiệm vô chủ; IAM tối thiểu; checklist deploy và rollback rõ ràng.               |

### Thứ tự hoàn thành và tệp bàn giao

| Thứ tự | Thời điểm | Người | Tệp phải hoàn thành trong bước này | Bàn giao cho |
| --- | --- | --- | --- | --- |
| 1 | Ngày 1 | C | ai_pipeline/prompts/tutor_remediation.txt, ai_pipeline/processors/build_tutor_context.py, backend/app/models/tutor.py, backend/app/schemas/tutor.py, backend/app/services/tutor_service.py, backend/app/api/tutor.py | B tích hợp TutorPanel; A kiểm tra attempt ownership. |
| 2 | Ngày 1-2, song song bước 1 | D | backend/app/dependencies.py, backend/app/services/lesson_service.py, infrastructure/deployment/deploy-checklist.md, docs/aws-deployment.md, infrastructure/iam/README.md, infrastructure/cloudwatch/README.md | C/B có quy tắc quyền cuối cùng và môi trường demo đã rà IAM. |
| 3 | Ngày 2 | C | backend/app/api/analytics.py và các truy vấn/service cần thiết cho metric cơ bản | B có response analytics ổn định; A xác nhận chỉ instructor sở hữu course truy cập được. |
| 4 | Ngày 2-3 | B | frontend/src/api/tutor.api.js, frontend/src/components/tutor/TutorPanel.jsx, frontend/src/components/quiz/QuizResult.jsx, frontend/src/pages/LearningPage.jsx, frontend/src/components/ui/Button.jsx, frontend/src/components/ui/ErrorMessage.jsx, frontend/src/components/ui/EmptyState.jsx, frontend/src/components/ui/Spinner.jsx, frontend/src/components/ui/ui.css | C xác nhận request Tutor; A kiểm tra loading/error/empty và không lộ đáp án. |
| 5 | Ngày 3 | A | docs/demo-script.md, database/migrations/README.md và checklist bug end-to-end | B/C/D diễn tập demo cùng dữ liệu cố định. |
| 6 | Ngày 4 | C → D → B → A | C khóa AI/Tutor; D xác nhận AWS và cleanup; B khóa UI; A duyệt PR cuối và chạy demo | Tạo bản demo cuối; extension admin/flashcard chỉ được giữ nếu không ảnh hưởng luồng MVP. |

### Nghiệm thu tuần 4

- Student làm quiz dưới 80 phần trăm, khởi tạo Tutor từ attempt của mình, luyện tập, retry và đạt từ 80 phần trăm.
- Backend chặn truy cập sai role, course chưa publish, lesson chưa unlock, quiz chưa approve và attempt không thuộc user.
- Instructor chỉ xem analytics của course mình sở hữu.
- Log/status pipeline tra cứu được; AWS budget alert và cleanup được kiểm tra.
- Toàn bộ unit test, integration test và demo flow chạy trước khi khóa bản.

## Lộ trình API và điều kiện hoàn thành

| Endpoint                                                                            | Tuần | Chủ sở hữu | Điều kiện hoàn thành                                             |
| ----------------------------------------------------------------------------------- | ---- | ---------- | ---------------------------------------------------------------- |
| GET /health                                                                         | 1    | A/D        | Trả health check và có trong app.                                |
| GET /courses, GET /courses/{id}                                                     | 1    | D          | Chỉ trả course đã publish cho student.                           |
| POST /courses, PATCH /courses/{id}                                                  | 2    | D          | Instructor sở hữu course mới được thay đổi.                      |
| POST /courses/{id}/sections, POST /sections/{id}/lessons                            | 2    | D          | Tạo structure với position hợp lệ.                               |
| GET /lessons/{id}                                                                   | 2    | D          | Kiểm tra enrollment, publish và unlock ở backend.                |
| POST /courses/{id}/enroll                                                           | 2    | D          | Chống enrollment trùng và xác định student từ dependency.        |
| PUT /lessons/{id}/progress, GET /courses/{id}/progress                              | 2    | B          | Lưu theo UNIQUE student/lesson, chỉ trả progress của caller.     |
| GET /sections/{id}/quiz, POST /quizzes/{id}/attempts, GET /students/me/quiz-history | 2    | C          | Không lộ đáp án trước submit; điểm/unlock do backend quyết định. |
| POST /lessons/{id}/upload-url                                                       | 2    | D          | Presigned URL có expiry, không lộ credential.                    |
| GET /lessons/{id}/processing-status, POST /lessons/{id}/retry                       | 3    | D          | Lưu status, log lỗi và chỉ retry state cho phép.                 |
| GET/PATCH /lessons/{id}/ai-content, POST /lessons/{id}/approve                      | 3    | C          | Instructor review trước publish; output validate theo schema.    |
| POST /courses/{id}/publish                                                          | 3    | D          | Không publish khi điều kiện review không đạt.                    |
| POST /tutor/sessions, POST /tutor/sessions/{id}/messages                            | 4    | C          | Session và attempt phải thuộc student hiện tại.                  |
| GET /instructor/courses/{id}/analytics                                              | 4    | C          | Chỉ instructor sở hữu course xem được metric cơ bản.             |

Mã lỗi tối thiểu cần được kiểm thử: 400 input sai, 401 chưa xác thực, 403 thiếu quyền hoặc chưa unlock, 404 không tồn tại, 409 trạng thái không hợp lệ và 500 lỗi server.

## Danh sách kiểm tra trước demo

- [ ] Frontend có package manifest hợp lệ, build được và không còn tệp source rỗng.
- [ ] API contract, ORM model, schema SQL và response thực tế thống nhất.
- [ ] Có migration cho mọi thay đổi sau schema ban đầu.
- [ ] Toàn bộ router cần thiết được đăng ký trong FastAPI.
- [ ] Student không xem được draft/unpublished content hoặc section chưa unlock.
- [ ] Quiz không trả correct answer trước submit; score từ client bị bỏ qua.
- [ ] Instructor approve AI content trước publish.
- [ ] Upload dùng presigned URL; IAM tối thiểu; không có secret trong repo.
- [ ] FAILED có log, status và retry.
- [ ] Unit test quiz/unlock và integration test flow chạy xanh.
- [ ] Demo theo thứ tự instructor → processing → review/approve → student quiz fail → Tutor → retry/pass → unlock.
- [ ] Tài nguyên AWS đã có budget alert và hướng dẫn cleanup.

## Rủi ro và cách kiểm soát

| Rủi ro                       | Cách xử lý                                                                                                    |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Frontend bị rỗng             | Ưu tiên khôi phục app shell và course flow trong tuần 1; giữ extension admin/flashcard ở backlog.             |
| Contract thay đổi giữa chừng | Cập nhật contract/schema trước code, thông báo các owner bị ảnh hưởng và chỉ merge sau review.                |
| AWS chậm hoặc quota lỗi      | Dùng adapter mock và fixture local; demo có transcript/video dự phòng; vẫn thử ít nhất một AWS workflow thật. |
| Lộ đáp án hoặc bypass unlock | Viết test ở service/API, không tin dữ liệu UI và trả 403 từ backend.                                          |
| Pipeline không quan sát được | Lưu trạng thái từng bước, log FAILED và có retry idempotent.                                                  |
| A quá tải review             | PR nhỏ, review trong ngày; B/C/D tiếp tục phần không phụ thuộc review.                                        |
| Scope bị phình               | Ưu tiên end-to-end một course và một video demo; cắt analytics nâng cao, admin và flashcard trước.            |
