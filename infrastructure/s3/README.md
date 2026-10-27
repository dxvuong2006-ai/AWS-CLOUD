# Amazon S3 Storage

## 1. Overview

LearnCloud sử dụng Amazon S3 để lưu trữ video bài học. Trong giai đoạn phát triển, FastAPI chạy local và tạo Presigned URL để client upload video trực tiếp lên S3.

## 2. S3 Configuration

| Property | Value |
|---|---|
| Bucket | `learncloud-videos-mentorcloud` |
| Region | `ap-southeast-1` |
| Block Public Access | Enabled |
| Object Ownership | Bucket owner enforced |
| Encryption | SSE-S3 |
| Versioning | Disabled |

## 3. Object Key Convention

Video gốc được lưu theo cấu trúc:

`lessons/{lesson_id}/raw/{uuid}.{extension}`

Ví dụ:

`lessons/1/raw/example.mp4`

## 4. Upload Flow

1. Instructor gửi `POST /lessons/{lesson_id}/upload-url`.
2. FastAPI kiểm tra lesson và quyền instructor.
3. S3 Storage Adapter tạo Presigned PUT URL bằng boto3.
4. API trả về `upload_url`, `object_key`, `expires_in`, `method` và `content_type`.
5. Client gửi HTTP PUT trực tiếp lên Amazon S3.

Video không được truyền qua FastAPI.

## 5. Local Configuration

Yêu cầu: Python, boto3, AWS CLI và IAM credentials hợp lệ.

```powershell
aws configure --profile learncloud
$env:AWS_PROFILE="learncloud"
$env:AWS_DEFAULT_REGION="ap-southeast-1"
```

Không lưu AWS Access Key và Secret Access Key trong source code.

## 6. CORS Configuration

Các origin local được cho phép:

- `http://localhost:5173`
- `http://127.0.0.1:5173`

Cho phép `PUT`, `GET`, `HEAD`; frontend upload bằng Presigned URL.

CORS không thay thế IAM hoặc bucket policy.

## 7. Testing

Đã kiểm thử các bước:

- AWS CLI xác thực thành công với IAM User.
- AWS CLI upload file thử lên S3 thành công.
- FastAPI sinh Presigned URL thành công.
- PowerShell gửi HTTP PUT qua Presigned URL thành công.
- Object xuất hiện trong S3 Console.

File video giả chỉ dùng để kiểm thử HTTP upload, không phải video hợp lệ để xử lý hoặc phát.

## 8. Limitations / Next Steps

- Chưa triển khai endpoint xác nhận upload và lưu `raw_video_key` vào PostgreSQL.
- Chưa tích hợp giao diện upload video của React.
- Chưa triển khai pipeline Transcribe/MediaConvert.
- Xác thực `X-Demo-User` hiện chỉ dành cho local development; cần thay bằng cơ chế xác thực thực tế.
- Kiểm thử Signature V4 và browser CORS trước khi tích hợp frontend.

## 9. Cleanup

Sau thử nghiệm, xóa các object test không cần thiết trong S3 Console. Không xóa bucket khi LearnCloud vẫn đang sử dụng.

Theo dõi chi phí AWS thường xuyên và kiểm tra các tài nguyên không còn dùng.