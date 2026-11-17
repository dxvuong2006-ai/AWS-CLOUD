# [Lịch sử] Kế hoạch rollout production K4 + K5

> **TÀI LIỆU LỊCH SỬ - KHÔNG XÁC MINH HIỆN TẠI.** Thời điểm áp dụng: snapshot chuẩn bị rollout trước 17/11/2026; ngày chính xác không được ghi. Các tên resource, artifact hash, test result và quyết định readiness dưới đây chỉ có giá trị lịch sử; xem [hướng dẫn triển khai hiện tại](../../03-implementation/aws-deployment.md) trước mọi thao tác.

> Tài liệu chuẩn bị rollout lịch sử. Định danh account AWS và ARN tĩnh đã được gỡ. Lần dọn tài liệu không truy vấn AWS/RDS; mọi tài nguyên và kết quả readiness/test nêu dưới đây cần được xác minh lại trước khi xem là hiện trạng.

## Quyết định readiness

**GO có điều kiện cho một canary được kiểm soát; chưa phải quyết định GO production đầy đủ.**

Tài liệu rollout trước ghi nhận luồng K4/K5 có 84 test trọng tâm và 9 subtest; frontend có 64 test pass; cùng contract K4/K5 đã pass E2E trên AWS cô lập với Lesson 4. Các cổng vận hành còn lại khi đó gồm: chạy preflight production DB, xác nhận MediaConvert queue, kiểm tra kết nối VPC/DB của K5 mà không ghi dữ liệu nghiệp vụ, xác nhận đích APAC của Bedrock profile và SCP, đồng thời xử lý hoặc phê duyệt ngoại lệ cho bộ API test offline cũ. Đây là kết quả lịch sử, không phải xác nhận hiện tại.

## Luồng production được ghi nhận trong lần rà soát cũ

1. Rule `learncloud-video-upload` khớp S3 Object Created dưới `lessons/*/raw/*` rồi khởi chạy Standard workflow `learncloud-video-pipeline`.
2. K4 `claim` xác thực quan hệ upload/lesson và nhận quyền sở hữu ledger. Định danh upload/run xác định giúp một EventBridge delivery trùng trở thành no-op hoặc conflict an toàn, thay vì tạo thêm MediaConvert job.
3. K4 `submit` tạo một MediaConvert job. ASL không tự retry ranh giới không idempotent này.
4. K4 poll trạng thái, xác minh object đã xử lý và ghi `VIDEO_READY`.
5. `ai_enabled=false` kết thúc an toàn ở video-ready. Khi `ai_enabled=true`, workflow chỉ gọi `learncloud-ai-worker` để chạy Transcribe rồi tạo nội dung bằng Bedrock.
6. K4 `finalize_ai` xác minh nội dung K5 đã lưu và cập nhật Lesson thành `REVIEW_REQUIRED`, run thành `COMPLETE` trong một transaction.
7. Lỗi được xử lý qua K4 `fail`, ghi error an toàn và loại retry trước khi workflow kết thúc thất bại.

Báo cáo ASL cũ nhắc tới hai tên worker dưới đây; phải lấy ARN hiện tại từ inventory môi trường đã được duyệt:

- `learncloud-video-pipeline`
- `learncloud-ai-worker`

## E2E so với phương án production đã chuẩn bị

| Hạng mục | E2E | Chuẩn bị production |
|---|---|---|
| Database | `learncloud_k5_test`, có hard guard | `learncloud`, runtime thông thường; không có test guard |
| Lambda handler | Test wrapper | `video_pipeline_handler.handler`, `ai_worker_handler.handler` |
| Phạm vi tài nguyên | Chỉ Lesson 4 | `lessons/*/raw/*`, `lessons/*/processed/*`, `ai-transcripts/*` |
| Bật AI | Bắt buộc trong test | Ban đầu giữ cờ K4/K5 ở `false` |
| State machine | Tài nguyên test riêng | State machine production hiện có, cập nhật có versioning |
| Event source | Input test thủ công | S3 EventBridge rule hiện có; dự kiến event trùng |
| Kết quả DB | `COMPLETE/REVIEW_REQUIRED` | Cùng contract; instructor review trước khi publish |

ZIP production phải loại `app/test_database_guard.py`, `video_pipeline_test_handler.py` và `ai_worker_test_handler.py`. Builder khi đó hỗ trợ thêm test support tùy chọn bằng `--include-test-support`; không dùng tùy chọn này cho artifact production.

## Cổng database

Chạy `database/checks/production_k4_k5_preflight.sql` trong pgAdmin trước. Script chạy chỉ đọc trong transaction và từ chối database khác `learncloud`. Các mục được kiểm tra:

