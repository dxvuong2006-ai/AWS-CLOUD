# [Lịch sử] Runbook E2E K4 + K5 cô lập trên AWS

> **TÀI LIỆU LỊCH SỬ - KHÔNG XÁC MINH HIỆN TẠI.** Thời điểm áp dụng: snapshot E2E trước 17/11/2026; ngày chính xác không được ghi. Fixture, resource name và handler test bên dưới chỉ dành cho môi trường cô lập cũ; xem [hướng dẫn triển khai hiện tại](../../03-implementation/aws-deployment.md) trước khi thiết kế E2E mới.

> Giữ fixture Lesson 3 làm bằng chứng lần chạy thất bại. Hướng dẫn fixture Lesson 4, thứ tự sao chép S3, IAM policy đã render và cách dùng lại workflow cho Lesson N nằm trong `database/k5/e2e4/README.md`.

Runbook này tạo tài nguyên chỉ dành cho test; không sửa hoặc tái sử dụng Lambda K4 hay Step Functions production. Production cần giữ `VIDEO_AI_ENABLED=false` trong suốt E2E test.

## Định danh fixture cố định

- Database: `learncloud_k5_test`; login/owner: `learncloud_k5_test_user`.
- Lesson: `3`; upload: `00000000000000000000000000000003`; attempt: `0`.
- Run ID dự kiến: `158087c71b268297dfb20dfb02254b3dd6b34d9627bd092459655f552536e409`.
- Raw key: `lessons/3/raw/00000000000000000000000000000003.mp4`.
- Processed key dự kiến: `lessons/3/processed/00000000000000000000000000000003/attempt-1/video_720p.mp4`.
- Transcript key dự kiến: `ai-transcripts/158087c71b268297dfb20dfb02254b3dd6b34d9627bd092459655f552536e409/transcript.json`.

Run ID là SHA-256 của `00000000000000000000000000000003:0`. Không điền sẵn Step Functions execution ARN: K4 claim lưu giá trị thực của `$$.Execution.Id`, và mọi callback K4/K5 phải khớp execution đó.

## Tài nguyên AWS chỉ dành cho test

1. Lambda role `learncloud-video-pipeline-k5-e2e-test-role` và `learncloud-ai-worker-k5-e2e-test-role`, dùng `lambda-trust.json`, test policy tương ứng trong `infrastructure/iam/` và VPC ENI policy có sẵn.
2. MediaConvert role `learncloud-mediaconvert-k5-e2e-test-role`, dùng `mediaconvert-trust.json` và `mediaconvert-k5-e2e-test-permissions.json`.
3. Step Functions role `learncloud-k4-k5-e2e-test-sfn-role`, dùng `step-functions-trust.json` và `k4-k5-e2e-test-step-functions-permissions.json`.
4. Tạo trước log group cho hai Lambda test và log group Step Functions riêng có mã hóa, retention ngắn cho test.
5. Lambda `learncloud-video-pipeline-k5-e2e-test` và `learncloud-ai-worker-k5-e2e-test`, dùng test handler/config mẫu.
6. Standard state machine `learncloud-k4-k5-e2e-test`, tạo từ `k4-k5-e2e-test.asl.json` sau khi thay cả hai ARN placeholder test.
7. EventBridge recovery rule chỉ dành cho test, render từ `k4-k5-e2e-test-execution-failure.pattern.json`, scope đúng ARN state machine test và target K4 test Lambda. Cấp quyền invoke cho `events.amazonaws.com` với ARN rule chính xác làm `SourceArn`.

Dùng security group riêng cho Lambda. RDS có thể cho phép TCP/5432 từ SG đó, nhưng database credential chỉ được grant trên `learncloud_k5_test`. Cả hai test handler đều fail closed nếu `APP_ENV` khác `k5-integration-test`, driver không phải PostgreSQL hoặc URL user/database không khớp `learncloud_k5_test_user` / `learncloud_k5_test`.

## Đóng gói tại máy local

Đóng gói K4 test ZIP từ dependency folder Linux Python 3.12 x86_64 đã review:

```powershell
.\.venv\Scripts\python.exe backend\scripts\build_video_pipeline_package.py `
  --dependencies build\video-dependencies-k4-fixed `
  --include-test-support `
  --output build\video-pipeline-k4-k5-e2e-test.zip
```

Đóng gói K5 test ZIP từ cùng dependency folder đã review:

```powershell
.\.venv\Scripts\python.exe backend\scripts\build_ai_worker_package.py `
  --dependencies build\video-dependencies-k4-fixed `
  --include-test-support `
  --output build\ai-worker-k4-k5-e2e-test.zip
```

