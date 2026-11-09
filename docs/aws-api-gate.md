# TÀI LIỆU BÀN GIAO HẠ TẦNG AWS – LEARNCLOUD

**Dự án:** LearnCloud – Learning Management System on AWS  
**Người phụ trách:** Dũng – Cloud Deployment  
**Ngày cập nhật:** 09/11/2026  
**AWS Region:** Singapore (`ap-southeast-1`)

---

## 1. Thông tin hạ tầng AWS

| Thành phần            | Thông tin bàn giao                 |
| --------------------- | ---------------------------------- |
| AWS Region            | `ap-southeast-1`                   |
| API Gateway           | `learncloud-api-API`               |
| API Gateway ID        | `lavh5njepc`                       |
| API Stage             | `default`                          |
| Lambda Function       | `learncloud-api`                   |
| Lambda Runtime        | Python 3.12 – x86_64               |
| Lambda Handler        | `lambda_function.lambda_handler`   |
| Lambda Execution Role | `LearnCloud-Lambda-Execution-Role` |
| RDS Instance          | `learncloud-db`                    |
| Database Engine       | PostgreSQL 16.9                    |
| Database Name         | `learncloud`                       |
| S3 Bucket             | `learncloud-videos-mentorcloud`    |
| Cognito User Pool ID  | `ap-southeast-1_o2Y9UHxoo`         |
| Cognito App Client ID | `3b8ro7mhcnkdfvk5grr76fn1pe`       |
| CloudWatch Log Group  | `/aws/lambda/learncloud-api`       |
| DB_PASSWORD           | mentorcloudrds                     |

### API Base URL

```text
https://lavh5njepc.execute-api.ap-southeast-1.amazonaws.com/default
```

Frontend sử dụng địa chỉ này làm API Base URL.

Ví dụ các endpoint đã kiểm thử:

```text
GET  /health
GET  /courses
GET  /courses/{course_id}/sections

POST /courses
POST /courses/{course_id}/sections
POST /sections/{section_id}/lessons
POST /lessons/{lesson_id}/upload-url
```

Đây là các route đã được sử dụng trong quá trình kiểm thử; không phải danh sách đầy đủ các API của LearnCloud.

### CORS và Cognito JWT trên HTTP API

HTTP API phải xử lý preflight từ trình duyệt trước khi request tới Lambda:

- Allowed origins: `http://localhost:5173`, `http://127.0.0.1:5173` và
  `https://d1my2q1fj0jxmb.cloudfront.net`. Nếu đổi domain frontend, cập nhật
  origin production chính xác tại đây và trong `CORS_ALLOWED_ORIGINS` của Lambda.
- Allowed methods: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`, `HEAD`.
- Allowed headers: `authorization`, `content-type`.
- Không bật credential cookies; frontend gửi Cognito Access Token trong
  `Authorization: Bearer ...`.
- Route `OPTIONS /{proxy+}` dùng cùng Lambda integration nhưng
  `Authorization: NONE` để preflight không bị JWT authorizer chặn.
- Frontend đăng nhập trực tiếp với Cognito; không tạo route `/auth/login` công khai
  trên API Gateway. Các endpoint đăng ký/xác minh/khôi phục mật khẩu phía backend
  (`POST /auth/register`, `/auth/verify-email`,
  `/auth/resend-verification`, `/auth/forgot-password`, `/auth/reset-password`)
  dùng `Authorization: NONE`. Chúng cần truy cập được trước khi người dùng có
  access token.
- Nếu API Gateway còn route `POST /auth/login` từ cấu hình cũ, hãy xóa route đó
  sau khi deploy backend mới; route đăng nhập không còn thuộc API.
- `GET /auth/me` và các API nghiệp vụ dùng Cognito JWT authorizer. Gửi Cognito
  Access Token trong `Authorization: Bearer <access-token>`.
- User Pool ID, App Client ID và Region trong frontend phải cùng pool/client với
  Lambda và API Gateway JWT authorizer. App client dùng cho SPA phải là public
  (không có client secret) và bật `ALLOW_USER_PASSWORD_AUTH`.
- Đăng nhập frontend dùng Amplify Auth với `USER_PASSWORD_AUTH`; Cognito phát
  token trực tiếp cho trình duyệt. Backend không gọi `InitiateAuth`, `GetUser`
  hoặc `AdminListGroupsForUser` cho thao tác xác thực thông thường; `/auth/me`
  dùng claims đã được API Gateway xác minh và ánh xạ user/role vào PostgreSQL.
- User phải được tạo/liên kết trong PostgreSQL qua luồng đăng ký-xác minh hoặc
  quy trình cấp tài khoản quản trị trước lần gọi `/auth/me` đầu tiên; Access Token
  không mặc định chứa email để backend tự tạo hồ sơ mới.
- Các API quản trị Cognito và các thao tác đăng ký, xác minh, đổi/khôi phục mật
  khẩu vẫn gọi Cognito từ Lambda; chúng vẫn cần network path tới Cognito riêng.
- Các route nghiệp vụ khác tiếp tục dùng Cognito JWT authorizer; không bỏ
  authorizer khỏi route wildcard.

Sau khi cập nhật cấu hình CORS/route, xác nhận `OPTIONS` trả thành công và có
`Access-Control-Allow-Origin`, `Access-Control-Allow-Methods` và
`Access-Control-Allow-Headers`. CORS được cấu hình trên HTTP API; middleware
FastAPI một mình không thể xử lý preflight nếu Gateway từ chối request trước
khi gọi Lambda.

---

## 2. Cấu hình dành cho Frontend React

Trong thư mục Frontend, tạo hoặc cập nhật file `.env.local`:

```dotenv
VITE_API_BASE_URL=https://lavh5njepc.execute-api.ap-southeast-1.amazonaws.com/default

