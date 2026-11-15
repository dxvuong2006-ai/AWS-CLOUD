# Triển khai LearnCloud lên AWS theo kiến trúc K1–K6

Tài liệu này hướng dẫn dựng môi trường demo theo kiến trúc trong báo cáo tiến độ 2: S3/CloudFront/Cognito, API Gateway/Lambda, RDS PostgreSQL, S3 video, pipeline bất đồng bộ và Bedrock. Dùng một AWS account cho nhóm bốn người, nhưng mỗi người đăng nhập bằng danh tính riêng. Lambda được đóng gói dạng ZIP; không dùng Docker. Giữ môi trường trong 1–2 tuần để giảng viên kiểm tra.

> Các bước tạo dịch vụ AWS không tự bổ sung tính năng còn thiếu trong mã nguồn. Trước khi làm các mục được đánh dấu **Cần chuẩn bị mã**, hoàn thiện handler, auth và workflow theo mục 1. Môi trường HTTP/API công khai chỉ dùng dữ liệu demo; dự kiến có phí trong thời gian chạy.

## Kiến trúc cần tạo

```text
Người dùng → CloudFront → S3 (React)       Cognito cấp JWT
                         └─ video CDN ← S3 processed
Người dùng ── JWT ──→ API Gateway → Lambda (FastAPI/Mangum) → RDS PostgreSQL
                                      ├→ S3 raw/processed
                                      └→ Bedrock
Trình duyệt ── presigned PUT ──→ S3 raw → EventBridge → Step Functions
                                                      → MediaConvert → Transcribe
                                                      → Pipeline Lambda → Bedrock/RDS/S3
CloudWatch nhận logs/metrics; AWS Budgets cảnh báo chi phí
```

## 0. Chia quyền AWS cho bốn người

Chủ account thực hiện các thao tác IAM:

1. Đăng nhập root, mở **Security credentials**, bật MFA. Root chỉ dùng cho quản lý account.
2. Tìm **IAM Identity Center** → **Enable** nếu chưa bật.
3. **Users** → **Add user**, tạo bốn danh tính bằng email thành viên. Mỗi người tự đặt mật khẩu từ thư mời.
4. **Groups** → **Create group**, tạo `LearnCloud-Deployers`, `LearnCloud-Backend`, `LearnCloud-Frontend`, `LearnCloud-Reviewers`; thêm A, B, C, D theo thứ tự.
5. **Permission sets** → **Create permission set** → **Custom permission set**. Gắn AWS managed policies phù hợp:
   - `LearnCloud-Deploy`: `PowerUserAccess` (A tạo dịch vụ; không có quyền quản lý IAM/billing).
   - `LearnCloud-Backend`: `AWSLambda_FullAccess`, `AmazonAPIGatewayAdministrator`, `AmazonRDSReadOnlyAccess`, `AmazonS3ReadOnlyAccess`, `CloudWatchReadOnlyAccess`.
   - `LearnCloud-Frontend`: `AmazonS3FullAccess`, `CloudFrontFullAccess`, `AmazonCognitoPowerUser` (chỉ dùng trong account lab).
   - `LearnCloud-ReadOnly`: `ReadOnlyAccess`.
6. **AWS accounts** → chọn account → **Assign users or groups**. Gán từng group với permission set tương ứng.
7. Mỗi người vào AWS access portal, chọn cùng account và đúng permission set. Xác nhận account ID giống nhau, danh tính khác nhau.

Không dùng chung access key; không gắn `AdministratorAccess` cho cả nhóm. Chủ account/IAM administrator tạo execution roles ở các bước sau vì permission set của nhóm không quản lý IAM.

Trên máy người đóng gói, cần AWS CLI v2, Git, Python 3.12 và Node.js/npm. Không cần Docker. Mở PowerShell và đăng nhập CLI theo phần **Command line or programmatic access** trong AWS access portal:

```powershell
aws sso login --profile learncloud
aws sts get-caller-identity --profile learncloud
```

Xác nhận đúng account ID trước khi tạo tài nguyên. Region thống nhất toàn tài liệu là **Asia Pacific (Singapore) `ap-southeast-1`**.

## 1. Kiểm tra mã nguồn trước khi tạo AWS resources

