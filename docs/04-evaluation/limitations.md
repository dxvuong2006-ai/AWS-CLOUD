# Giới hạn và hướng phát triển

Tài liệu này phân biệt phần cố ý nằm ngoài MVP với khoảng trống kỹ thuật, rủi ro chưa kiểm chứng và open issue có bằng chứng. “Chưa xác minh” không tự động là bug; ngược lại, source tồn tại không tự động là chức năng production-ready.

## Ngoài phạm vi MVP

Các mục sau không phải lỗi của phạm vi đã chốt trong báo cáo:

- Thanh toán, subscription, marketplace hoặc chứng chỉ trả phí. Enrollment chỉ là ghi danh.
- Livestream, lớp học đồng bộ, ứng dụng mobile native và social/community features.
- DRM/chống tải xuống tuyệt đối; URL có hạn chỉ giảm chia sẻ lâu dài.
- Adaptive learning cá nhân hóa hoàn chỉnh; ngưỡng checkpoint 50/80 là luật cố định.
- Chatbot đa dụng hoặc RAG trên nhiều nguồn; Tutor chỉ bám học liệu/câu sai của section.
- Multi-region, high availability/DR toàn diện và cam kết SLA production.
- Nhiều profile bitrate/độ phân giải; báo cáo mô tả đầu ra 720p duy nhất.

## Giới hạn chức năng hiện hữu

| Giới hạn | Bằng chứng | Tác động | Hướng xử lý |
|---|---|---|---|
| Ngưỡng completion video là `0.1` | `backend/app/services/progress_service.py` | Có thể đánh dấu hoàn thành sau 10% thời lượng; không phù hợp mặc định sản phẩm | Chốt yêu cầu, đưa thành cấu hình/server policy, backfill/test trigger |
| Checkpoint 50/80 cố định | Source và báo cáo | Dễ giải thích/test nhưng không thích ứng người học | Thu thập dữ liệu, thử nghiệm policy có version; không tự đổi theo client |
| Video một output MP4/720p theo thiết kế | PDF/ASL/adapter | Không thích nghi băng thông/thiết bị; không DRM | HLS/multi-bitrate sau khi đo nhu cầu/chi phí, signed cookies/URL phù hợp |
| AI luôn cần review | Báo cáo + review gate | Tăng thời gian Instructor | Cải thiện rubric/prompt, confidence và diff UI; không bỏ review chỉ để nhanh |
| Tutor có fallback local | Source | Demo/test có output nhưng không chứng minh Bedrock | Hiển thị nguồn/mode trong telemetry nội bộ; E2E model riêng |
| Hai bề mặt review API | OpenAPI: `review-draft*` và `ai-content`/`approve` | Contract/UI bảo trì phức tạp, nguy cơ hành vi lệch | Chọn canonical flow, deprecate có version và migration client |
| Nhiều response chưa có schema cụ thể | OpenAPI ghi JSON object | Client/generator khó ổn định | Bổ sung Pydantic response model và error schema |
| Admin monitoring ở mức job/app | Source | Không thay CloudWatch operational visibility | Tách quyền vận hành; thêm read-only aggregated metrics nếu cần |

## Khoảng chưa xác minh

Các mục sau chưa có kiểm tra runtime mới trong lượt tài liệu:

- inventory và trạng thái CloudFront/S3 frontend, API Gateway/Lambda alias, Cognito pool/client/authorizer;
- RDS endpoint/schema/registry/constraints/runtime grants và dữ liệu hiện tại;
- bucket CORS/policy/encryption, presigned PUT/GET và range playback với object thật;
- EventBridge rule/target, Step Functions definition/version, MediaConvert/Transcribe/Bedrock execution;
- CloudWatch log groups, alarms, retention, dashboard, AWS Budgets và cost anomaly monitor;
- K4/K5 duplicate/retry/stale callback trên PostgreSQL/AWS thật;
- Guardrails, model/profile/quota và giới hạn lượt Tutor hằng ngày;
- browser E2E và PostgreSQL-gated suites trong môi trường test cô lập.


## Open issue và rủi ro kỹ thuật

### Migration/schema phân nhánh

Repository có nhiều file version `0004` và chuỗi lịch sử `V1__`–`V3__`, trong khi bootstrap, models và từng database có thể khác nhau. Đây là rủi ro operator có thật: chạy migration theo glob có thể áp nhánh sai. Giải pháp là registry/schema preflight, backup/restore rehearsal và reconciliation migration được review; không sửa registry bằng tay.

### Cognito và RDS không có transaction chung

Tạo/xác minh user có thể thành công ở Cognito nhưng thất bại khi ghi RDS. Source đã có fail-closed/reconciliation logic, nhưng provisioning idempotent trên PostgreSQL/AWS cần được chạy lại. Không liên kết account chỉ theo email và không suy role đặc quyền từ group không được đối soát.

### Exactly-once không tồn tại ở EventBridge/S3

Event có thể giao nhiều lần; submit external job có thể timeout sau khi dịch vụ đã nhận. Ledger, immutable upload, lock và stale callback guard giảm rủi ro nhưng không loại bỏ nhu cầu reconciliation. Không redrive mù qua MediaConvert submit hoặc xóa ledger để “thử lại sạch”.

### Dữ liệu đánh giá nhỏ

AI rubric chỉ 5 video/20 câu/10 Tutor responses; pipeline timing chỉ 3 video; API timing thiếu request count/concurrency/p95/error rate. Không đủ để kết luận khả năng mở rộng hoặc chất lượng theo môn/ngôn ngữ/âm thanh. Xem [AI và hiệu năng](ai-and-performance.md).

### Tài liệu lịch sử chứa identifier cũ

Các runbook cũ giữ tên tài nguyên/endpoint/ID theo thời điểm để bảo toàn hướng dẫn. Chúng không phải secret nhưng có thể lỗi thời và không nên dùng làm inventory. Trước khi công khai rộng, nhóm có thể thay identifier môi trường bằng placeholder nếu chính sách threat model yêu cầu; tuyệt đối không thêm credential/token/password.

## Ưu tiên phát triển

1. **P0 - Tính đúng và an toàn:** chốt completion threshold; đối soát migration/schema; chạy PostgreSQL auth/access/progress/quiz/pipeline gates trên DB test; secret scan; route × role matrix.
2. **P1 - Quan sát và rollout:** inventory AWS có ngày, non-production canary K4/K5, alarms/budget, playback/upload thật và rollback rehearsal.
3. **P1 - Contract:** canonical review API, response/error schemas đầy đủ, deprecation plan và OpenAPI contract tests.
4. **P2 - Chất lượng AI:** corpus/rubric lớn hơn, WER tái hiện được, inter-rater agreement, prompt/model versioning và Guardrails/quota verification.
5. **P2 - Hiệu năng/video:** benchmark có p95/error/throughput, multi-bitrate/HLS và CDN authorization theo dữ liệu thực.
6. **P3 - Sản phẩm:** chỉ xem adaptive threshold, DRM/mobile hoặc tính năng ngoài MVP sau khi luồng cốt lõi ổn định và có nhu cầu đo được.