VITE_AWS_REGION=ap-southeast-1
VITE_COGNITO_USER_POOL_ID=<user-pool-id>
VITE_COGNITO_APP_CLIENT_ID=<public-app-client-id>
```

Không tạo App Client có client secret cho ứng dụng trình duyệt. Hãy xác nhận
`VITE_COGNITO_APP_CLIENT_ID` khớp với client ID trong Lambda và Audience của JWT
authorizer trước khi build/deploy frontend.

Tên biến phải được đối chiếu với code Frontend thực tế. Nếu dự án đang dùng tên biến khác, giữ nguyên tên mà ứng dụng đọc.

### Gửi yêu cầu tới Backend

Các API yêu cầu xác thực phải gửi Cognito Access Token qua HTTP Header:

```http
Authorization: Bearer <ACCESS_TOKEN>
```

Ví dụ:

```javascript
const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/courses`, {
  headers: {
    Authorization: `Bearer ${accessToken}`,
  },
});
```

**Lưu ý:**

- Không sử dụng AWS Access Key hoặc Secret Access Key trong Frontend.
- Không đưa mật khẩu RDS vào file `.env.local` của Frontend.
- Cognito User Pool ID và App Client ID là thông tin cấu hình ứng dụng; chúng không thay thế cơ chế bảo mật và xác thực JWT.
- Không commit Access Token, Refresh Token hoặc thông tin bí mật lên GitHub.

---

## 3. Hướng dẫn cập nhật Backend lên AWS Lambda

Backend LearnCloud sử dụng:

- FastAPI để xây dựng API.
- Mangum để chạy FastAPI trên Lambda.
- SQLAlchemy và pg8000 để kết nối PostgreSQL.
- API Gateway để cung cấp HTTP API.
- Cognito JWT Authorizer để xác thực người dùng.

### 3.1. Cấu trúc mã nguồn

Repository có các thư mục chính:

```text
LMS_Cloud/
├── backend/
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── dependencies.py
│       ├── api/
│       ├── services/
│       ├── models/
│       ├── repositories/
│       └── ...
├── ai_pipeline/
├── package_lambda.py
└── learncloud-lambda.zip
```

Gói Lambda sau khi đóng gói phải có cấu trúc:

```text
learncloud-lambda.zip
├── lambda_function.py
├── app/
│   ├── main.py
│   └── ...
└── ai_pipeline/
    └── ...
```

### 3.2. Đóng gói Backend

Mở Windows CMD tại thư mục dự án:

```bat
cd /d D:\PROJECTS\LMS_Cloud
```

Chạy script đóng gói đã sử dụng:

```bat
python package_lambda.py
```

Trước khi upload, kiểm tra ZIP có `lambda_function.py`, `app/main.py` và `app/services/auth_service.py`.

### 3.3. Deploy lên Lambda

Yêu cầu: Thành viên thực hiện phải được cấp IAM permission phù hợp để cập nhật Lambda.

Chạy:

```bat
aws lambda update-function-code ^
  --function-name learncloud-api ^
  --zip-file fileb://learncloud-lambda.zip ^
  --region ap-southeast-1 ^
  --no-cli-pager
```

Chờ AWS cập nhật:

```bat
aws lambda wait function-updated ^
  --function-name learncloud-api ^
  --region ap-southeast-1
```

Kiểm tra:

```bat
aws lambda get-function-configuration ^
  --function-name learncloud-api ^
  --region ap-southeast-1 ^
  --query "{State:State,LastUpdateStatus:LastUpdateStatus,Handler:Handler}" ^
  --output json
```