Kiến trúc báo cáo là kiến trúc đích. Repository hiện có FastAPI, React/Vite, schema PostgreSQL, S3 adapter và một ASL placeholder rỗng; chưa có Lambda handler/Mangum, Cognito JWT integration hay workflow Step Functions hoàn chỉnh. Làm các việc sau trước khi kỳ vọng toàn hệ thống chạy:

1. **K2 – Lambda:** thêm `mangum` vào `backend/requirements.txt`; tạo `backend/app/lambda_handler.py`:

   ```python
   from mangum import Mangum
   from app.main import app

   handler = Mangum(app, lifespan="off")
   ```

   Cập nhật cấu hình backend để lấy database secret từ Secrets Manager hoặc SSM, thay vì yêu cầu `DATABASE_URL` dạng mật khẩu thuần trong Lambda environment.

2. **M1 – Cognito:** API Gateway JWT authorizer xác minh issuer, audience và thời hạn token. Cập nhật backend để đọc claims đã xác minh từ API Gateway request context, ánh xạ `sub` tới `users.cognito_sub`, rồi kiểm tra role, ownership, enrollment và unlock. Cập nhật `backend/app/config.py` để không còn bắt buộc `JWT_SECRET_KEY` khi Cognito là issuer. Không đưa `X-Demo-User` ra môi trường AWS.
3. **K1 – frontend:** đặt API base URL theo API Gateway; đăng nhập bằng Cognito OIDC/authorization code + PKCE; gửi `Authorization: Bearer <token>`.
4. **K3 – video:** triển khai signed URL cho video processed qua CloudFront; presigned upload chỉ ghi đúng prefix `lessons/{lesson_id}/raw/`.
5. **K4 – pipeline:** viết và kiểm tra state machine ASL cùng các Lambda/task handlers cho MediaConvert, Transcribe, Bedrock, update trạng thái RDS và ghi output S3. File `infrastructure/step-functions/video_pipeline.asl.json` hiện chưa có định nghĩa.
6. Tạo một **migration Lambda dùng một lần** chạy trong VPC để nạp `database/schema.sql`, rồi migration chưa áp dụng từ `database/migrations/`. RDS là private nên không chạy migration từ máy cá nhân. Xóa/quyền thu hồi handler migration sau khi xác nhận schema.
7. Xác nhận adapter và dependencies chọn đúng AWS implementations; fixture/mock chỉ dùng khi chưa kết nối dịch vụ thật.

Nếu các việc trên chưa hoàn thành, chỉ có thể kiểm tra từng dịch vụ độc lập; không đánh dấu LearnCloud đã deploy hoàn chỉnh.

## 2. Tạo cảnh báo ngân sách trước

1. Mở **Billing and Cost Management** → **Budgets** → **Create budget**.
2. Chọn **Use a template (simplified)** → **Monthly cost budget**.
3. Đặt tên `learncloud-demo-budget`, nhập hạn mức nhóm được phép chi, ví dụ `20 USD` (đổi theo phê duyệt của nhóm).
4. Đặt cảnh báo email ở 50%, 80% và 100%; nhập email người theo dõi.
5. Chọn **Create budget**.

Budgets gửi cảnh báo, không tự dừng dịch vụ. Theo dõi chi phí hằng ngày trong suốt 1–2 tuần.

## 3. Tạo VPC, subnet và security groups

### 3.1 VPC

1. Console Region `ap-southeast-1` → tìm **VPC** → **Your VPCs** → **Create VPC**.
2. Chọn **VPC and more**; name `learncloud`; IPv4 CIDR `10.20.0.0/16`; IPv6 None; tenancy Default.
3. Chọn 2 AZ, 0 public subnet, 2 private subnets (một subnet ở mỗi AZ); NAT Gateway **None**; VPC endpoints **None**; bật DNS hostnames và DNS resolution.
4. CIDR hai subnet phải khác nhau và nằm trong `10.20.0.0/16`. Dùng cả hai private subnet cho Lambda và DB subnet group.
5. Xem Preview, chọn **Create VPC**, chờ hoàn tất. Ghi VPC ID và hai private subnet IDs.

Không đặt Lambda hoặc RDS vào public subnet. Không tạo NAT Gateway cho lab này. Các Lambda trong VPC cần VPC endpoints cho dịch vụ AWS mà chúng gọi; endpoints sẽ được tạo ở bước 3.3.

### 3.2 Security groups

Trong **VPC → Security groups → Create security group**, tạo:

| Name                   | Inbound                                            | Outbound                                                  |
| ---------------------- | -------------------------------------------------- | --------------------------------------------------------- |
| `learncloud-lambda-sg` | Không có inbound                                   | TCP 5432 tới `learncloud-rds-sg`; TCP 443 tới endpoint SG |
| `learncloud-rds-sg`    | PostgreSQL TCP 5432, source `learncloud-lambda-sg` | Mặc định                                                  |
| `learncloud-vpce-sg`   | HTTPS TCP 443, source `learncloud-lambda-sg`       | Mặc định                                                  |

Tạo tất cả trong VPC `learncloud`. Không thêm source `0.0.0.0/0` vào RDS.

### 3.3 VPC endpoints thay NAT

1. VPC → **Endpoints** → **Create endpoint**.
2. Tạo endpoint loại **AWS services** cho `com.amazonaws.ap-southeast-1.s3`, service category **Gateway**. Chọn VPC `learncloud` và route tables của app subnets. Endpoint policy phải cho phép bucket raw/processed của dự án.
3. Lặp lại loại **Interface** cho từng AWS API mà Lambda trong VPC gọi: `bedrock-runtime`, `secretsmanager`, `logs`; K4 pipeline Lambda cần thêm `mediaconvert` và `transcribe`. Nếu code gọi thêm dịch vụ AWS, tạo endpoint tương ứng hoặc thiết kế NAT có kiểm soát.
4. Với từng Interface endpoint: chọn VPC `learncloud`, hai app subnets (mỗi AZ một subnet), bật **Enable DNS name**, gắn `learncloud-vpce-sg`.
5. Chọn **Create endpoint** và đợi trạng thái `Available`.

Interface endpoints tính phí theo giờ/dữ liệu. Đếm endpoint thực sự cần dùng; không tạo Bedrock endpoint nếu chưa gọi Bedrock. Không tạo NAT Gateway trong cùng lúc chỉ để “thử”, vì sẽ phát sinh phí.

## 4. Tạo ba S3 buckets private

Tạo lần lượt bucket frontend, raw, processed trong Region Singapore. Mỗi tên bucket phải duy nhất toàn cầu, ví dụ `learncloud-web-<account-id>-<suffix>`, `learncloud-raw-...`, `learncloud-processed-...`.

Với từng bucket: **S3 → Create bucket**, giữ **Block all public access** bật, **Object Ownership: Bucket owner enforced**, mã hóa SSE-S3, rồi **Create bucket**.

### 4.1 CORS cho bucket raw

Raw bucket → **Permissions → CORS → Edit**. Sau khi có CloudFront domain, thay origin placeholder:

```json
[
  {
    "AllowedOrigins": ["https://<CLOUDFRONT_DOMAIN>"],
    "AllowedMethods": ["PUT", "HEAD"],
    "AllowedHeaders": ["Content-Type"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 300
  }
]
```

CORS chỉ cho phép trình duyệt gửi request từ origin web; quyền S3 vẫn do IAM/presigned URL quyết định. Object raw theo `lessons/{lesson_id}/raw/{random_id}.mp4`; processed dùng prefix tương ứng `lessons/{lesson_id}/processed/`.

## 5. Tạo Cognito User Pool

1. Mở **Amazon Cognito** → **User pools** → **Create user pool**.
2. Sign-in options chọn email; password policy để mặc định mạnh; bật MFA nếu phù hợp demo.
3. Tạo app client kiểu **Public client** cho SPA, không tạo client secret. Chọn authentication flow phù hợp với OIDC authorization code + PKCE.
4. Chưa thêm hosted domain/custom domain nếu dùng domain mặc định; hoàn tất **Create user pool**.
5. Trong User Pool → **App integration**, tạo domain Cognito và ghi lại **User pool ID**, **App client ID**, domain và issuer URL.
6. Tạo group `Instructor`, `Student`, `Admin` tại **Groups**. Tạo user demo tại **Users**, gán vào từng group; không cấp role tự chọn từ form đăng ký.
7. Ghi lại callback/logout URLs sau khi có CloudFront distribution; sửa App client để chỉ chấp nhận URLs thật của demo.

Cognito chỉ xác minh danh tính/token. Backend vẫn phải kiểm tra quyền sở hữu course, enrollment và unlock.

## 6. Tạo Secrets Manager secret và RDS PostgreSQL

