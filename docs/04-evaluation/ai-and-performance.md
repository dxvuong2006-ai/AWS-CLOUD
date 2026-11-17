# Đánh giá AI và hiệu năng

## Pipeline video

| Mẫu | Dung lượng / thời lượng video | MediaConvert | Bedrock | Tổng tới `REVIEW_REQUIRED` | Trạng thái |
|---|---|---:|---:|---:|---|
| Video 1 | 14,6 MB / 6 phút 23 giây | 1 phút 19 giây | 32 giây | 1 phút 51 giây | `REVIEW_REQUIRED` |
| Video 2 | 18,2 MB / 7 phút 15 giây | 1 phút 34 giây | 38 giây | 2 phút 12 giây | `REVIEW_REQUIRED` |
| Video 3 | 12,8 MB / 4 phút 48 giây | 1 phút 8 giây | 29 giây | 1 phút 38 giây | `REVIEW_REQUIRED` |

Phương pháp được báo cáo: ghi thời điểm bắt đầu/kết thúc từng bước và tổng thời gian tới trạng thái review. Bảng PDF chỉ tách cột MediaConvert và Bedrock, không có thời gian Transcribe riêng, thời gian queue/cold start, retry, Region/account, model/version hay log id. Vì vậy:

- Không suy ra SLA, throughput hay tỷ lệ thời gian/video.
- Không khẳng định “nhanh hơn thời lượng video” trong mọi trường hợp.
- Không dùng ba mẫu để dự báo chi phí hoặc tải production.
- Muốn đo lại phải lưu timestamp chuẩn từ Step Functions/CloudWatch cho MediaConvert, Transcribe, AI worker, DB finalize và queue/cold-start.

## Chất lượng transcript và học liệu AI theo báo cáo

| Chỉ số | Thang/cỡ mẫu | Kết quả PDF | Hạn chế/diễn giải |
|---|---|---:|---|
| Độ đúng summary + key concepts | 1–5; 5 video | 4,2/5 trung bình | Không ghi số người chấm, độ đồng thuận hay rubric chi tiết cho từng mức |
| Mốc nguồn quiz khớp nội dung | 20 câu từ 5 video | 18/20 (90%) | Hai mốc bắt đầu quá sớm và được chỉnh; chưa có dataset để tái kiểm |
| JSON hợp lệ | 5 summary + 20 quiz output | 25/25 (100%) | Báo cáo nói một output ban đầu thiếu trường rồi được bổ sung/xác thực lại; cần phân biệt first-pass với after-fix |
| Mức chỉnh sửa | 5 summary + 5 bộ concepts + 20 câu quiz | 6/30 mục (20%) | Chủ yếu thuật ngữ và phương án nhiễu; chưa có phân loại severity |
| Transcript WER | 5 video có transcript chuẩn | 8,7% | Không có transcript chuẩn, quy tắc normalization/tokenization hay WER từng video trong repo |
| Tutor liên quan câu sai | 1–5; 10 phản hồi | 4,1/5 trung bình | Không ghi người chấm/blinding/inter-rater; một phản hồi còn chung chung |

### Cách hiểu WER

WER thường được tính bằng `(substitutions + deletions + insertions) / số từ tham chiếu`. Để tái hiện phải chốt:

- transcript tham chiếu do ai tạo/duyệt;
- cách viết hoa, dấu câu, số, từ viết tắt và tên dịch vụ AWS;
- đơn vị token/từ cho tiếng Việt;
- macro average hay gộp toàn corpus;
- model/language code và audio đầu vào.

PDF nêu lỗi thường gặp ở tên dịch vụ AWS và từ viết tắt, đồng thời đề xuất chuẩn hóa từ điển thuật ngữ. Với thông tin hiện có, chỉ có thể ghi “WER 8,7% trên 5 video theo báo cáo”, không thể xem là chất lượng tổng quát.


## Thời gian phản hồi API

| Endpoint | Thời gian ghi trong PDF |
|---|---:|
| `GET /courses` | 1,16 giây |
| `GET /lessons/{id}` | 3,2 giây |
| `POST /quizzes/{id}/attempts` | 2,1 giây |

Phần văn bản PDF nói dùng số request/mức đồng thời cố định và báo trung bình, p95, tỷ lệ lỗi, nhưng bảng chỉ có **một giá trị** cho mỗi endpoint và không ghi:

- giá trị đó là mean, median hay p95;
- số request, concurrency, warm-up/cold start;
- client location, network, AWS/local, cache và database size;
- error rate, payload, auth path và phiên bản artifact.

Vì thiếu các trường trên, bảng chỉ là quan sát lịch sử, không phải benchmark có thể so sánh. Không dùng nó để đặt SLO hoặc tuyên bố hiệu năng production.

## Thiết kế phép đo lại

### API

1. Chọn commit/artifact, môi trường test, database snapshot và ba role/fixture cố định.
2. Đo riêng cold/warm Lambda; ghi payload size và endpoint authorization path.
3. Chạy warm-up, sau đó nhiều mức concurrency với thời lượng đủ dài.
4. Báo request count, success/error theo status, mean, median, p90, p95, p99 và throughput.
5. Gắn CloudWatch/X-Ray hoặc request id đã làm sạch để tách API Gateway, Lambda, DB và external service.

### Pipeline

1. Lập corpus video theo ngôn ngữ, độ dài, codec, âm thanh và nhiễu; lưu hash thay vì dữ liệu nhạy cảm trong report công khai.
2. Đo queue, MediaConvert, Transcribe, AI generation, validation/finalize và tổng end-to-end.
3. Ghi success, retry, failure category, duplicate event và chi phí trên từng mẫu.
4. Tính WER bằng script/version normalization cố định; lưu transcript chuẩn trong kho dữ liệu riêng có quyền truy cập.
5. Chấm AI theo rubric nhiều người chấm, báo inter-rater agreement và first-pass/after-review riêng.