Kết quả cần có:

```json
{
  "State": "Active",
  "LastUpdateStatus": "Successful",
  "Handler": "lambda_function.lambda_handler"
}
```

**Quy tắc triển khai:** Chỉ cập nhật code khi có bản được nhóm thống nhất. Cần lưu phiên bản Lambda đang hoạt động trước khi triển khai thay đổi lớn. Không tự ý xóa Lambda Layer, Security Group hoặc thay đổi cấu hình VPC.

Nếu thêm thư viện Python mới, phải cập nhật Lambda Layer tương ứng; chỉ đóng gói lại mã nguồn là chưa đủ.

---

## 4. Cấu hình Backend và Database

Lambda được cấu hình các Environment Variables:

| Key                     | Mục đích                                              |
| ----------------------- | ----------------------------------------------------- |
| `DB_HOST`               | Endpoint PostgreSQL                                   |
| `DB_PORT`               | Cổng PostgreSQL, hiện dùng `5432`                     |
| `DB_NAME`               | Tên database, `learncloud`                            |
| `DB_USER`               | Database username                                     |
| `DB_PASSWORD`           | Mật khẩu database – **không bàn giao trong tài liệu** |
| `AWS_REGION`            | `ap-southeast-1`                                      |
| `COGNITO_REGION`        | `ap-southeast-1`                                      |
| `COGNITO_USER_POOL_ID`  | Cognito User Pool ID                                  |
| `COGNITO_APP_CLIENT_ID` | Cognito App Client ID                                 |
| `S3_BUCKET`             | Bucket lưu video                                      |

### Lưu ý kết nối PostgreSQL

- Lambda đã kết nối thành công tới RDS qua VPC và Security Group.
- Backend sử dụng SQLAlchemy và pg8000.
- Các thành viên không cần mở RDS ra Internet để triển khai API.
- Không lưu mật khẩu database trong repository hoặc tài liệu bàn giao.
- Mật khẩu hiện được đọc từ biến môi trường Lambda; cần chuyển sang cơ chế quản lý bí mật phù hợp khi hoàn thiện môi trường production.

---

## 5. Xác thực và phân quyền

LearnCloud sử dụng Cognito để xác thực và PostgreSQL để lưu hồ sơ người dùng.

Các vai trò nghiệp vụ:

| Cognito Group | Backend Role |
| ------------- | ------------ |
| `Instructor`  | `INSTRUCTOR` |
| `Student`     | `STUDENT`    |
| `Admin`       | `ADMIN`      |

Backend cần chuyển đổi tên nhóm một cách thống nhất, bao gồm trường hợp API Gateway truyền nhóm dưới dạng chuỗi `[Instructor]`.

**Lưu ý dành cho Backend:**

- API Gateway JWT Authorizer xác thực token trước khi chuyển yêu cầu vào Lambda đối với các route được bảo vệ.
- Backend kiểm tra vai trò và quyền sở hữu tài nguyên.
- Cognito `sub` phải được liên kết chính xác với `users.cognito_sub` trong PostgreSQL.
- Cần hoàn thiện luồng đồng bộ người dùng tự động, tránh phụ thuộc vào việc INSERT thủ công tài khoản.
- Không tự cấp quyền `ADMIN` hoặc `INSTRUCTOR` nếu không có thông tin phân quyền đã xác thực.

---

## 6. Quy trình upload video lên Amazon S3

Backend đã triển khai cơ chế **Presigned PUT URL**.

Luồng hoạt động:

```text
Frontend
   |
   | POST /lessons/{lesson_id}/upload-url
   v
API Gateway → Lambda FastAPI
   |
   | Kiểm tra Instructor và quyền sở hữu Lesson
   v
Tạo S3 Presigned URL
   |
   v
Frontend PUT video trực tiếp lên S3
   |
   v
Amazon S3 Bucket
```

### API tạo URL upload

```http
POST /lessons/{lesson_id}/upload-url
```

Request Body ví dụ:

```json
{
  "filename": "test-video.mp4",
  "content_type": "video/mp4",
  "file_size": 1048576
}
```

Response bao gồm `upload_url`, `object_key`, `expires_in`, `method` và `content_type`.
`upload_id` và `required_headers` chỉ có khi backend bật video pipeline; khi chưa
bật pipeline, frontend vẫn PUT tệp lên Presigned URL với `Content-Type`.

Frontend dùng `PUT` đến `upload_url` với header `Content-Type` phù hợp, không gửi Cognito Token tới S3.

**Đã kiểm thử thành công:** Backend tạo URL, S3 nhận request PUT với HTTP 200 và object video xuất hiện trong bucket.

