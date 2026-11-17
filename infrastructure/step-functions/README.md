# Video pipeline

`video_pipeline.asl.json` dùng **Standard**, JSONPath, Lambda optimized integration
`arn:aws:states:::lambda:invoke`. Thay `${PIPELINE_LAMBDA_ARN}` và `${AI_WORKER_ARN}`
trên bản sao trước khi import. Khi AI tắt, ARN AI có thể tạm trỏ tới cùng pipeline
Lambda (nhánh này không được gọi); tuyệt đối không bật AI trước khi C tích hợp.

Luồng: claim upload → PROCESSING → submit một lần → Wait 30 giây/GetJob tối đa
120 lượt → yêu cầu job COMPLETE và HEAD output không rỗng → lưu processed key →
AI tùy chọn → kiểm tra completion proof và dữ liệu DB → REVIEW_REQUIRED.
AI worker riêng chạy ba action: start Transcribe xác định theo run_id, poll qua Wait
state, rồi đọc transcript và sinh/lưu draft bằng Bedrock. Worker không tự finalize,
approve hoặc publish; pipeline Lambda vẫn là nơi duy nhất chuyển sang REVIEW_REQUIRED.
Không có đường tự approve/publish. Khi AI tắt: execution SUCCEEDED nhưng ledger
VIDEO_READY, Lesson PROCESSING; chưa phải toàn bộ pipeline học liệu thành công.

AWS có hỗ trợ [MediaConvert `.sync`](https://docs.aws.amazon.com/step-functions/latest/dg/connect-mediaconvert.html).
Bản này chọn Lambda + GetJob để lưu job ID và kiểm soát submit chưa rõ kết quả.
[ClientRequestToken chỉ chống trùng trong một phút](https://docs.aws.amazon.com/mediaconvert/latest/apireference/idempotency.html);
ledger SUBMITTING được commit trước lời gọi. Không tự submit lại sau timeout.

Mỗi run ràng buộc upload UUID + retry_count và owner execution ARN. Khóa PostgreSQL
theo thứ tự Course → Lesson; UNIQUE(upload_id, attempt) bảo vệ claim bền vững.
Duplicate execution có thể tồn tại vì EventBridge StartExecution đặt tên khác nhau,
nhưng chỉ execution sở hữu run được xử lý. Giữ ledger để không mất bằng chứng dedupe.

Task timeout/Catch ghi FAILED; timeout toàn execution 7200 giây hoặc StopExecution
cần `recovery_handler`, rule execution-failure và audit thủ công nếu sự kiện bị mất.
[Sự kiện trạng thái Standard có cơ chế best effort](https://docs.aws.amazon.com/step-functions/latest/dg/eventbridge-integration.html).
Không dùng Console Redrive: có thể quay lại state submit mà không đi qua claim mới.
Dùng API retry sau đối soát job cũ; outbox chạy lại bằng event mới, output attempt mới.

`sample-upload-input.json` chỉ minh họa. Phải thay lesson/key/ETag bằng upload intent
và object thật; input mẫu không tạo dữ liệu DB, không xác nhận một upload tùy ý.

**MANUAL AWS CONSOLE STEP:** import, validate, cấu hình logging và chạy thử theo
[hướng dẫn tiếng Việt lưu trữ](../../docs/archive/aws/video-pipeline-console-setup.md).
Local tests kiểm tra JSON, graph, payload SDK và guards; chưa phải AWS ASL validation.
