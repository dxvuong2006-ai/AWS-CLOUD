# CloudWatch

**MANUAL AWS CONSOLE STEP:** tạo các log groups trước Lambda vì policy mẫu không
cấp CreateLogGroup. Chọn ap-southeast-1; retention khởi đầu 7 ngày cho môi trường lab.

| Log group | Nguồn |
| --- | --- |
| /aws/vendedlogs/states/learncloud-video-pipeline | Standard workflow |
| /aws/lambda/learncloud-video-pipeline | claim, submit, poll, verify, fail, reconcile |
| /aws/lambda/learncloud-video-relay | outbox retry relay |
| /aws/lambda/learncloud-video-recovery | execution failure/timeout/abort recovery |

Step Functions: logging ERROR, **Include execution data OFF**. Lịch sử execution
vẫn có input/output, chỉ cấp GetExecutionHistory cho người vận hành cần thiết.
Lambda: log level INFO nếu muốn thấy `video_job_submitted` chứa run ID/job ID an toàn;
không bật botocore/SQLAlchemy DEBUG. Runtime tự ghi RequestId, REPORT, duration.

Theo dõi RUNNING, SUCCEEDED, FAILED, TIMED_OUT, ABORTED. SUCCEEDED ở
VideoReadyAIPending chỉ hoàn tất video, không có AI hay quyền publish. DuplicateIgnored
cũng SUCCEEDED nhưng không tạo job. Đối chiếu ledger/processing-status trước kết luận.

Tìm MediaConvert lỗi: đọc `video_job_submitted`, hoặc SELECT run ID/job ID từ ledger;
MediaConvert → Jobs → tìm Job ID → xem Error code/Message và input/output. MediaConvert
không được bản này cấu hình tự đẩy toàn bộ job log vào một log group riêng. Job chưa có ID
và state SUBMITTING/FAILED safe_to_retry=false cần đối soát, không submit mù.

Log Insights (chọn log group pipeline, khoảng thời gian nhỏ):

```text
fields @timestamp, @message
| filter @message like /video_job_submitted|video_pipeline_failed|pipeline_operation_failed/
| sort @timestamp desc
| limit 100
```

Thêm run ID cố định vào filter khi điều tra. Execution graph cho biết task RetryAttempt,
TaskScheduled/TaskFailed và số lượt PollMediaConvert; không suy số retry từ retry_count:
retry_count là lượt người dùng retry lesson, khác retry lỗi task và lượt poll.

Alarm gợi ý, tạo qua CloudWatch → Alarms → Create alarm → Select metric:

| Namespace / metric | Dimension | Điều kiện lab ban đầu |
| --- | --- | --- |
| AWS/States ExecutionsFailed, ExecutionsTimedOut, ExecutionsAborted | StateMachineArn | Sum >= 1 / 5 phút, 1 datapoint |
| AWS/Lambda Errors, Throttles | FunctionName, cả 3 functions | Sum >= 1 / 5 phút |
| AWS/Lambda Duration | FunctionName | p95 > 80% timeout, 2/2 datapoints |
| AWS/Events FailedInvocations | RuleName (nếu có dimension trong Console) | Sum >= 1 / 5 phút |

Treat missing data = not breaching cho metric phát sinh thưa. SNS email notification
cần chính người dùng tạo topic/subscription và bấm xác nhận email. Không có alarm nào
đã được tạo. Nếu metric chưa xuất hiện, chạy test thủ công trước hoặc dùng metric filter
`"video_pipeline_failed"` → namespace LearnCloud/Video → PipelineFailures → alarm Sum >=1.
Đây là cấu hình đề xuất, code chưa phát custom metric hoặc dashboard backlog tự động.

IAM AccessDenied: tách role Lambda (CreateJob/PassRole/HEAD) với role MediaConvert
(GetObject raw/PutObject processed). Timeout: kiểm tra VPC egress, DNS, DB và job đang
PROGRESSING. Missing object: kiểm tra đúng bucket/region/key/ETag và output basename;
HEAD 403 có thể che object không tồn tại khi thiếu ListBucket, không coi mọi 403 là NoSuchKey.
DB connection failed: localhost trong Lambda không phải máy Docker của bạn.

FAILED: sửa nguyên nhân → đối soát job còn chạy/chưa rõ → reconcile khi cần → API retry.
RecordFailure không tự publish. Nếu recovery rule thất bại hoặc status event bị mất
(best effort), so execution thực tế với ledger rồi invoke recovery thủ công bằng event
trạng thái terminal đã xác minh; không dùng fake event để hạ lesson đang chạy.

Không ghi secret, access key, session token, JWT, DATABASE_URL/password, Presigned URL,
Authorization, request/response body, transcript, prompt/đáp án AI hoặc PII. Không paste
execution input/output đầy đủ vào ticket công khai. Khóa quyền xem Lambda env/logs.

Kiểm soát phí: 7 ngày lab / 14–30 ngày theo nhu cầu thật, tắt DEBUG, ERROR thay ALL,
không log từng nội dung video, giới hạn query time range, theo dõi Billing/Budgets.
Xóa log groups chỉ sau lưu bằng chứng cần thiết; xem
[cleanup lịch sử](../../docs/archive/aws/video-pipeline-console-setup.md#phan-10--cleanup).
