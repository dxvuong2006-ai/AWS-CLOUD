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
# IAM templates — chưa áp dụng

**MANUAL AWS CONSOLE STEP:** thay placeholders trên bản sao, dùng IAM JSON editor;
không commit account/role thật vào template. Tạo log groups trước vì không cấp quyền
tạo log group tự động. Không dùng AdministratorAccess.

| Role gợi ý | Trust JSON | Permission JSON |
| --- | --- | --- |
| LearnCloudVideoMediaConvertRole | mediaconvert-trust.json | mediaconvert-permissions.json |
| LearnCloudVideoPipelineLambdaRole | lambda-trust.json | lambda-pipeline-permissions.json |
| LearnCloudVideoRelayLambdaRole | lambda-trust.json | lambda-relay-permissions.json |
| LearnCloudVideoRecoveryLambdaRole | lambda-trust.json | lambda-recovery-permissions.json |
| LearnCloudVideoStateMachineRole | step-functions-trust.json | step-functions-permissions.json |
| LearnCloudVideoEventBridgeRole | eventbridge-trust.json | eventbridge-permissions.json |

Nếu Lambda trong VPC, bổ sung lambda-vpc-permissions.json cho từng Lambda cần kết nối
DB. Resource `*` ở các API network/log-delivery là giới hạn phân quyền của các API
liên quan; không có s3:*, iam:* hoặc states:* rộng toàn account. Runtime không cần
CreateStateMachine/UpdateFunctionCode/IAM management hoặc S3 DeleteObject.

Placeholders: ACCOUNT_ID (12 số), MEDIACONVERT_QUEUE_NAME (ví dụ Default),
MEDIACONVERT_ROLE_ARN, PIPELINE_LAMBDA_ARN, AI_WORKER_ARN, STATE_MACHINE_ARN.
Bus khác default phải sửa policy relay và rules cùng lúc. Chọn queue on-demand đã có;
MEDIACONVERT_QUEUE_ARN phải trùng queue được phép trong policy và trust MC.

Policy backend Presigned PUT/GET hiện có được giữ nguyên: khi bật pipeline cần
PutObject raw, GetObject raw/processed theo API hiện hành; backend không cần
StartExecution/PutEvents nhờ outbox. DB application user cần SELECT/INSERT/UPDATE
hai bảng ledger, không cần CREATE/DROP. DB grants do người quản trị DB duyệt riêng.

Mẫu dùng S3 SSE-S3. Nếu bucket dùng customer-managed SSE-KMS, phải bổ sung quyền
Decrypt/GenerateDataKey đúng key và key policy cho các role tương ứng trước khi chạy;
không tự đổi encryption của bucket đang hoạt động để né lỗi quyền.

Lambda invocation từ EventBridge cần resource-based permission đúng rule ARN;
Console thường thêm khi gắn trigger. Người thao tác cần iam:PassRole đúng role và
service, không phải quyền PassRole toàn account. C cần role riêng cho Transcribe/
Bedrock, chưa thuộc policy video này.

Thao tác chi tiết, ARN và kiểm tra quyền:
[phần IAM trong hướng dẫn](../../docs/aws-video-pipeline-console-setup.md#phan-2--iam-roles-va-policies).
