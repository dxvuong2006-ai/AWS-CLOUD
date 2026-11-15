# EventBridge — CODE READY / AWS NOT DEPLOYED

**MANUAL AWS CONSOLE STEP:** mọi rule/target/permission bên dưới do người dùng tạo.
Các file chứa `${ACCOUNT_ID}`, `${STATE_MACHINE_ARN}` phải được thay trên bản sao.

| Rule gợi ý | Pattern / schedule | Target / input |
| --- | --- | --- |
| learncloud-video-upload | `s3-object-created.pattern.json` | Standard Step Functions; `s3-input-transformer.json` |
| learncloud-video-retry | `retry.pattern.json` | Cùng State Machine; InputPath `$.detail` |
| learncloud-video-recovery | `execution-failure.pattern.json` | Lambda recovery; toàn bộ matched event |
| learncloud-video-relay-tick | `rate(1 minute)` | Lambda relay; `{}` |

S3 bucket Properties → Amazon EventBridge → Edit → On. Chọn default event bus,
cùng region ap-southeast-1. Pattern lọc bucket `learncloud-videos-mentorcloud`,
Object Created, key `lessons/*/raw/*`; output nằm dưới `lessons/*/processed/*` nên
không kích hoạt lại. Pattern không xác thực lesson; Lambda còn kiểm tra canonical
key, UUID phiên upload đã cấp, kích thước, MIME, thời gian ghi và ETag từ HEAD.

Nguồn dispatch duy nhất là **EventBridge**. Upload mới đi từ S3; retry chủ động
đi từ outbox → relay PutEvents → rule retry → cùng workflow. Backend/confirm-upload
không gọi StartExecution. Không bật thêm trigger S3 Lambda hoặc dispatcher khác.

Source hiện không có `confirm-upload`. Khi opt-in, `upload-url` lưu upload intent
trước khi trả URL; object S3 hợp lệ chính là xác nhận upload. Vì intent commit trước
khi client có thể PUT, không còn race với confirm endpoint. DRAFT → PROCESSING chỉ
sau kiểm tra object, không giả lập UPLOADED. Nếu đội sau này thêm confirm-upload
bắt buộc, phải bổ sung trạng thái CONFIRMED + wait/reconciliation có hạn vào gate,
và giữ EventBridge là dispatcher; không chỉ gắn một endpoint rồi chạy hai pipeline.

Duplicate event/execution được xử lý bằng ledger PostgreSQL, không chỉ event ID
hoặc token MediaConvert. Relay giữ QUEUED và phát lại mỗi 2 phút cho đến lúc claim;
PutEvents thành công chưa chứng minh target đã nhận. API retry chỉ ghi outbox trong
cùng transaction tăng retry_count; rollback DB không để lại yêu cầu xử lý ngoài DB.

Role EventBridge dùng `eventbridge-trust.json` + `eventbridge-permissions.json`,
chỉ StartExecution đúng state machine. Target Lambda dùng resource-based permission
principal events.amazonaws.com, SourceArn chính xác rule; Console thêm khi tạo trigger.
Chỉ relay có PutEvents cho source/detail-type nội bộ; hạn chế người có StartExecution.

Target retry policy: tối đa tuổi event 24 giờ, tối đa 185 lần (có thể giảm theo lab).
Nên thêm SQS **Standard DLQ** cùng region để giữ failed deliveries; Console cần policy
SendMessage từ events.amazonaws.com giới hạn đúng rule ARN. DLQ là tài nguyên bổ sung,
không có trong code xử lý; người vận hành kiểm tra/redeliver thủ công sau sửa lỗi.

EventBridge Sandbox dùng `sample-s3-event.json` và pattern đã thay account. Test thêm
key processed (không match), bucket khác (không match), cùng raw event hai lần
(có thể có hai executions nhưng một run/job). Payload transformer phải có etag;
không dùng legacy S3 `Records[0]` hay URL-decode key của schema khác.

Xem [cấu trúc S3 event](https://docs.aws.amazon.com/AmazonS3/latest/userguide/ev-events.html),
[input transformer](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-transform-target-input.html)
và [hướng dẫn thao tác](../../docs/aws/video-pipeline-console-setup.md#phan-6--eventbridge).
