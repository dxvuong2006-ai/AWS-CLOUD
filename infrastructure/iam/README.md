# AWS IAM Configuration

## 1. Mục đích

Tài liệu mô tả cấu hình IAM cho FastAPI local khi sử dụng Amazon S3.

## 2. IAM Identity

- IAM User: `learncloud-backend-dev`
- AWS CLI Profile: `learncloud`
- Region: `ap-southeast-1`

IAM User được dùng trong môi trường phát triển local. Khi triển khai backend lên AWS Lambda, dự kiến chuyển sang IAM Execution Role thay vì sử dụng Access Key dài hạn.

## 3. IAM Policy

Policy đề xuất: `LearnCloudS3VideoPolicy`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "LearnCloudS3LessonVideos",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::learncloud-videos-mentorcloud/lessons/*"
    }
  ]
}
```

Policy sử dụng nguyên tắc least privilege, chỉ cấp các quyền cần thiết cho object thuộc prefix `lessons/`.

## 4. AWS CLI Setup

Cài AWS CLI trên Windows.

```powershell
aws configure --profile learncloud
```

Kiểm tra danh tính:

```powershell
aws sts get-caller-identity --profile learncloud
```

Kết quả cần cho thấy IAM User `learncloud-backend-dev`.

## 5. FastAPI Integration

Trong terminal chạy FastAPI:

```powershell
$env:AWS_PROFILE="learncloud"
$env:AWS_DEFAULT_REGION="ap-southeast-1"
```

Thư viện boto3 sử dụng AWS credential provider chain. Không hardcode Access Key trong backend.

## 6. Security

- Không commit `.env`, AWS Access Key hoặc Secret Access Key.
- Không chia sẻ Presigned URL còn hiệu lực.
- Giữ S3 Block Public Access.
- Không cấp quyền `s3:*` khi không cần thiết.
- Sử dụng AWS Signature Version 4.
- Định kỳ kiểm tra và thu hồi các access key không còn sử dụng.
- Thay cơ chế xác thực demo bằng JWT/Cognito trước khi triển khai công khai.

## 7. Verification

Đã xác minh:

- AWS CLI xác thực thành công.
- boto3 nhận đúng IAM identity.
- Upload thử object lên S3 thành công.
- FastAPI sinh Presigned URL.
- Upload qua Presigned URL thành công.

## 8. Cleanup

Khi không còn cần môi trường dev:

1. Vô hiệu hóa hoặc xóa Access Key.
2. Gỡ IAM Policy khỏi IAM User nếu không còn sử dụng.
3. Xóa IAM User nếu không còn cần.
4. Kiểm tra tài nguyên S3 và AWS Billing.

Chỉ thực hiện những bước này sau khi xác nhận không còn ứng dụng nào phụ thuộc vào IAM User.