### 6.1 Secret

1. Mở **Secrets Manager** → **Store a new secret** → loại **Other type of secret**. Thêm key/value `username` và `password` cho user ứng dụng.
2. Target runtime login `learncloud_app` is a recommended dedicated least-privilege role, not an existing RDS role confirmed in the current review. Do not assume it exists or create it as part of this migration. The current local Backend reads `learncloud_admin` from repository-root `.env`; provision a separate app role and rotate the runtime secret only through a separately reviewed DBA/deployment change.
3. Secret name `learncloud/prod/database` → lưu. Sau khi bootstrap user/grant trong database, bảo đảm username/password trong secret khớp thông tin user đó.

### 6.2 DB subnet group và database

1. RDS → **Subnet groups** → **Create DB subnet group**. Name `learncloud-db-subnets`, VPC `learncloud`, chọn hai AZ và cả hai private subnet đã tạo ở mục 3.
2. RDS → **Databases → Create database → Standard create → PostgreSQL**. Chọn version PostgreSQL 16 nếu có.
3. Identifier `learncloud-prod-db`; chọn lớp phù hợp ngân sách lab; bật encryption và automated backup theo thời hạn cần giữ.
4. Connectivity: VPC `learncloud`; DB subnet group `learncloud-db-subnets`; **Public access: No**; security group chỉ `learncloud-rds-sg`; port 5432.
5. Initial database name `learncloud`. Dùng credentials quản lý riêng; không đưa password vào tài liệu.
6. Chọn **Create database**, đợi **Available**, ghi endpoint/port.
7. Mở secret `learncloud/prod/database` → **Retrieve secret value → Edit**, cập nhật username/password khớp database ứng dụng. DB cần role/grant giới hạn quyền ứng dụng; master chỉ dùng để tạo user/schema.

## 7. Tạo IAM execution roles

IAM administrator tạo các role riêng. Không dùng một role quản trị chung cho mọi dịch vụ.

| Role                              | Trusted service | Quyền chính                                                                                                                               |
| --------------------------------- | --------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `learncloud-api-lambda-role`      | Lambda          | CloudWatch Logs; đọc secret DB; đọc/ghi đúng S3 prefix; quyền VPC network interface; invoke đúng Bedrock model nếu API Tutor chạy tại đây |
| `learncloud-pipeline-lambda-role` | Lambda          | Logs; đọc secret DB; đọc raw và ghi processed; gọi đúng Bedrock model                                                                     |
| `learncloud-statemachine-role`    | Step Functions  | Chỉ invoke Pipeline Lambda; quyền start/get job MediaConvert/Transcribe nếu state machine trực tiếp gọi các API đó                        |
| `learncloud-eventbridge-role`     | EventBridge     | Chỉ start đúng state machine                                                                                                              |
| `learncloud-mediaconvert-role`    | MediaConvert    | Đọc raw prefix, ghi processed prefix                                                                                                      |

Trong IAM → Roles → Create role, chọn đúng trusted service/use case; sau đó **Add permissions → Create inline policy → JSON** để giới hạn bucket ARN, secret ARN, function ARN, state machine ARN và Bedrock model ARN. Lambda roles cần `AWSLambdaVPCAccessExecutionRole` hoặc quyền tương đương để tạo network interfaces. Không gắn `AdministratorAccess`, `s3:*` hoặc `bedrock:*`.

ARN chứa account ID, Region và suffix secret do AWS tạo; lấy ARN từ trang resource rồi thay đúng vào policy. Sai ARN thường gây `AccessDenied` khi test.

## 8. Đóng gói FastAPI ZIP và tạo Lambda

### 8.1 Đóng gói không dùng Docker

Thực hiện trong **AWS CloudShell** (biểu tượng terminal trên AWS Console), để cài dependency theo Linux runtime của Lambda:

1. Chuẩn bị source backend đã push lên repository hoặc tải ZIP source không chứa `.env`, credentials, `.venv`, `__pycache__`.
2. CloudShell → tải source lên, giải nén vào thư mục làm việc. Xác nhận `requirements.txt` có `mangum` và có `app/lambda_handler.py` theo mục 1.
3. Xác nhận Lambda runtime là Python 3.12, architecture x86_64. Tạo package bằng wheel Linux tương thích (không cài package Windows trực tiếp vào ZIP):