**Chưa xác nhận:** API thông báo hoàn tất upload, cập nhật Lesson sau upload, tự động xử lý video, transcript và AI Pipeline.

---

## 7. Kiểm thử sau triển khai

| Bài kiểm thử                              | Kết quả đã xác nhận               |
| ----------------------------------------- | --------------------------------- |
| `GET /health`                             | HTTP 200                          |
| `GET /courses`                            | HTTP 200, trả danh sách khóa học  |
| `GET /courses/1/sections`                 | HTTP 200                          |
| `POST /courses`                           | Tạo khóa học thành công           |
| `POST /courses/5/sections`                | Tạo Section thành công            |
| `POST /sections/8/lessons`                | Tạo Lesson thành công             |
| `POST /lessons/13/upload-url`             | Tạo Presigned URL thành công      |
| PUT video tới S3                          | HTTP 200, xác nhận object trên S3 |
| Kiểm thử toàn bộ nghiệp vụ và AI Pipeline | Chưa hoàn tất                     |

Các ID 5, 8 và 13 là dữ liệu đã tạo để thử nghiệm; không được dùng cố định trong mã nguồn Frontend.

### Kiểm tra log khi gặp lỗi

Vào:

**AWS Console → CloudWatch → Log groups → `/aws/lambda/learncloud-api`**

Tìm request tương ứng theo thời điểm và Request ID. Không ghi Access Token, mật khẩu hoặc Presigned URL vào log.

---

## 8. Phân công trách nhiệm sau bàn giao

**Cloud Deployment – Dũng**

- Quản lý hạ tầng IAM, VPC, Lambda, API Gateway, RDS, S3.
- Theo dõi CloudWatch và AWS Budgets.
- Hỗ trợ deploy backend và xử lý lỗi hạ tầng.
- Kiểm tra IAM Role, quyền AWS và cấu hình môi trường.

**Backend Team**

- Phát triển và bảo trì API nghiệp vụ.
- Quản lý database schema, migrations.
- Hoàn thiện xác thực, đồng bộ người dùng và phân quyền.
- Bổ sung cơ chế xác nhận upload và cập nhật Lesson.
- Viết kiểm thử cho API.

**Frontend Team**

- Cấu hình API Base URL và Cognito.
- Tích hợp đăng nhập, quản lý Course/Section/Lesson.
- Tích hợp upload video bằng Presigned URL.
- Kiểm thử CORS và xử lý trạng thái upload.

**AI Pipeline Team**

- Tích hợp xử lý video sau upload.
- Triển khai các bước transcript, summary, flashcard và quiz.
- Phối hợp Backend để cập nhật trạng thái xử lý và học liệu vào database.

---

## 9. Các lưu ý bảo mật và vận hành

1. Không chia sẻ mật khẩu RDS, AWS Secret Access Key, Cognito Access Token hoặc Presigned URL còn hiệu lực.
2. Chỉ cấp IAM permissions cần thiết cho từng thành viên.
3. Không thay đổi VPC, RDS hoặc Security Groups khi chưa thống nhất với người phụ trách hạ tầng.
4. Không upload file `.env` lên Lambda hoặc GitHub.
5. Những API yêu cầu đăng nhập phải được bảo vệ bằng JWT Authorizer và kiểm tra quyền tại backend.
6. Kiểm tra CloudWatch Alarms, SNS email và AWS Budgets định kỳ.
7. Xóa Lambda chẩn đoán tạm thời `learncloud-db-inspect` sau khi hoàn tất kiểm thử, tránh duy trì bản sao thông tin database.
8. Giữ lại bản Lambda version ổn định để khôi phục khi triển khai lỗi.

---

## 10. Kết luận bàn giao

Hạ tầng cốt lõi của LearnCloud đã được triển khai trên AWS và kiểm thử thành công các luồng chính:

**Frontend/Client → API Gateway → Lambda FastAPI → RDS PostgreSQL**, cùng với **Cognito JWT Authorization** và **S3 Presigned Video Upload**.

Nhóm có thể sử dụng hạ tầng hiện tại để tiếp tục tích hợp các module nghiệp vụ và AI.

Các phần cần hoàn thiện trước khi nghiệm thu hệ thống đầy đủ gồm: đồng bộ tài khoản tự động, xác nhận upload và cập nhật Lesson, tích hợp AI Pipeline, kiểm thử Frontend và kiểm tra đầy đủ monitoring, alarms, bảo mật.

**Trạng thái bàn giao:** Hạ tầng nền tảng đã hoạt động; chưa xác nhận toàn bộ chức năng LMS hoàn chỉnh.