- Các bảng K4/K5 và content column bắt buộc.
- Migration ledger `0005` cùng sáu integrity constraint.
- Trạng thái Lesson, CHECK constraint và các row `APPROVED` cũ.
- Quyền của application role cần cho K4/K5.
- Tính toàn vẹn định danh upload/run.

Audit chỉ đọc trước đây ghi nhận ledger `0005` có mặt, nhưng database production vẫn đăng ký `0004` lịch sử cho phép `APPROVED`, trong khi code/schema hiện tại publish sau review. Migration `database/migrations/0009_reconcile_k4_k5_production.sql` được chuẩn bị để hội tụ schema. Migration này:

- Từ chối database không phải `learncloud` hoặc thiếu ledger/tương thích.
- Chỉ khóa bảng `lessons` trong khoảng DDL ngắn.
- Chuyển các row `APPROVED` hiện có sang `PUBLISHED`.
- Thay Lesson status CHECK và ghi version `0009`.
- Không chạy lại `0005`, không sửa K5 content hoặc pipeline identity.

Migration từng pass validation bằng PostgreSQL 16.15 Docker trên dữ liệu drift giả lập có row `APPROVED`. Trước khi áp dụng cần review số row bị ảnh hưởng và tạo RDS snapshot thông thường. Nếu không chấp nhận đổi tự động `APPROVED -> PUBLISHED`, dừng và giải quyết các row qua workflow review trước khi chạy `0009`.

Không áp dụng `0007`/`0008`, `V3` hoặc checkpoint migration chỉ để bật K4/K5; chúng thuộc nhánh xác thực, Tutor remediation hoặc lịch sử thay thế.

## Tài nguyên AWS

Giữ và cập nhật tại chỗ các tài nguyên đã tồn tại, sau khi xác minh inventory:

- Lambda K4 `learncloud-video-pipeline` và role `LearnCloudVideoPipelineLambdaRole`.
- Standard state machine `learncloud-video-pipeline` và role `LearnCloudVideoStateMachineRole`.
- EventBridge rule `learncloud-video-upload` và target role.
- S3 production bucket, MediaConvert queue hiện có và `LearnCloudVideoMediaConvertRole`.
- RDS/database, private subnet trong VPC và security path K4/RDS.
- Step Functions và K4 CloudWatch log group hiện có.

Tạo theo kế hoạch cũ:

- Lambda `learncloud-ai-worker` với execution role và log group riêng.
- K5 security group riêng, hoặc dùng SG Lambda hiện hữu sau review, có outbound tới RDS và AWS service endpoint/NAT.
- CloudWatch alarm/dashboard và AWS Budget hằng tháng ở mức thấp, kèm cost anomaly alert.
- Có thể dùng Step Functions published version và `PROD` alias để rollout theo tỷ lệ.

Cập nhật theo kế hoạch cũ:

- ZIP và environment K4; giữ `VIDEO_AI_ENABLED=false`.
- Step Functions role chỉ được invoke đúng K4 và K5.
- ASL production.
- K4/K5 inline policy và K5 VPC ENI permission.
- Chỉ cập nhật EventBridge nếu pattern/transformer đang chạy khác file đã render; không tạo rule upload thứ hai.

Tên chính xác của MediaConvert queue production không có trong repository. Lấy từ K4 config hiện hành trước khi render K4 policy. Đồng thời xác nhận private subnet ID, security group ID của K4/K5, cơ chế inject production DB credential, K5 role ARN, yêu cầu KMS cho RDS/bucket nếu có và destination Region/SCP của APAC inference profile. Không tự đoán các giá trị này.

## Ranh giới IAM

- **K4:** log stream cho đúng log group; S3 read/list trên raw/processed Lesson prefix; `mediaconvert:CreateJob` trên queue cụ thể; `GetJob`; `iam:PassRole` chỉ với `LearnCloudVideoMediaConvertRole` và chỉ cho MediaConvert.
- **K5:** log stream đúng log group; S3 read processed video/transcript và chỉ ghi vào `ai-transcripts/*`; Transcribe start giới hạn theo Region, output bucket/key pattern; chỉ đọc job `learncloud-k5-*`; chỉ invoke Nova Micro qua APAC inference profile đã duyệt.
- **Cả hai Lambda trong VPC:** sáu ENI action trong `infrastructure/iam/lambda-vpc-permissions.json`. Các EC2 API này cần `Resource: "*"`; không mở rộng statement khác.
- **Step Functions:** chỉ invoke hai Lambda production. API chuyển log CloudWatch cần `Resource: "*"`.
- **EventBridge:** `states:StartExecution` chỉ trên ARN state machine production chính xác.
- **MediaConvert:** chỉ đọc raw video và ghi processed output trong bucket production.