Chưa upload ZIP cho tới khi đã review SHA-256 và handler ở root archive.

Render ba input cho operator tại local. Script xác thực cả hai ARN chỉ trỏ tới Lambda dành riêng cho test và không gọi AWS:

```powershell
.\infrastructure\deployment\render-k4-k5-e2e-test.ps1 `
  -PipelineLambdaArn '<test K4 Lambda ARN>' `
  -AiWorkerLambdaArn '<test K5 Lambda ARN>' `
  -VideoPath '<local MP4 path>' `
  -OutputDirectory 'build\k4-k5-e2e-before-upload'
```

Chạy SQL đã render trước khi upload S3. Sau upload, gọi lại script với `-S3ETag '<ETag không có dấu nháy>'` và output directory khác. Dùng input đã render (và ASL nếu chưa tạo), nhưng **không chạy lại SQL fixture trùng**.

## Trình tự kiểm thử AWS

1. Tạo test role, log group, VPC/SG attachment rồi hai test Lambda. Inject URL đã được duyệt chỉ trỏ `learncloud_k5_test`; tuyệt đối không sao chép production `DATABASE_URL`. Giữ nguyên production function.
2. Thay `${TEST_PIPELINE_LAMBDA_ARN}` và `${TEST_AI_WORKER_ARN}` trong bản sao ASL test. Xác nhận ARN không chỉ tới function production. Tạo state machine Standard riêng cùng Step Functions test role. Sau đó tạo test recovery rule với ARN chính xác, target K4 test Lambda; guarded wrapper chỉ chuyển sự kiện trạng thái Step Functions sang recovery.
3. Lấy đúng kích thước byte của MP4 local. Thay `__VIDEO_SIZE_BYTES__` trong bản sao `add_k4_k5_e2e_fixture.sql` bằng số nguyên dương đó. Trong pgAdmin, kết nối bằng `learncloud_k5_test_user` rồi chạy SQL một lần.
4. Trong vòng 24 giờ, upload MP4 với `Content-Type: video/mp4` vào raw key chính xác. Ghi lại ETag hiện tại, bỏ dấu nháy bao quanh. Không overwrite object sau khi lấy ETag.
5. Thay `__S3_ETAG_WITHOUT_QUOTES__` trong state-machine input template. Chỉ start đúng một execution của **test state machine**.
6. Chỉ theo dõi test execution/log group. Trạng thái dự kiến: `CLAIMED -> SUBMITTING -> TRANSCODING -> VIDEO_READY -> COMPLETE`; Lesson đi từ `PROCESSING -> TRANSCRIBING -> AI_PROCESSING -> REVIEW_REQUIRED`.
7. Thành công khi trạng thái cuối là `ReviewRequired`, run `COMPLETE`, Lesson 3 là `REVIEW_REQUIRED`, transcript/summary/key concepts không rỗng, có một quiz chưa approve, ba question và ít nhất một flashcard chưa approve. Không trạng thái nào tự publish nội dung.

## Retry và xử lý lỗi

- Claim và Transcribe start xác định có tính idempotent trong cùng execution.
- Poll, verify, generate và finalize có thể retry an toàn; generate/finalize xác minh lại dữ liệu proof đã lưu. Submit không được ASL tự retry vì timeout của CreateJob không rõ job đã được nhận hay chưa.
- Không dùng Step Functions Console Redrive sau submit. Nếu chưa rõ submit thành công không, đối soát MediaConvert job trước. Execution thất bại ghi `FAILED`; dùng application retry để tạo attempt/run mới thay vì tái sử dụng run ID này.
- Step Functions Standard failure event được giao theo cơ chế best effort. Với test thủ công này, kiểm tra trực tiếp ledger sau execution bị stop/timeout trước khi cleanup.

## Rollback và dọn tài nguyên test

1. Chỉ stop test execution nếu còn chạy. Xác nhận không còn MediaConvert/Transcribe job test đang hoạt động.
2. Tắt/xóa recovery rule test và Lambda permission của nó; xóa test state machine, hai test Lambda, log group/role riêng. Gỡ ingress rule RDS từ test SG nếu đã thêm.
3. Chỉ xóa ba test prefix của Lesson 3: raw, processed và transcript run prefix chính xác nêu ở trên.
4. Trong pgAdmin, chỉ chạy `rollback_k4_k5_e2e_fixture.sql` sau khi mọi test execution đã dừng. Script có guard database/user/identity và chỉ xóa fixture 3.
5. Không reset PostgreSQL sequence. Lần E2E sau cần Lesson, upload ID, run ID và S3 prefix mới.
