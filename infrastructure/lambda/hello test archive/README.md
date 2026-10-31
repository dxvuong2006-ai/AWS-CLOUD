# AWS Lambda

## 1. Mục tiêu

Tạo một AWS Lambda function trả về JSON để sử dụng API Gateway

## 2. Tạo Lambda Function

1. Truy cập [AWS Lambda Console](https://console.aws.amazon.com/lambda/home).
2. Chọn **Create function** → **Author from scratch**.
3. Cấu hình:
   - Function name: `learncloud-hello`
   - Runtime: `Python 3.12`
   - Permissions: tạo execution role cơ bản với quyền ghi CloudWatch Logs.
4. Nhấn **Create function**.

## 3. Viết Lambda Handler

Mở learncloud-hello. Trong phần **Code source** (phần mà giao diện giống vscode), mở file `lambda_function.py` và thay nội dung bằng:

```python
import json

def lambda_handler(event, context):
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps({
            "message": "Hello from LearnCloud"
        })
    }
```

Nhấn **Deploy** để lưu code.

## 4. Kiểm tra Lambda

1. Chọn **Test**.
2. Tạo test event tên `test-hello`.
3. Sử dụng JSON event:

```json
{}
```

4. Nhấn **Test**.

Kết quả mong đợi: `Status: Succeeded`, response có `statusCode: 200` và thông báo `Hello from LearnCloud`.
# Lambda video pipeline

`video_pipeline_handler.py` được đóng gói ở ZIP root cùng `app/` và dependencies Linux.
Không tạo client AWS hoặc kết nối DB ở import. Tất cả handlers chặn khi
VIDEO_PIPELINE_ENABLED=false; không có URL/API public cho các Lambda nội bộ.

| Function | Handler | Nhiệm vụ |
| --- | --- | --- |
| learncloud-video-pipeline | video_pipeline_handler.handler | claim/submit/poll/verify/finalize_ai/fail; reconcile do operator gọi |
| learncloud-video-relay | video_pipeline_handler.relay_handler | đọc QUEUED outbox, PutEvents retry; không StartExecution |
| learncloud-video-recovery | video_pipeline_handler.recovery_handler | ghi FAILED cho owner của execution terminal |

Services/repositories trong backend là nơi cập nhật DB; handler chỉ điều phối và
sanitize exceptions. Migration 0005 chỉ là file chuẩn bị, không tự chạy khi boot.

Runtime Python 3.12, x86_64, 256 MB; pipeline timeout 45s, relay 60s, recovery 30s.
Step Functions invoke timeout 60s, submit không Retry. Poll 30s/lần, tối đa 120 lần.
Reserved concurrency lab: pipeline 2, relay 1, recovery 1 nếu quota cho phép; không
đặt concurrency=0. Giới hạn pool DB/đồng thời theo capacity DB trước production.

Package source bằng `backend/scripts/build_video_pipeline_package.py` sau khi chuẩn bị
dependencies Linux. Không dùng `.venv` Windows hay copy code dài vào Console.
Environment, packaging, VPC, IAM và thao tác upload ZIP:
[hướng dẫn Console](../../docs/aws-video-pipeline-console-setup.md#phan-4--lambda).

Điểm C: worker nhận `{run_id, execution_arn}`, xác minh ownership/attempt, tạo và lưu
transcript/summary/concepts (và quiz/flashcard theo contract C), trả
`{run_id, completed: true}` chỉ khi toàn bộ output thật đã lưu. Worker phải idempotent,
không tự approve/publish, không gọi mock. `finalize_ai` còn kiểm tra lại DB và ownership.
AI tắt mặc định; synchronous worker có giới hạn timeout 900s. Nếu C cần workflow dài hơn,
phải đổi seam thành nested workflow hỗ trợ trước khi bật, không trả completed sớm.