Source hiện yêu cầu `DATABASE_URL`; ứng dụng không tự đọc SSM/Secrets Manager lúc runtime. Dùng cơ chế inject secret production đã được duyệt và application DB user có quyền tối thiểu. Không đặt credential trong repository, ZIP, ASL, policy JSON hoặc log. Không thêm quyền Secrets Manager trừ khi runtime được thay đổi có chủ đích để tự lấy secret.

Với `apac.amazon.nova-micro-v1:0`, cho phép profile ARN tại Singapore cùng Nova foundation-model ARN ở mọi destination Region; ràng buộc bằng `bedrock:InferenceProfileArn`. Trước deploy, kiểm tra profile trên Console hoặc `GetInferenceProfile` và xác nhận Organizations SCP cho phép mọi destination. Chỉ một destination bị chặn cũng có thể làm cross-Region inference thất bại.

## Thứ tự triển khai được đề xuất trong runbook cũ

1. Chốt/ thông báo thời gian canary ngắn. Ghi code hash Lambda, environment, role policy, ASL revision/version, EventBridge target/pattern và alarm state hiện tại. Tạo RDS snapshot có thể phục hồi.
2. Chạy read-only preflight trong pgAdmin và giải quyết mọi exception. Review số `APPROVED` cũ; chỉ chạy `0009` sau khi nghiệp vụ chấp thuận, rồi chạy lại preflight.
3. Tạo trước `/aws/lambda/learncloud-ai-worker` với retention/encryption phù hợp. Tạo K5 role/SG, gắn K5 + VPC policy, xác minh RDS SG chỉ nhận ingress từ K5 mà không mở CIDR rộng.
4. Tạo K5 Lambda từ production ZIP với production handler, Python 3.12 x86_64, private subnet, `APP_ENV=production` và hai AI flag `false`. Inject `DATABASE_URL` theo cơ chế secret được duyệt. Không gọi business action.
5. Cập nhật K4 role/policy nếu cần, sau đó code/config K4. Giữ `VIDEO_PIPELINE_ENABLED=true`, `VIDEO_AI_ENABLED=false`, `AI_WORKER_ENABLED=false`.
6. Cập nhật Step Functions role để chỉ gọi đúng hai ARN Lambda. Nếu có thể, publish ASL đã review thành version; lưu định nghĩa cũ để rollback. Giữ nguyên một upload rule.
7. Xác minh chỉ có một S3 upload rule được bật trỏ tới workflow; không có S3 notification, API code path hoặc rule thứ hai cùng khởi chạy. Input transformer chỉ đưa `kind/bucket/key/etag`; cấu hình retry limit và DLQ phù hợp.
8. Kiểm tra IAM bằng policy simulation/Console; xác minh Bedrock profile destination, Transcribe output access, VPC egress/endpoints, quota, log retention, alarm và budget. Không dùng Lesson production cho bước này.
9. Mở maintenance window ngắn, không cho upload/retry video khác. Bật `AI_WORKER_ENABLED=true` trước; worker vẫn không hoạt động nếu workflow chưa gọi. Ngay trước một upload thử nghiệm, đặt K4 `VIDEO_AI_ENABLED=true`. Upload một Lesson canary nhỏ bằng tiếng Anh, do instructor test thật trong production sở hữu.
10. Giữ K4 `VIDEO_AI_ENABLED=true` tới khi execution đạt `COMPLETE/REVIEW_REQUIRED`: K4 kiểm tra lại live flag tại `finalize_ai`, nên tắt giữa chừng sẽ làm canary thất bại. Sau đó đặt flag về `false`, kết thúc maintenance và review nội dung/chi phí. Nếu không thể chặn upload khác, không dùng canary bằng global flag; trước tiên triển khai version/alias riêng cùng trigger path cô lập.
11. Chỉ khi mọi gate đạt mới bật lại K4 AI trong cửa sổ lưu lượng thấp và mở rộng dần. Step Functions alias chỉ phân luồng một tỷ lệ nhỏ khi EventBridge target alias ARN; nếu không, dùng cửa sổ flag chỉ cho một upload như trên.

## An toàn khi duplicate và retry