```bash
mkdir -p package
python3 -m pip install --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --only-binary=:all: -r backend/requirements.txt -t package
cp -r backend/app package/app
cd package
zip -r ../learncloud-api.zip .
```

4. Upload `learncloud-api.zip` vào bucket deployment riêng, ví dụ `learncloud-artifacts-<account-id>` (private). Không dùng bucket video làm bucket artifact.

### 8.2 Tạo function

1. Lambda → **Functions → Create function → Author from scratch**.
2. Function name `learncloud-api-prod`; runtime Python 3.12; architecture x86_64; execution role `learncloud-api-lambda-role`.
3. Tạo function → **Code → Upload from → Amazon S3 location**, chọn artifact ZIP → Save.
4. **Runtime settings → Edit**: Handler `app.lambda_handler.handler`.
5. **Configuration → VPC → Edit**: chọn VPC `learncloud`, hai app subnets, security group `learncloud-lambda-sg`. Chờ trạng thái cập nhật hoàn tất.
6. **Configuration → Environment variables**: đặt `AWS_REGION`, tên bucket raw/processed và `DATABASE_SECRET_ARN`. Không dán password/JWT secret vào environment.
7. **Configuration → General configuration**: memory 1024 MB, timeout phù hợp request ngắn (ví dụ 30 giây). Video không đi qua Lambda; chỉ upload thẳng S3.
8. Tạo test event HTTP API và xác nhận `/health` trả `{"status":"ok"}`. Xem **Monitor → View CloudWatch logs** nếu lỗi.

Nếu package ZIP vượt giới hạn upload trực tiếp, dùng artifact bucket trong CloudShell rồi chọn source từ S3. Không dùng container image.

## 9. Tạo API Gateway và Cognito JWT authorizer

1. API Gateway → **Create API → HTTP API → Build**. API name `learncloud-api-prod`.
2. **Add integration** → Lambda `learncloud-api-prod`, Region `ap-southeast-1`.
3. Thêm routes `ANY /` và `ANY /{proxy+}`; gán Lambda integration.
4. **Authorization → Manage authorizers → Create**; type **JWT**; issuer URL là Cognito issuer; Audience là Cognito App client ID.
5. Gán authorizer cho route API nghiệp vụ. Chỉ `/health` có thể để public nếu thầy cần health check; các route nghiệp vụ phải yêu cầu JWT.
6. Stage `$default`, bật auto-deploy, tạo API. Ghi Invoke URL.
7. Kiểm tra không token → route nghiệp vụ trả 401; token hợp lệ vào backend để backend kiểm tra role/ownership/enrollment.
8. Cập nhật `VITE_API_URL` khi build frontend ở bước 10.

## 10. Tạo frontend S3 + CloudFront (K1)

### 10.1 Upload web build

1. Trên máy có source, đặt URL API Gateway và thông tin Cognito theo cấu hình frontend đã triển khai:

```powershell
cd frontend
$env:VITE_API_URL = "<API_GATEWAY_INVOKE_URL>"
npm.cmd install
npm.cmd run build
```

2. Build nằm trong `frontend/dist`. S3 → bucket frontend → **Upload** → **Add files/Add folder**, chọn tất cả nội dung bên trong `dist`, rồi **Upload**.
3. Không bật **Static website hosting** public; giữ Block Public Access.

### 10.2 CloudFront OAC

1. Mở **CloudFront → Distributions → Create distribution**.
2. Origin domain: chọn bucket frontend dạng S3 REST origin (không chọn website endpoint). Origin access: **Origin access control settings (recommended)** → Create new OAC → signing behavior **Sign requests**.
3. Viewer protocol policy **Redirect HTTP to HTTPS**; default root object `index.html`.
4. Tạo distribution. Sau khi tạo, mở distribution → origin → **Copy policy**/Update bucket policy; áp dụng policy được CloudFront đề xuất để chỉ distribution này đọc bucket.
5. Chọn SPA fallback: **Custom error responses**, HTTP 403 và 404 map tới `/index.html`, response code 200.
6. Chờ distribution **Deployed**. Ghi domain `dxxxxx.cloudfront.net`; cập nhật Cognito callback/logout URLs và CORS raw bucket dùng `https://<CLOUDFRONT_DOMAIN>`.
7. Mở domain HTTPS, kiểm tra frontend tải được. Sau lần upload build mới, **Invalidations → Create invalidation → `/*`**.

