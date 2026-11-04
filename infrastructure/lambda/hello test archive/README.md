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