EventBridge có thể gọi một rule/target nhiều lần. Dùng database ledger làm lớp idempotency có thẩm quyền; không dựa vào delivery exactly-once. Xác nhận chỉ có một producer path. Giữ `submit` không có tự động retry vì timeout có thể xảy ra sau khi MediaConvert nhận job. Poll có giới hạn và tên job Transcribe xác định có thể retry an toàn. `RecordFailure -> Fail` là kết thúc có chủ ý; dùng recovery/reconcile rule rõ ràng, không redrive mù qua ranh giới không idempotent.

## Giám sát và kiểm soát chi phí

Đặt alarm cho Step Functions `ExecutionsFailed/TimedOut/Throttled`, `Errors/Throttles/Duration` của cả hai Lambda, MediaConvert job thất bại, Transcribe job lỗi/chạy lâu và Bedrock invocation lỗi/throttle. Dashboard đếm theo trạng thái workflow an toàn và theo dõi run bị kẹt quá thời gian chờ dự kiến. Không ghi transcript, prompt/output, DB URL, token hoặc raw AWS exception vào log.

Bắt đầu với reserved concurrency K5 thấp, kiểm soát quota dịch vụ, AWS Budget và cost anomaly monitor. Theo dõi phút output MediaConvert, giây audio Transcribe, token input/output Bedrock, thời lượng Lambda, Step Functions transition và tăng trưởng S3. Sau này có thể thêm application inference profile để phân bổ usage Bedrock mà không đổi content contract.

## Rollback

1. Tắt K4 `VIDEO_AI_ENABLED=false` trước; execution mới chỉ chạy video K4.
2. Không redrive execution lỗi cho tới khi xác định ranh giới non-idempotent cuối cùng. Để canary đã nhận quyền chạy xong hoặc dừng có chủ đích rồi đối soát ledger.
3. Nếu lỗi ở orchestration/K4, khôi phục state-machine version/definition cũ và ZIP/config K4 trước đó. Nếu lỗi chỉ thuộc K5, tắt K5.
4. Giữ lại review data và migration `0009`; không rollback schema bằng SQL phá hủy. Nội dung `REVIEW_REQUIRED` có thể được review/reject qua ứng dụng.
5. Giữ log, execution ARN, run ID, MediaConvert/Transcribe job ID và error code đã làm sạch trong incident record.

## Phân loại kết quả test trong báo cáo cũ

- Bộ K4/K5 trọng tâm: **PASS** — 84 test, 9 subtest.
- Bộ frontend: **PASS** — 64 test.
- PostgreSQL 16.15 preflight/migration/postflight: **PASS**.
- Legacy full-offline unittest runner: **FAIL** — 161 test, 51 failure, 21 error. Có 20 lỗi do test mock symbol `review_service.S3StorageAdapter` đã bị bỏ; 35 assertion nhận `401` từ authentication boundary mới; các lỗi còn lại phần lớn là logging/status do auth short-circuit. Một processing test cũng dùng patch storage cũ. Báo cáo cũ coi đây là độ lệch test harness/contract, không phải lỗi trong bộ K4/K5 trọng tâm, nhưng toàn repo khi đó vẫn đỏ. Cần sửa hoặc phê duyệt waiver cho các nhóm này trước rollout rộng.

Các kết quả trên là bản ghi lịch sử; không phải test đã chạy trong lượt dọn docs này.

## Artifact đã chuẩn bị trong báo cáo cũ

- `build/production-k4-k5-preparation/learncloud-video-pipeline-production.zip` — SHA-256 `9eb0ac94f1dd12615ddac5ca6cbe82dfb76521a0effae1dbe85214c4052dd627`.
- `build/production-k4-k5-preparation/learncloud-ai-worker-production.zip` — SHA-256 `6c8d7f0bb39404a42a3ca96371c6135cba7286c94a8809a487598e95f6e2c80f`.
- `build/production-k4-k5-preparation/video_pipeline.production.asl.json` — SHA-256 `327301fff6a8091ff45340e214d855553a32d15f290c84b8caa0b5c064aba01f`.
- `database/checks/production_k4_k5_preflight.sql` — SHA-256 `cebc5f0201fb846be511514a7781aedae80d27aa39f50a5841de799d0d608d8d`.
- `database/migrations/0009_reconcile_k4_k5_production.sql` — SHA-256 `9cf986badbe80ab06825f5f431a9c779f40e746e18a32903abd12e0a55c6431e`.

Runbook cũ hướng dẫn tạo lại bundle bằng `infrastructure/deployment/render-k4-k5-production.ps1` sau khi nhập đúng MediaConvert queue name và role ARN. Bundle khi đó cố ý bỏ K4 inline policy đã render vì chưa biết queue name; không được đoán giá trị này.