### 10.3 Video processed qua CloudFront signed URL

1. Trong AWS CloudShell tạo cặp khóa riêng cho CloudFront:

   ```bash
   openssl genrsa -out cloudfront-private.pem 2048
   openssl rsa -pubout -in cloudfront-private.pem -out cloudfront-public.pem
   ```

2. CloudFront → **Public keys** → **Create public key**. Name `learncloud-video-public-key`; mở `cloudfront-public.pem`, copy toàn bộ nội dung vào **Public key contents**, lưu.
3. CloudFront → **Key groups** → **Create key group**. Name `learncloud-video-key-group`; thêm public key vừa tạo → **Create key group**.
4. CloudFront → **Distributions** → chọn frontend distribution → **Origins → Create origin**. Chọn S3 processed bucket dạng REST origin; tạo OAC và để **Sign requests**. Cập nhật bucket policy để chỉ distribution này đọc bucket processed.
5. Tạo behavior cho path `lessons/*/processed/*` (hoặc path khớp key thực tế), chọn processed S3 origin, bật trusted authorization/signed URLs và chọn key group `learncloud-video-key-group`. Lưu thay đổi, đợi distribution **Deployed**.
6. Lưu `cloudfront-private.pem` dưới dạng secret trong Secrets Manager; xóa bản tạm khỏi CloudShell sau khi xác nhận secret đã lưu. Cấp quyền đọc secret này cho API Lambda role.
7. Backend cần được lập trình để chỉ sau khi kiểm tra enrollment, publish và unlock mới ký CloudFront URL có thời hạn. Kiểm thử URL đã ký truy cập được, URL không ký hoặc hết hạn bị từ chối.

Không bật public access hoặc trả URL S3 trực tiếp cho video học viên. Bước ký URL cần có trong backend trước khi luồng học video được nghiệm thu.

## 11. Tạo pipeline bất đồng bộ K4

**Chỉ thực hiện khi state machine ASL và handlers đã được viết, kiểm tra và đặt trong repository.** ASL hiện trống nên chưa thể tạo workflow chạy thật chỉ bằng Console.

1. Mở S3 raw bucket → **Properties** → **Amazon EventBridge** → bật **Send notifications to Amazon EventBridge** → Save changes. Xác nhận định nghĩa workflow dùng đúng resource ARN của MediaConvert, Transcribe, Pipeline Lambda và account Region.
2. Step Functions → **State machines → Create state machine** → **Write your workflow in code** → loại **Standard**. Dán nội dung ASL đã review; chọn `learncloud-statemachine-role`; tạo state machine.
3. Ghi State machine ARN. Test bằng object video ngắn trong bucket raw; xác nhận mỗi bước có trạng thái và error path.
4. EventBridge → **Rules → Create rule**. Name `learncloud-raw-video-created`; event bus default; rule type **Rule with an event pattern**.
5. Event pattern lọc `source: aws.s3`, `detail-type: Object Created`, đúng bucket raw và prefix/suffix video theo code (ví dụ `.mp4`). Chọn target Step Functions state machine vừa tạo và role `learncloud-eventbridge-role`.
6. Enable rule. Upload một tệp thử vào `lessons/<id>/raw/`; kiểm tra Step Functions execution và trạng thái lesson RDS.
7. Cấu hình trong workflow retry, timeout, Catch; chống chạy trùng theo `(lesson_id, object_key)`. Chỉ S3 Object Created khởi chạy workflow; không dùng confirm-upload làm trigger thứ hai.

MediaConvert và Transcribe phát sinh chi phí theo job/usage. Dùng một video ngắn để nghiệm thu, dọn output thử sau khi kiểm tra.

## 12. Bedrock K5

1. Mở **Amazon Bedrock** tại `ap-southeast-1` → **Model access**. Chọn model được phép dùng trong Region và hoàn tất yêu cầu access nếu Console hiện ra.
2. Ghi model ID chính xác; gắn `bedrock:InvokeModel`/`bedrock:Converse` chỉ cho model đó vào API Lambda role hoặc pipeline Lambda role tương ứng.
3. Nếu gọi từ Lambda trong VPC, xác nhận Interface endpoint `bedrock-runtime` ở trạng thái Available và endpoint SG nhận HTTPS từ Lambda SG.
4. Bật Guardrails cho Tutor theo cấu hình đã duyệt; giới hạn số lượt gọi/ngày. Không gửi tên/email học viên vào prompt; Tutor chỉ dùng attempt và học liệu đã duyệt.
5. Kiểm tra CloudWatch log không ghi prompt nhạy cảm, token, secret hay presigned URL.

