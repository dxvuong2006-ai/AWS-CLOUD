# API Gateway

## 1. Mục tiêu

Tạo một API Gateway để cung cấp HTTP endpoint có thể gọi từ trình duyệt hoặc Postman.

## 2. Tạo API Gateway

1. Truy cập [AWS API Gateway Console](https://ap-southeast-2.console.aws.amazon.com/apigateway/home?region=ap-southeast-2).
2. Chọn **Create API** → **HTTP API** → **Build**.
3. Cấu hình API:
   - API name: `learncloud-api`
   - IP address type: `IPv4`
4. Thêm integration:
   - Integration type: Lambda
   - Region: `ap-southeast-2`
   - Lambda function: `learncloud-hello`
5. Tạo route:
   - Method: `GET`
   - Resource path: `/hello`
   - Integration target: `learncloud-hello`
6. Tạo stage `$default` và bật **Auto-deploy**.
7. Kiểm tra cấu hình rồi chọn **Create**.

## 3. Kiểm tra API Endpoint

Sau khi tạo API, lấy **Invoke URL** trong API Gateway và thêm `/hello` vào cuối URL.

Ví dụ:

```text
https://fq5w2z5s66.execute-api.ap-southeast-2.amazonaws.com/hello
```

Mở URL trên trình duyệt hoặc gọi bằng Postman.

Kết quả mong đợi:

```json
{"message": "Hello from LearnCloud"}
```

## 4. Lưu ý

- API hiện tại dùng để thử nghiệm tích hợp API Gateway với Lambda, chưa phải API nghiệp vụ của LearnCloud.
- Route chưa được cấu hình xác thực nên có thể cho phép truy cập công khai.
- Không lưu AWS Access Key, Secret Key hoặc thông tin nhạy cảm vào GitHub.
- Kiểm tra và xóa tài nguyên AWS không còn sử dụng để hạn chế chi phí phát sinh.