## 13. CloudWatch K6 và theo dõi chi phí

1. CloudWatch → **Logs → Log groups**. Xác nhận log group Lambda API, Pipeline Lambda và Step Functions xuất hiện.
2. Chọn log group → **Actions → Edit retention**; đặt retention 7 hoặc 14 ngày cho demo.
3. CloudWatch → **Alarms → Create alarm**. Tạo alarm cho Lambda Errors/Throttles, API Gateway 5xx và Step Functions execution failures; gửi SNS email nếu nhóm đã cấu hình SNS topic.
4. Billing → **Budgets** kiểm tra budget và ngưỡng 50/80/100%. Kiểm tra thường xuyên trong 1–2 tuần.
5. Log chỉ ghi lesson_id, execution_id, bước xử lý, thời gian, status và lỗi đã làm sạch; không ghi PII, secret, JWT hoặc URL ký.

## 14. Nghiệm thu, giữ môi trường 1–2 tuần

| Kiểm tra          | Kết quả mong đợi                                                                                                   |
| ----------------- | ------------------------------------------------------------------------------------------------------------------ |
| CloudFront domain | Trang React tải qua HTTPS; S3 frontend vẫn private                                                                 |
| Cognito           | Tài khoản demo đăng nhập, nhận JWT; callback đúng domain                                                           |
| API Gateway       | Request không token nhận 401; token hợp lệ gọi API                                                                 |
| Authorization     | Student không xem draft/lesson chưa unlock; Instructor chỉ sửa course của mình                                     |
| RDS               | Private, không public; Lambda kết nối qua TCP 5432                                                                 |
| Upload            | Backend cấp presigned PUT; browser tải trực tiếp vào raw S3                                                        |
| Workflow          | S3 Object Created chạy đúng một Step Functions execution; trạng thái kết thúc REVIEW_REQUIRED hoặc FAILED có lý do |
| Review            | Instructor duyệt; lesson sang PUBLISHED; student mới xem được                                                      |
| Video             | Backend kiểm tra enrollment/unlock trước khi cấp CloudFront signed URL                                             |
| Logs/Budget       | Logs tra được theo lesson/execution; budget alert đã bật                                                           |

Gửi giảng viên CloudFront URL, tài khoản LearnCloud demo và thời hạn kiểm tra. Không gửi AWS portal, AWS credential, DB password, private key hay secret. Trong kỳ kiểm tra, giữ CloudFront, API Gateway, Cognito, Lambda, RDS và S3 tồn tại; dịch vụ Lambda/API không cần giữ execution chạy liên tục. Không xóa RDS hoặc bucket trước khi thầy hoàn tất.

## 15. Cleanup sau khi giảng viên xác nhận

1. Sao lưu dữ liệu cần giữ; ghi biên bản và URL/IDs cần bàn giao, không ghi secret.
2. Tắt EventBridge rule để object mới không khởi động job.
3. Xóa API Gateway và CloudFront distribution (CloudFront cần disable trước khi delete); xóa Cognito demo users/pool nếu không giữ môi trường.
4. Xóa Lambda functions và Step Functions state machine sau khi xác nhận không còn execution cần tra cứu.
5. Xóa object test; xóa S3 buckets chỉ khi đã xác nhận dữ liệu không cần giữ và bucket trống.
6. Xóa RDS/snapshot theo quyết định nhóm; xóa DB subnet group, VPC endpoints, security groups và VPC sau cùng.
7. Gỡ quyền IAM Identity Center của thành viên rời nhóm. Kiểm tra Billing để tìm endpoint hoặc tài nguyên còn tồn tại.

## Trạng thái hiện tại của repository

Repo có FastAPI/React, schema và adapter S3; các hạng mục Cognito JWT, Lambda/Mangum, đóng gói ZIP, signed video delivery, và state machine/EventBridge/MediaConvert/Transcribe cần hoàn thiện trước khi có thể nghiệm thu toàn bộ K1–K6. Không coi `/health` của local hoặc Lambda mẫu là bằng chứng pipeline và xác thực Cognito đã hoạt động.
