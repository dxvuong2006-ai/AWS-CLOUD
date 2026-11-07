# Triển khai LearnCloud lên AWS theo kiến trúc K1–K6

Tài liệu này là runbook triển khai demo LearnCloud trên **một AWS account dùng chung**, Region **Asia Pacific (Singapore), `ap-southeast-1`**. Bốn thành viên A/B/C/D đăng nhập bằng user riêng trong IAM Identity Center; không dùng chung mật khẩu hoặc access key. Các nút trong Console có thể đổi nhãn nhẹ theo giao diện AWS; nếu khác, dùng ô tìm kiếm dịch vụ trên đầu trang để mở đúng dịch vụ.

> **Đọc trước khi bấm tạo:** hạ tầng AWS không tự bổ sung tính năng ứng dụng còn thiếu. Mục 1 là cổng kiểm tra bắt buộc. Nếu mục nào ghi **CHƯA SẴN SÀNG**, dừng ở đó và giao việc cho người phụ trách; không tạo dịch vụ trả phí để thay thế mã còn thiếu. Môi trường demo có thể phát sinh phí.

### Quy ước dùng trong toàn bộ runbook

- Làm theo thứ tự mục **0 → 15**. Chỉ chuyển mục tiếp theo khi điều kiện “Kết quả cần ghi lại” của mục hiện tại đã đạt.
- Người bấm Console phải đăng nhập bằng **AWS account dùng chung** và permission set đã được cấp cho đúng nhiệm vụ. A/B/C/D không phải AWS account riêng; đó là bốn danh tính riêng trong cùng account.
- Mọi thao tác cần tài nguyên trong Region đều phải ở `ap-southeast-1`. IAM Identity Center/Billing/CloudFront là các màn hình có thể hiển thị phạm vi toàn cục; không tự đổi Region của các dịch vụ còn lại.
- Giá trị trong `<DẤU_NGOẶC_GÓC>` là chỗ cần thay bằng giá trị thật đã ghi ở các bước trước. Không nhập nguyên dấu ngoặc.
- **Không ghi password, private key, token, presigned URL hoặc secret vào tài liệu, Git, chat nhóm hay ảnh chụp màn hình.** Chỉ lưu các ARN, URL, ID và tên tài nguyên không nhạy cảm trong bảng bàn giao của nhóm.

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

## 0. Vai trò, đầu việc và quyền AWS

Phân công dưới đây dùng các vai trò A–D đã nêu trong API contract: A phụ trách kiến trúc
và thao tác tích hợp backend trên AWS; B frontend, C AI/review, D mã backend/database và
hạ tầng runtime. A trực tiếp cấu hình API Gateway/CloudWatch và chạy kiểm tra API trên AWS
theo thông số D bàn giao. **Chủ account** là người quản lý AWS account;
vai trò này có thể do một thành viên đảm nhiệm nhưng không đồng nghĩa với A/B/C/D.

| Người/vai trò | Phạm vi chịu trách nhiệm | AWS access cần có | Bàn giao/điều kiện hoàn tất |
|---|---|---|---|
| **Chủ account / IAM administrator** | Bật MFA, IAM Identity Center, tạo danh tính riêng, permission sets, ngân sách và runtime execution roles. Duyệt quyền, theo dõi Billing, thu hồi quyền khi kết thúc. Root chỉ dùng cho việc quản trị account cần root. | Quản trị IAM/Identity Center và Billing ở mức cần thiết; không dùng root cho triển khai ứng dụng. Không chia sẻ thông tin đăng nhập. | Gửi cho nhóm account ID, region, permission set và tên/ARN tài nguyên cần thiết; không gửi credential hay secret. |
| **A — Kiến trúc và AWS backend integration** | Chốt contract/tiêu chí; trực tiếp tạo HTTP API, Lambda integration, routes, JWT authorizer và stage API Gateway; cấu hình log retention, SNS notification và CloudWatch alarms; gọi thử API AWS, kiểm tra 401/403/health và theo dõi log. | Permission set riêng giới hạn vào API Gateway LearnCloud, invoke và `lambda:AddPermission` trên function được chỉ định, CloudWatch logs/alarms và SNS topic theo prefix LearnCloud. Không có quyền sửa code/config Lambda, IAM, RDS hay migration. | Bàn giao API ID/Invoke URL, route/auth map, alarms, kết quả smoke test và lỗi cần D xử lý; xác nhận API sẵn sàng cho B tích hợp. |
| **B — Frontend** | Tích hợp Cognito OIDC/PKCE, API Gateway URL/JWT, upload trực tiếp S3 và playback; build React, cấu hình S3 frontend/CloudFront và kiểm tra luồng UI. | Chỉ quyền cần thiết trên frontend bucket/distribution và Cognito app client. Không cần quyền IAM, RDS hay pipeline runtime. | Bàn giao build, URL/callback/CORS cần cấu hình, kết quả đăng nhập/upload/playback và lỗi UI còn lại cho D/A. |
| **C — AI và review học liệu** | Chốt đầu vào/đầu ra Transcribe/Bedrock theo contract; tích hợp worker AI, kiểm tra nội dung sinh, trạng thái REVIEW_REQUIRED và quy trình Instructor review/approve. Không tự approve/publish nội dung. | Không cần quyền AWS rộng mặc định. Khi tích hợp AWS được duyệt, chỉ cấp quyền Bedrock/Transcribe cần thiết và quyền xem log liên quan; không cấp IAM/RDS quản trị. | Bàn giao contract worker, model/service đã được phép, kiểm tra chất lượng và xác nhận AI bật được an toàn; AI giữ tắt nếu chưa đạt. |
| **D — Backend implementation và cloud runtime** | Sở hữu FastAPI/services/repositories/adapters, đóng gói và tạo/cập nhật Lambda, schema/migration, S3 backend, VPC/network, IAM runtime-role templates, Step Functions/EventBridge/MediaConvert. Cấp function ARN, Cognito issuer/client ID và danh sách routes cho A tạo API Gateway; xử lý finding A báo. | Permission set triển khai giới hạn theo tài nguyên LearnCloud trên Lambda/VPC/S3/RDS/Step Functions/EventBridge và `iam:PassRole` chỉ cho runtime roles đã duyệt. Không cấp IAM policy/role tùy ý hay Billing. | Bàn giao Lambda/runtime config đã duyệt, database/migration status, role ARN và thông số để A cấu hình API Gateway. |

### Cấp danh tính và permission sets

#### 0.1 Chủ account: bật MFA và vào IAM Identity Center

1. Mở `https://console.aws.amazon.com/` và đăng nhập bằng danh tính chủ account. Chọn đúng AWS account; kiểm tra account ID ở menu tài khoản góc trên bên phải.
2. Nếu đang dùng root: chọn menu tên account → **Security credentials** → mục **Multi-factor authentication (MFA)** → **Assign MFA device** → làm theo mã QR/ứng dụng xác thực → **Assign MFA**. Đăng xuất root sau bước này; công việc thường ngày dùng danh tính quản trị riêng.
3. Ô tìm kiếm dịch vụ → nhập **IAM Identity Center** → mở dịch vụ. Nếu thấy **Enable**, chọn **Enable** và xác nhận. Chờ trang tổng quan xuất hiện.
4. Menu trái → **Users** → **Add user**. Tạo bốn user riêng bằng email thành viên, đặt tên dễ nhận biết như `learncloud-a`, `learncloud-b`, `learncloud-c`, `learncloud-d`; chọn gửi email hướng dẫn đăng nhập → **Next** → **Add user**.
5. Menu trái → **Groups** → **Create group**. Tạo lần lượt `LearnCloud-Architecture`, `LearnCloud-Frontend`, `LearnCloud-AIReview`, `LearnCloud-BackendCloud`; trong từng group, chọn user tương ứng → **Create group**.

#### 0.2 Chủ account: tạo permission sets và gán người dùng

1. IAM Identity Center → **Permission sets** → **Create permission set** → **Custom permission set**.
2. Tạo `LearnCloud-ReadOnly` trước. Chọn thời hạn phiên 1–4 giờ → **Next** → tab **AWS managed policies** → tìm/chọn `ReadOnlyAccess` → **Next** → đặt tên → **Create**. Gán cho C; A cũng giữ quyền này để xem logs và điều tra.
3. Tạo `LearnCloud-AwsIntegration` bằng **Custom permission set** cho A. Chủ account/AWS admin dán inline policy đã review, giới hạn vào API Gateway LearnCloud (create/update integration/routes/authorizer/stage), invoke và `lambda:AddPermission` trên đúng Lambda function, CloudWatch logs/alarms và SNS topic có tên bắt đầu `learncloud-`. Không cấp Lambda code/config update, IAM role/policy, RDS hoặc quyền sửa database.
4. Tạo `LearnCloud-Frontend` và `LearnCloud-BackendCloud` bằng **Custom permission set**. Dán policy nội bộ đã review, giới hạn theo ARN/tags tài nguyên LearnCloud; quyền D cần `iam:PassRole` chỉ cho runtime roles đã duyệt. Không dán policy runtime từ `infrastructure/iam/` vào permission set triển khai.
5. Với `LearnCloud-AIReview`, giữ `ReadOnlyAccess`; chỉ thêm quyền Bedrock/Transcribe sau khi A duyệt model/dịch vụ và D cung cấp ARN cần thiết.
6. IAM Identity Center → **AWS accounts** → đánh dấu account lab → **Assign users or groups** → **Assign users or groups**.
7. Chọn group A → **Next** → gán `LearnCloud-ReadOnly` và `LearnCloud-AwsIntegration` → **Next → Submit**. Gán các group còn lại với permission sets phù hợp. Không gán permission set quản trị cho cả nhóm.
8. Mỗi thành viên mở email mời, đặt mật khẩu và bật MFA theo yêu cầu. Đăng nhập access portal; chọn đúng account, đúng permission set, rồi bấm **Management console**. Giao diện cần thiết sẽ được cấp theo nhiệm vụ.

> Nếu chủ account chưa có policy triển khai đã review cho các custom permission sets, dừng tại đây và nhờ AWS/IAM administrator chuẩn bị policy. Không thay thế bằng `AdministratorAccess` hoặc `PowerUserAccess`.

#### 0.3 Mỗi thành viên: xác nhận account và Region

1. Cài AWS CLI v2 nếu cần chạy lệnh kiểm tra; mở access portal → chọn account → **Command line or programmatic access** → làm theo mục **AWS CLI** để tạo/cập nhật profile SSO cá nhân.
2. Mở PowerShell và chạy:

```powershell
aws sso login --profile learncloud
aws sts get-caller-identity --profile learncloud
```

3. Xác nhận `Account` khớp account ID chủ account đã thông báo. Mỗi người dùng profile/phiên đăng nhập của mình; không sao chép file credentials của thành viên khác.
4. Trong AWS Console, mở menu Region ở góc trên bên phải → chọn **Asia Pacific (Singapore) ap-southeast-1**. Khi chuyển sang dịch vụ khác, kiểm tra lại Region trước khi tạo resource.

IAM Identity Center cấp quyền đăng nhập vào AWS. Nó không tạo user Instructor/Student trong LearnCloud và cũng không thay thế execution role của Lambda/Step Functions.

#### 0.4 Nhiệm vụ thực tế trên AWS của A

A làm phần kết nối và vận hành kiểm tra sau khi D đã tạo Lambda/runtime role. Đây là thao tác thật trên AWS, không chỉ review tài liệu:

1. **Tạo API Gateway HTTP API** theo mục 9: gắn Lambda API, thêm routes, đặt JWT authorizer và tạo `$default` stage. D bàn giao function ARN, Cognito issuer/client ID và route nào cần bảo vệ.
2. **Cấu hình giám sát backend** theo mục 13: đặt log retention cho các function, tạo SNS topic/subscription và CloudWatch alarms cho Lambda/API Gateway/Step Functions.
3. **Chạy smoke test trên AWS**: kiểm tra `/health`, request nghiệp vụ thiếu token phải 401, token demo hợp lệ phải tới được backend; xem API Gateway/Lambda logs và ghi request ID để D tra lỗi.
4. **Bàn giao cho B/D**: API ID, Invoke URL, route/auth map, alarm names và kết quả test. Không gửi token/secret trong bảng bàn giao.

Các việc bắt đầu sau khi mục 1 xác nhận API Cognito/Lambda sẵn sàng. Nếu A chưa được gán `LearnCloud-AwsIntegration`, chủ account cấp permission set giới hạn trước khi làm. A không sửa Lambda code/environment, IAM roles, RDS hoặc migration.

#### 0.5 Bảng ghi kết quả để bàn giao giữa các thành viên

Tạo một bản copy bảng này trong tài liệu nội bộ nhóm. Chỉ ghi ID/ARN/URL và tên tài nguyên, tuyệt đối không ghi giá trị secret:

| Giá trị cần bàn giao | Ai ghi | Giá trị |
|---|---|---|
| AWS account ID / Region | Chủ account / D |  |
| VPC ID / private subnet IDs / Lambda, RDS, endpoint SG IDs | D |  |
| Frontend, raw, processed S3 bucket names | D/B |  |
| Cognito User Pool ID / App Client ID / domain | B |  |
| RDS endpoint / port / database name / Secret ARN | Chủ DB / D |  |
| Runtime role names / ARNs | Chủ account / D |  |
| Lambda function names / ARNs / status | D |  |
| Step Functions ARN / EventBridge rule names | D |  |
| API Gateway ID/Invoke URL / CloudFront domain | A (API Gateway) / B (CloudFront) |  |
| Người nhận budget alert / mức trần / ngày cleanup | Chủ account / A |  |

### Ai thực hiện các mục triển khai

| Mục | Người chịu trách nhiệm chính | Phối hợp/duyệt |
|---|---|---|
| 1, 3, 6–8, 11, 15 — readiness/backend code, mạng, DB, Lambda, workflow, cleanup | D | A xác nhận thông tin API/route, smoke test và review trạng thái; chủ account cấp quyền; chủ DB duyệt schema/migration |
| 9 — API Gateway HTTP API, routes, JWT authorizer, stage và endpoint test | A | D bàn giao Lambda ARN, Cognito issuer/client ID, invoke permission; B kiểm tra bearer token từ frontend |
| 13 — log retention, SNS alerts và CloudWatch alarms | A | D bàn giao tên resources/metrics; chủ account theo dõi Billing và người nhận alert |
| 4, 5, 10 — S3 frontend/media, Cognito app client, CloudFront và tích hợp UI | B (tích hợp và xác nhận); D (backend bucket/policy và phối hợp cấu hình AWS) | Chủ account/IAM admin cấp quyền; A rà soát; C kiểm tra phần học liệu nếu liên quan |
| 12 — Bedrock và dịch vụ AI | C (contract, tích hợp và chất lượng); D (IAM/network/runtime deployment) | A duyệt phạm vi/chi phí; chủ account xác nhận quyền model và ngân sách |
| 2, 14 — ngân sách và nghiệm thu tổng thể | Chủ account (budget), A (tiêu chí/điều phối + smoke test AWS) | B/C/D cung cấp kết quả phần mình; D xử lý backend finding |

Không bắt đầu tạo tài nguyên tính phí trước khi chủ account chốt ngân sách và D xác nhận
region/quyền. Quyền sản phẩm trong Cognito (`Instructor`, `Student`, `Admin`) là vai trò
người dùng LearnCloud, khác với vai trò thành viên nhóm A–D và quyền IAM của AWS.

Trên máy người đóng gói, cần AWS CLI v2, Git, Python 3.12 và Node.js/npm. Không cần Docker. Mở PowerShell và đăng nhập CLI theo phần **Command line or programmatic access** trong AWS access portal:

```powershell
aws sso login --profile learncloud
aws sts get-caller-identity --profile learncloud
```

Xác nhận đúng account ID trước khi tạo tài nguyên. Region thống nhất toàn tài liệu là **Asia Pacific (Singapore) `ap-southeast-1`**.

## 1. Kiểm tra mã nguồn trước khi tạo AWS resources

**Chịu trách nhiệm:** D rà soát backend/workflow; B rà soát frontend/Cognito; C xác nhận
contract AI/review; A chốt dependency và tiêu chí sẵn sàng.

Trạng thái mã được đối chiếu với repository hiện tại. Đây là **cổng sẵn sàng**, không phải bước bấm Console. D ghi trạng thái từng dòng; A duyệt; chỉ bắt đầu mục 2 khi toàn bộ yêu cầu của luồng demo đã sẵn sàng.

| Hạng mục cần có trước AWS | Trạng thái hiện tại trong repo | Người làm / điều kiện đạt |
|---|---|---|
| Video pipeline Lambda/Step Functions/EventBridge | Có handler, ASL và hướng dẫn Console riêng; tài liệu ghi **CODE READY / AWS NOT DEPLOYED**. | D triển khai theo [hướng dẫn pipeline](aws-video-pipeline-console-setup.md); chủ DB duyệt và áp dụng schema ledger theo [migration 0005](video-pipeline-migration-0005.md). |
| API FastAPI lên Lambda | `backend/requirements.txt` chưa có `mangum`; chưa có `backend/app/lambda_handler.py`; settings yêu cầu `DATABASE_URL` và `JWT_SECRET_KEY`. | D phải thêm/kiểm tra adapter Lambda, cách lấy DB secret an toàn, và cấu hình runtime trước khi tạo API Lambda. ZIP Windows không dùng trực tiếp cho dependency cần binary Linux. |
| Cognito authentication | Frontend gửi bearer token nếu có nhưng chưa có OIDC sign-in; backend hiện dùng JWT local/demo, chưa đọc JWT claims do API Gateway xác minh. | B tích hợp authorization code + PKCE; D triển khai ánh xạ `sub`/role và authorization backend. Giữ các API nghiệp vụ đóng cho đến khi đạt. |
| API CORS | `backend/app/main.py` chỉ cho localhost:5173 hiện tại. | D cập nhật allow-origin thành CloudFront domain thật trước khi kiểm tra browser. |
| S3 playback qua CloudFront signed URL | Chưa thấy tích hợp signer trong cấu hình backend. | B/D hoàn thiện key group + signer, test authorization; không coi cấu hình distribution đơn thuần là hoàn tất playback private. |
| Video database ledger | Có migration file 0005, được ghi là **REVIEWED / NOT APPLIED** và chỉ chạy khi điều kiện trong migration/preflight khớp. Có hai file mang số `0004` trong repository; phải dùng registry DB và tài liệu migration để xác định đúng lịch sử. | Chủ DB kiểm tra backup/preflight, xác nhận chính xác version/description và áp dụng migration qua quy trình đã review. Không nạp schema bằng Lambda migration dùng một lần và không chạy file 0005 theo phỏng đoán. |
| AI Worker của C | `VIDEO_AI_ENABLED` mặc định false; hướng dẫn pipeline quy định chưa tích hợp thì không bật AI. | C bàn giao worker thật, contract, model ID và tiêu chí chất lượng; D cấu hình role/secret/network; A duyệt chi phí. |

**Kết luận hiện tại:** chưa thể làm trọn bộ click-through rồi có ứng dụng AWS hoàn chỉnh chỉ với trạng thái code hiện tại. Có thể dựng một số tài nguyên nền sau khi ngân sách/quyền được duyệt, nhưng chưa được đưa API public hoặc bật pipeline/AI cho đến khi các hàng tương ứng đạt. Không tạo Lambda migration để chạy `database/schema.sql`; migration do chủ DB vận hành theo quy trình đã duyệt.

### 1.1 Checklist trước khi đi vào Console

1. D mở repository → xem các file và trạng thái ở bảng trên; ghi `SẴN SÀNG` hoặc `CHƯA SẴN SÀNG` cho từng hàng.
2. B chuẩn bị URL callback/logout dự kiến theo định dạng `https://<CLOUDFRONT_DOMAIN>/`; không nhập URL giả vào Cognito production app client.
3. C xác nhận AI bật hay tắt trong demo. Nếu chưa có worker/model đã duyệt, chọn **tắt**.
4. Chủ account ghi hạn mức ngân sách được phép chi, người nhận cảnh báo, ngày bắt đầu và ngày cleanup.
5. A rà soát bảng; nếu API Cognito hoặc DB migration chưa sẵn sàng thì ghi rõ giới hạn demo và không làm các bước bật public API.

## 2. Tạo cảnh báo ngân sách trước

**Chịu trách nhiệm:** Chủ account tạo budget; A xác nhận mức trần với nhóm; D kiểm tra cảnh báo.

1. Chủ account đăng nhập Console → ô tìm dịch vụ → nhập **Billing and Cost Management** → chọn kết quả.
2. Menu trái → **Budgets** → **Create budget**.
3. Chọn **Customize (advanced)** nếu muốn nhiều ngưỡng cảnh báo; chọn **Next**. Chọn loại **Cost budget** → **Next**.
4. Ở **Set your budget**, nhập tên `learncloud-demo-budget`, kỳ **Monthly**, bắt đầu tháng hiện tại, đơn vị **USD**, số tiền đã được nhóm duyệt → **Next**.
5. Ở **Configure alerts**, chọn ngưỡng **Actual** 50%, **Actual** 80% và **Forecasted** 100% (hoặc ngưỡng nhóm đã duyệt). Với từng cảnh báo, nhập email nhận thông báo → **Add alert**.
6. Bấm **Next** qua phần action (không tạo action tự động dừng tài nguyên trong hướng dẫn này) → kiểm tra Summary → **Create budget**.
7. Quay về **Budgets**; xác nhận `learncloud-demo-budget` hiện trong danh sách. Ghi email nhận cảnh báo và hạn mức vào bảng bàn giao.

Budgets gửi cảnh báo, không tự dừng dịch vụ. Theo dõi chi phí hằng ngày trong suốt 1–2 tuần.

## 3. Tạo VPC, subnet và security groups

**Chịu trách nhiệm:** D thiết kế và cấu hình mạng; chủ account/IAM admin cấp quyền cần thiết.

### 3.1 VPC

1. Đăng nhập bằng permission set của D → Region góc trên phải **Asia Pacific (Singapore)** → ô tìm dịch vụ → **VPC**.
2. Menu trái → **Your VPCs** → **Create VPC**. Chọn **VPC and more**.
3. Nhập **Name tag auto-generation** `learncloud`; IPv4 CIDR `10.20.0.0/16`; IPv6 **No IPv6 CIDR block**; tenancy **Default**.
4. **Number of Availability Zones** = 2; **Number of public subnets** = 0; **Number of private subnets** = 2; NAT gateways = **None**; VPC endpoints = **None**; bật DNS hostnames/resolution nếu có tùy chọn.
5. Mở **Preview**; xác nhận có 2 private subnet ở 2 AZ, không có public subnet/NAT. Chọn **Create VPC** và chờ trạng thái tạo xong.
6. Mở **Your VPCs** → chọn `learncloud` → ghi **VPC ID**. Mở **Subnets** → lọc VPC ID vừa ghi → ghi hai subnet có **Auto-assign public IPv4 address = No** và hai **Subnet ID**. Ghi thêm route table IDs nếu hiện.

Không đặt Lambda hoặc RDS vào public subnet. Không tạo NAT Gateway cho lab này. Các Lambda trong VPC cần VPC endpoints cho dịch vụ AWS mà chúng gọi; endpoints sẽ được tạo ở bước 3.3.

### 3.2 Security groups

Trong **VPC → Security groups → Create security group**, tạo từng security group theo các bước dưới đây. Với mỗi group, bấm **Create security group**, nhập name/description, chọn **VPC `learncloud`**, cấu hình rule rồi bấm **Create security group**:

| Name | Inbound | Outbound |
|---|---|---|
| `learncloud-lambda-sg` | Không có inbound | TCP 5432 tới `learncloud-rds-sg`; TCP 443 tới endpoint SG |
| `learncloud-rds-sg` | PostgreSQL TCP 5432, source `learncloud-lambda-sg` | Mặc định |
| `learncloud-vpce-sg` | HTTPS TCP 443, source `learncloud-lambda-sg` | Mặc định |

1. Tạo `learncloud-rds-sg` trước: **Inbound rules → Add rule** → Type **PostgreSQL** → Source **Custom** → nhập/chọn ID của `learncloud-lambda-sg` sau khi group đó có; nếu chưa có thì lưu group trước, quay lại **Edit inbound rules** sau khi tạo Lambda SG.
2. Tạo `learncloud-vpce-sg`: Inbound **HTTPS**, Source `learncloud-lambda-sg`.
3. Tạo `learncloud-lambda-sg`: không thêm inbound rule. Với outbound, nếu Console mặc định `All traffic`, thay bằng TCP 5432 đến `learncloud-rds-sg` và HTTPS 443 đến `learncloud-vpce-sg` sau khi đã có cả hai group.
4. Quay lại `learncloud-rds-sg` → **Inbound rules → Edit inbound rules** → PostgreSQL/TCP 5432, Source `learncloud-lambda-sg` → **Save rules**.
5. Mở từng group, xác nhận **VPC ID** giống nhau. Không thêm nguồn `0.0.0.0/0` vào RDS. Nếu VPC wizard tạo subnet/route khác dự kiến, dừng và sửa trước khi tạo DB.

### 3.3 VPC endpoints thay NAT

1. Chỉ tạo endpoint cho API mà Lambda thật sự gọi; D liệt kê từ environment/SDK client và policy trước. Mỗi endpoint interface có phí theo giờ.
2. Console → **VPC → Endpoints → Create endpoint**. Với S3 chọn **AWS services**, tìm `com.amazonaws.ap-southeast-1.s3`, Type **Gateway**, chọn VPC `learncloud`, chọn route table gắn với hai private app subnet, policy **Full access** chỉ nếu bucket policy/IAM role đã giới hạn bucket; sau đó **Create endpoint**.
3. Với endpoint dạng interface, lặp lại **Create endpoint** → tìm service name Region Singapore (ví dụ `secretsmanager`, `logs`, `bedrock-runtime`, `mediaconvert` hoặc `transcribe` đúng theo code đang chạy) → Type **Interface** → VPC `learncloud`.
4. Ở **Subnets**, đánh dấu đúng hai private subnets, mỗi AZ một subnet. Ở **Security groups**, chọn `learncloud-vpce-sg`; bật **Enable DNS name/Private DNS** nếu tùy chọn được cung cấp.
5. Bấm **Create endpoint** → đợi **Status = Available**. Ghi endpoint ID và service name. Lặp cho từng API cần thiết.
6. Nếu Lambda cần gọi endpoint chưa có, yêu cầu D/IAM admin bổ sung trước khi bật chức năng. Không tạo NAT Gateway như cách thử nhanh.

Interface endpoints tính phí theo giờ/dữ liệu. Đếm endpoint thực sự cần dùng; không tạo Bedrock endpoint nếu chưa gọi Bedrock. Không tạo NAT Gateway trong cùng lúc chỉ để “thử”, vì sẽ phát sinh phí.

## 4. Tạo ba S3 buckets private

**Chịu trách nhiệm:** D tạo raw/processed buckets và policy backend; B phối hợp bucket
frontend, CORS và xác nhận browser upload; B kiểm tra build frontend.

1. D tạo tên bucket duy nhất trước, ví dụ `learncloud-web-<ACCOUNT_ID>-<SUFFIX>`, `learncloud-raw-<ACCOUNT_ID>-<SUFFIX>`, `learncloud-processed-<ACCOUNT_ID>-<SUFFIX>`. Dùng chữ thường, số và dấu gạch ngang; lưu tên chính xác.
2. Mở **S3 → Buckets → Create bucket**. Chọn Region `ap-southeast-1`; nhập tên bucket frontend → **Object Ownership: Bucket owner enforced** → giữ **Block all public access** bật → **Bucket Versioning: Disable** cho demo nếu không cần versioning → **Default encryption: SSE-S3** → **Create bucket**.
3. Lặp lại bước 2 cho raw và processed bucket. Không bật Static website hosting; CloudFront sẽ đọc bucket frontend riêng tư.
4. Mở từng bucket → **Properties** → xác nhận Region, Block Public Access và encryption. Ghi ba tên bucket vào bảng bàn giao.

### 4.1 CORS cho bucket raw

Raw bucket → **Permissions → Cross-origin resource sharing (CORS) → Edit**. Sau khi CloudFront domain đã tồn tại, dán CORS JSON dưới đây, thay domain thật rồi bấm **Save changes**. Với CORS PUT yêu cầu `If-None-Match` theo pipeline hiện tại, giữ header đó trong `AllowedHeaders`:

```json
[
  {
    "AllowedOrigins": ["https://<CLOUDFRONT_DOMAIN>"],
    "AllowedMethods": ["PUT", "HEAD"],
    "AllowedHeaders": ["Content-Type", "If-None-Match"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 300
  }
]
```

CORS chỉ cho phép trình duyệt gửi request từ origin web; quyền S3 vẫn do IAM/presigned URL quyết định. Object raw theo `lessons/{lesson_id}/raw/{random_id}.mp4`; processed dùng prefix tương ứng `lessons/{lesson_id}/processed/`.

## 5. Tạo Cognito User Pool

**Chịu trách nhiệm:** B tích hợp OIDC/PKCE và kiểm thử sign-in; D cấu hình issuer/API
authorizer và ánh xạ identity ở backend. Chủ account quản lý danh tính IAM Identity Center
riêng cho thành viên nhóm theo mục 0; danh tính người học/demo do nhóm ứng dụng chuẩn bị.

1. B (frontend) đăng nhập Console → ô tìm dịch vụ → **Amazon Cognito** → đảm bảo Region `ap-southeast-1` → **User pools → Create user pool**.
2. **Configure sign-in experience** → chọn **Email** → **Next**. Ở security requirements, giữ password policy mạnh mặc định; MFA chọn **Optional** cho demo hoặc **Required** nếu toàn bộ người demo có MFA; **Next**.
3. **Configure sign-up experience** → tắt self-service sign-up nếu chỉ dùng tài khoản demo được tạo thủ công; **Next**.
4. **Configure message delivery** → dùng email gửi mặc định nếu phù hợp demo → **Next**.
5. **Integrate your app** → tên pool `learncloud-demo-users`; application type **Single-page application (SPA)**; nhập app name `learncloud-web`; callback/logout tạm để trống nếu màn hình cho phép, nếu bắt buộc thì chờ CloudFront ở mục 10 rồi quay lại. Chọn **Create user directory**.
6. Pool hoàn tất → menu trái **App clients** → chọn `learncloud-web`. Xác nhận client là public SPA, **không có client secret**. Ghi **User pool ID** và **Client ID**.
7. Trong pool → **App integration → Domain → Create Cognito domain**. Nhập prefix duy nhất (ví dụ `learncloud-<account-id>-<suffix>`) → **Create Cognito domain**. Ghi domain và issuer `https://cognito-idp.ap-southeast-1.amazonaws.com/<USER_POOL_ID>`.
8. Pool → **Groups → Create group**. Tạo lần lượt `Instructor`, `Student`, `Admin`; không thêm quyền AWS cho các group này.
9. Pool → **Users → Create user**. Tạo user demo bằng email nhóm kiểm soát; chọn gửi invitation hoặc đặt mật khẩu theo chính sách. Mở user → **Add to group** → chọn đúng nhóm. Lặp lại cho Instructor/Student demo.
10. Sau khi có domain CloudFront ở mục 10, vào **App clients → learncloud-web → Login pages/Managed login** (tên tab có thể khác) → **Edit**. Bật Authorization code grant, scope `openid`, callback `https://<CLOUDFRONT_DOMAIN>/`, sign-out URL cùng origin; lưu. Chỉ thêm URL thật của môi trường demo.

> Tạo User Pool không tự tích hợp đăng nhập vào frontend/backend. Chỉ mở API Gateway routes cho người dùng sau khi B và D hoàn tất code OIDC/JWT theo mục 1.

Cognito chỉ xác minh danh tính/token. Backend vẫn phải kiểm tra quyền sở hữu course, enrollment và unlock.

## 6. Tạo Secrets Manager secret và RDS PostgreSQL

**Chịu trách nhiệm:** D chuẩn bị cấu hình kết nối và migration; chủ DB quyết định schema,
credentials ứng dụng và thời điểm áp dụng; chủ account cấp secret access cho runtime role.

### 6.1 Secret

1. D (và chủ DB) vào **Secrets Manager → Secrets → Store a new secret**.
2. Chọn **Other type of secret** → **Key/value pairs**. Nhập `username` và `password` của DB application user do chủ DB chuẩn bị; bấm **Next**. Không dùng password master.
3. Secret name nhập `learncloud/demo/database`; description `LearnCloud application DB credentials`; **Next**.
4. Rotation để **Disable automatic rotation** cho demo trừ khi nhóm đã triển khai quy trình rotation → **Next → Store**.
5. Mở secret vừa tạo → **Retrieve secret value** để kiểm tra tên key (không chụp/chia sẻ giá trị). Ghi **Secret ARN** vào bảng bàn giao.

### 6.2 DB subnet group và database

1. RDS → menu trái **Subnet groups → Create DB subnet group**. Nhập name `learncloud-db-subnets`, description `Private subnets for LearnCloud`, VPC `learncloud`; chọn hai Availability Zones và hai private subnet đã ghi ở mục 3 → **Create**.
2. RDS → **Databases → Create database** → **Standard create** → **Engine type: PostgreSQL**. Chọn phiên bản được policy lớp/lab hỗ trợ (16 nếu có) → template **Free tier** nếu thực sự đủ cho lab, nếu không **Dev/Test** → **Next**.
3. **Settings**: DB instance identifier `learncloud-demo-db`; Master username nhập tên quản trị DB riêng; chọn **Manage master credentials in Secrets Manager** nếu tùy chọn có. Nếu không, chủ DB tự tạo password và cất an toàn; không ghi vào repo/tài liệu.
4. **Instance configuration**: chọn lớp nhỏ nhất được phép và đủ cho demo; **Storage**: loại General Purpose SSD, bật encryption, chỉ bật storage autoscaling với giới hạn đã được duyệt. Backup retention đặt theo thời gian demo (ví dụ 7 ngày).
5. **Connectivity**: VPC `learncloud`; **DB subnet group** `learncloud-db-subnets`; Public access **No**; VPC security group **Choose existing** → bỏ default nếu có → chọn `learncloud-rds-sg`; port 5432. Không bật public access.
6. **Database authentication**: password authentication. **Additional configuration** → Initial database name `learncloud`; giữ deletion protection bật khi đang nghiệm thu/giữ dữ liệu; tắt Performance Insights nếu không được duyệt phí.
7. Kéo xuống xem **Estimated monthly costs**; nếu chưa có budget approval thì bấm Cancel. Nếu được duyệt, bấm **Create database**.
8. RDS → **Databases → learncloud-demo-db**. Chờ **Status = Available**. Tab **Connectivity & security** → ghi endpoint, port, subnet group, security group ID. Không gửi mật khẩu cùng endpoint.
9. Chủ DB bootstrap role/schema theo migration đã được review; cập nhật secret `learncloud/demo/database` để `username/password` khớp application user. Lambda không dùng master user.
10. Dùng [quy trình migration 0005](video-pipeline-migration-0005.md) để preflight/backup/review/apply/verify. Nếu version registry hoặc constraint khác điều kiện migration, dừng; không sửa DB Console trực tiếp.

## 7. Tạo IAM execution roles

**Chịu trách nhiệm:** Chủ account/IAM admin tạo hoặc duyệt runtime roles; D cung cấp
trust/policy templates và xác nhận mỗi role chỉ có quyền của dịch vụ tương ứng.

**Không tạo một role chung.** Role pipeline đã có template trong `infrastructure/iam/`; cần tạo đúng sáu role runtime như bảng ở [hướng dẫn triển khai pipeline, Phần 2](aws-video-pipeline-console-setup.md#phan-2--iam-roles-va-policies). API Lambda role chưa có template phù hợp trong repo; D phải hoàn tất cấu hình API và gửi policy đã review trước khi chủ account tạo role đó.

### 7.1 Tạo runtime roles theo template

1. Chủ account/IAM administrator mở **IAM → Policies → Create policy → JSON**.
2. Trong Explorer mở `infrastructure/iam/README.md`; dùng bảng role ở đó để ghép mỗi file `*-permissions.json` với trust file tương ứng. Tạo một policy riêng cho từng service, thay tất cả placeholder theo ARN/Account ID đã ghi. Không thêm password/secret value vào JSON.
3. Trong IAM wizard bấm **Next** → nhập tên policy theo role → **Create policy**. Nếu AWS báo quyền `Resource: *`, kiểm tra đúng file template; không tự mở rộng thêm quyền.
4. IAM → **Roles → Create role → Custom trust policy**. Mở trust JSON tương ứng trong repo, thay `${ACCOUNT_ID}` nếu file yêu cầu → dán vào ô **Custom trust policy** → **Next**.
5. Tìm policy vừa tạo, đánh dấu checkbox → **Next** → đặt chính xác tên role từ `infrastructure/iam/README.md` → **Create role**.
6. Mở role → tab **Trust relationships** → xác nhận service principal đúng (Lambda, Step Functions, EventBridge hoặc MediaConvert). Tab **Permissions** → xác nhận chỉ có policy tương ứng.
7. Lặp lại cho sáu role. Thứ tự xử lý ARN placeholder và gán PassRole được trình bày đầy đủ trong [Phần 2 của hướng dẫn pipeline](aws-video-pipeline-console-setup.md#phan-2--iam-roles-va-policies); theo đúng thứ tự đó vì một số policy cần ARN của role/function/state machine đã tạo.
8. Ghi role ARN vào bảng bàn giao. Không copy ARN/private data vào Git. Không tạo API Lambda role cho đến khi D cung cấp policy API được duyệt.

Không gắn `AdministratorAccess`, `PowerUserAccess`, `s3:*`, `bedrock:*` hoặc `iam:*` cho runtime role.

## 8. Đóng gói FastAPI ZIP và tạo Lambda

**Chịu trách nhiệm:** D đóng gói và cấu hình Lambda; chủ account cấp quyền triển khai;
B cung cấp API URL/config cần cho frontend.

### 8.1 Video pipeline Lambda

Trong repository, `infrastructure/lambda/video_pipeline_handler.py` có ba entry point và hướng dẫn đóng gói trong `docs/aws-video-pipeline-console-setup.md`. Theo [Phần 4 — Lambda](aws-video-pipeline-console-setup.md#phan-4--lambda), người thao tác thực hiện tuần tự:

1. D chuẩn bị ZIP theo script/hướng dẫn trong repo trên Windows hoặc môi trường Linux tương thích. Không tải source ZIP có `.env`, credentials hay `.venv`.
2. Console → chọn Region `ap-southeast-1` → **Lambda → Functions → Create function → Author from scratch**.
3. Tạo lần lượt ba function `learncloud-video-pipeline`, `learncloud-video-relay`, `learncloud-video-recovery`; Runtime **Python 3.12**, Architecture **x86_64**, chọn **Use an existing role** và role tương ứng đã tạo ở mục 7.
4. Mở từng function → tab **Code → Upload from → .zip file → Upload → chọn ZIP → Save**. Vào **Runtime settings → Edit** → nhập handler tương ứng từ `infrastructure/lambda/README.md` → **Save**.
5. Mở **Configuration → General configuration → Edit** → đặt timeout/memory theo `infrastructure/lambda/README.md` → **Save**.
6. Mở **Configuration → Environment variables → Edit** → nhập cấu hình theo bảng ở [Phần 4.3 của runbook pipeline](aws-video-pipeline-console-setup.md#phan-4--lambda). Giữ `VIDEO_PIPELINE_ENABLED=false` cho đến khi DB schema/network/IAM đã sẵn sàng; AI flag giữ false.
7. Mở **Configuration → VPC → Edit** → chọn VPC `learncloud`, hai private subnet, security group Lambda → **Save**. Đợi status update xong; kiểm tra Security Group RDS cho phép 5432 từ Lambda SG.
8. Vào **Monitor → View CloudWatch logs** sau khi thử invocation. Không mở function thành public URL.

### 8.2 FastAPI API Lambda — đang chặn

Không tạo `learncloud-api-prod` cho đến khi bảng mục 1 báo **SẴN SÀNG**: repo hiện thiếu `mangum`/handler và Cognito authentication production. Khi D bổ sung code, D cần thêm phụ lục API Lambda với handler thật, environment variables theo `backend/app/config.py`, policy role riêng và smoke test. Không dùng Lambda probe RDS thay cho API LearnCloud; probe ở `infrastructure/lambda/README.md` chỉ đọc DB.

## 9. Tạo API Gateway và Cognito JWT authorizer

**Chịu trách nhiệm:** A tạo/cấu hình API Gateway và chạy smoke test AWS; D bàn giao Lambda,
Cognito values và quyền invoke; B xác nhận frontend gửi JWT đúng.

**Chỉ làm sau mục 8.2 đạt.** A thao tác Console; D cung cấp/đối chiếu ARN và cấu hình; B kiểm tra token ở frontend.

1. A đăng nhập bằng `LearnCloud-AwsIntegration` → Console Region `ap-southeast-1` → **API Gateway → Create API → HTTP API → Build**.
2. **Add integration → Lambda** → chọn function `learncloud-api-prod` → **Next**. API name `learncloud-api-demo` → **Next**.
3. **Configure routes**: thêm route `ANY /{proxy+}` và route `GET /health`; gán cả hai vào Lambda integration. Chưa bật route nghiệp vụ nếu code Cognito chưa xong.
4. **Define stages**: stage `$default`, bật **Auto-deploy** → **Next → Create**.
5. API vừa tạo → **Authorization → Manage authorizers → Create** → Authorizer type **JWT**; Name `learncloud-cognito-jwt`; Identity source `$request.header.Authorization`; Issuer URL `https://cognito-idp.ap-southeast-1.amazonaws.com/<USER_POOL_ID>`; Audience `<APP_CLIENT_ID>` → **Create**.
6. Menu **Routes** → chọn từng route nghiệp vụ → **Attach authorization** (hoặc **Manage authorization**) → chọn `learncloud-cognito-jwt` → **Save**. `/health` chỉ để public nếu A đồng ý.
7. Menu **Stages → $default**: xác nhận Auto-deploy. Ghi **Invoke URL**. Dán vào trình duyệt `/health`; chỉ coi smoke test đạt nếu response `{"status":"ok"}`. Thử route nghiệp vụ không token phải trả 401.
8. Nếu Console hỏi quyền invoke cho Lambda integration, chỉ cho phép API Gateway vừa tạo. D kiểm tra Lambda → **Configuration → Permissions**; resource policy phải giới hạn đúng API này.
9. A ghi API ID, Invoke URL, route/auth map vào bảng bàn giao. Test `/health`; route bảo vệ thiếu token phải trả 401. Với token hợp lệ, gọi một GET nghiệp vụ đã được D/B chọn và ghi HTTP status/request ID để tra CloudWatch.

Tham khảo [AWS: tạo JWT authorizer cho HTTP API](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html). API Gateway xác minh token; backend vẫn phải phân quyền theo role/ownership/enrollment.

## 10. Tạo frontend S3 + CloudFront (K1)

**Chịu trách nhiệm:** B build, upload và kiểm tra trang; D phối hợp OAC/bucket policy,
Cognito callback/logout và CORS; A xác nhận URL nghiệm thu.

### 10.1 Upload web build

1. B chỉ build sau khi D cấp API URL và Cognito values thật, và B đã hoàn tất OIDC integration. Mở PowerShell tại thư mục repo:

```powershell
cd frontend
$env:VITE_API_URL = "<API_GATEWAY_INVOKE_URL>"
npm.cmd install
npm.cmd run build
```

2. Chạy lệnh trong PowerShell; kết quả phải có `frontend/dist/index.html`. Nếu npm báo lỗi, dừng và xử lý build trước khi upload.
3. S3 Console → **Buckets** → chọn bucket frontend đã ghi mục 4 → **Upload → Add files**. Mở `frontend/dist`, nhấn `Ctrl+A` chọn toàn bộ file/thư mục con → **Open → Upload**. Chờ **Upload succeeded**.
4. Bucket → **Properties → Static website hosting**: xác nhận **Disabled**. **Permissions → Block public access**: xác nhận bật cả bốn cài đặt.

### 10.2 CloudFront OAC

1. Mở **CloudFront → Distributions → Create distribution**.
2. Nếu màn hình onboarding hỏi distribution type, chọn **Single website or app → Next**. Chọn **Amazon S3** làm origin type → **Browse S3** → chọn frontend bucket → **Use recommended origin settings** (bao gồm OAC).
3. Nhập Distribution name `learncloud-web-demo`; default root object `index.html`; viewer protocol **Redirect HTTP to HTTPS** nếu lựa chọn hiển thị → **Next** qua phần security/WAF theo chính sách nhóm → **Create distribution**.
4. CloudFront → distribution mới → tab **Origins** → chọn S3 origin → xác nhận **Origin access control** đang bật. Tab **Behaviors**: default behavior dùng S3 origin và redirect HTTP to HTTPS.
5. Nếu CloudFront hiện nút **Copy policy / Update bucket policy**, mở bucket frontend → **Permissions → Bucket policy → Edit**, dán policy CloudFront tạo → **Save changes**. Policy phải chỉ cho distribution vừa tạo quyền `s3:GetObject`; không cấp public read.
6. Distribution → tab **Error pages/Custom error responses → Create custom error response**. Tạo 403 và 404, response page path `/index.html`, response code `200`, error caching minimum TTL `0`; lưu từng rule. Nếu màn hình distribution mới có SPA option, cấu hình fallback tương ứng.
7. Chờ **Status = Deployed**. Tab **General** → ghi **Distribution domain name**. Mở `https://<CLOUDFRONT_DOMAIN>`; xác nhận trang load.
8. Quay lại Cognito mục 5 → App client login settings → đặt callback/logout URL thành origin chính xác `https://<CLOUDFRONT_DOMAIN>/` → Save. Quay lại raw S3 → Permissions → CORS, thay origin bằng cùng domain → Save.
9. Mỗi lần upload bản frontend mới: CloudFront → distribution → **Invalidations → Create invalidation** → Object paths `/*` → **Create invalidation**.

Tham khảo [AWS: tạo CloudFront distribution từ S3 với OAC](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/GettingStarted.SimpleDistribution.html). AWS thường tự cập nhật bucket policy khi tạo distribution; luôn kiểm tra policy và giữ bucket private.

### 10.3 Video processed qua CloudFront signed URL

**Đang chặn theo mục 1:** chưa thấy signer trong backend hiện tại. Không tạo/cất private key trong AWS cho đến khi D xác nhận code backend hỗ trợ ký URL và policy key đã review. Khi code sẵn sàng, D/B làm theo phụ lục riêng về signed playback; bước này hiện chưa thể nghiệm thu bằng Console đơn thuần.

Khi signer đã được triển khai, quy trình tổng quát là:

1. Tạo cặp khóa bằng công cụ bảo mật trên máy operator (không dùng CloudShell nếu không có quy trình lưu secret đã duyệt):

   ```bash
   openssl genrsa -out cloudfront-private.pem 2048
   openssl rsa -pubout -in cloudfront-private.pem -out cloudfront-public.pem
   ```

2. CloudFront → **Public keys** → **Create public key**. Name `learncloud-video-public-key`; mở `cloudfront-public.pem`, copy toàn bộ nội dung vào **Public key contents**, lưu.
3. CloudFront → **Key groups** → **Create key group**. Name `learncloud-video-key-group`; thêm public key vừa tạo → **Create key group**.
4. CloudFront → **Distributions** → chọn frontend distribution → **Origins → Create origin**. Chọn S3 processed bucket dạng REST origin; tạo OAC và để **Sign requests**. Cập nhật bucket policy để chỉ distribution này đọc bucket processed.
5. Tạo behavior cho path `lessons/*/processed/*` (hoặc path khớp key thực tế), chọn processed S3 origin, bật trusted authorization/signed URLs và chọn key group `learncloud-video-key-group`. Lưu thay đổi, đợi distribution **Deployed**.
6. Lưu `cloudfront-private.pem` dưới dạng secret trong Secrets Manager; xóa bản tạm khỏi CloudShell sau khi xác nhận secret đã lưu. Cấp quyền đọc secret này cho API Lambda role.
7. Backend phải chỉ ký URL sau khi kiểm tra enrollment, publish và unlock. Kiểm thử URL đã ký truy cập được, URL không ký hoặc hết hạn bị từ chối.

Không bật public access hoặc trả URL S3 trực tiếp cho video học viên. Bước ký URL cần có trong backend trước khi luồng học video được nghiệm thu.

## 11. Tạo pipeline bất đồng bộ K4

**Chịu trách nhiệm:** D triển khai và vận hành pipeline; C bàn giao worker AI/Transcribe
theo contract; chủ DB duyệt migration; A rà soát luồng và điều kiện bật.

State machine đã có trong `infrastructure/step-functions/video_pipeline.asl.json`; AWS chưa triển khai. Thực hiện theo từng màn hình trong [hướng dẫn pipeline](aws-video-pipeline-console-setup.md), vì hướng dẫn đó có các bước cho role, Lambda, Step Functions, EventBridge, CloudWatch và kiểm thử. Không tự tạo workflow mới bằng cách gõ JSON từ tài liệu này.

Trình tự bấm cấp cao: (1) xác nhận migration/DB/VPC/IAM; (2) tạo ba Lambda và gắn VPC; (3) thay ARN placeholder theo hướng dẫn; (4) **Step Functions → State machines → Create state machine → Standard → Write workflow in code**, dán ASL đã thay placeholder và chọn role Step Functions; (5) **S3 → bucket raw → Properties → Amazon EventBridge → Edit → On**; (6) **EventBridge → Rules → Create rule** cho upload, retry, recovery và relay tick; (7) bật rule sau khi test sandbox. Luồng duy nhất là EventBridge, không thêm S3→Lambda trực tiếp.

Điều kiện trước khi chạy video E2E: migration 0005 được chủ DB áp dụng; các Lambda cùng kết nối DB có schema tương thích; S3 raw CORS/immutable policy; IAM roles/PassRole đúng; VIDEO_PIPELINE_ENABLED true. AI vẫn tắt cho đến khi C bàn giao worker thật. Xem chi tiết từng nút, pattern và test tại [Phần 2–8 của runbook pipeline](aws-video-pipeline-console-setup.md).

MediaConvert và Transcribe phát sinh chi phí theo job/usage. Dùng một video ngắn để nghiệm thu, dọn output thử sau khi kiểm tra.

## 12. Bedrock K5

**Chịu trách nhiệm:** C chọn/tích hợp model và kiểm tra đầu ra; D cấu hình role, network,
feature flag và log; A duyệt phạm vi/chi phí.

1. Chỉ C/D làm bước này sau khi A duyệt model, Region, ngân sách và dữ liệu được phép gửi. Mở **Amazon Bedrock** ở `ap-southeast-1` → menu **Model catalog** → lọc theo Region/model family → chọn model → ghi **Model ID** và **Input/Output price**.
2. Với model cần form/điều khoản, chọn **Open in playground** và hoàn thành yêu cầu của nhà cung cấp. Với đa số model thương mại hiện tại, access có thể bắt đầu ở lần invoke đầu và cần quyền AWS Marketplace tương ứng; không thấy nút “Enable model access” không đồng nghĩa model đã chạy được. Xem [AWS: request access to models](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html).
3. C không tự chạy playground bằng dữ liệu thật. Chỉ dùng prompt thử không chứa PII; dừng nếu Console hiện giá/điều khoản chưa được duyệt hoặc báo AccessDenied.
4. D mở **IAM → Roles → role của Lambda gọi AI → Permissions → Add permissions → Create inline policy → JSON**. Dán policy đã giới hạn `bedrock:InvokeModel`/`bedrock:Converse` đúng Model ID/ARN, chọn **Next**, đặt tên `LearnCloudInvokeApprovedModel`, bấm **Create policy**. Không dùng `bedrock:*`.
5. Nếu Lambda ở VPC, VPC → Endpoints xác nhận `bedrock-runtime` **Available** và endpoint SG inbound HTTPS 443 chỉ nhận từ Lambda SG.
6. Giữ `VIDEO_AI_ENABLED=false` cho đến khi C bàn giao worker theo contract và D xác nhận log/role/feature flag. Không bật Guardrail hay AI bằng Console nếu worker không đọc cấu hình đó.

## 13. CloudWatch K6 và theo dõi chi phí

**Chịu trách nhiệm:** A cấu hình log retention, SNS và CloudWatch alarms; D bàn giao tên
function/state machine và xử lý lỗi ứng dụng; chủ account theo dõi Billing.

Trước khi tạo alarm, A tạo SNS notification topic nếu chưa có: **Amazon SNS → Topics → Create topic → Standard** → nhập `learncloud-ops-alerts` → **Create topic**. Mở topic → **Create subscription** → Protocol **Email** → nhập email nhóm đã xác nhận → **Create subscription**. Người nhận phải mở email AWS và bấm **Confirm subscription**; quay lại SNS và xác nhận `Subscription status = Confirmed`.

1. A mở **CloudWatch → Logs → Log groups**. Chọn từng group `/aws/lambda/<FUNCTION_NAME>` → **Actions → Edit retention setting** → chọn **1 week** hoặc **2 weeks** → **Save**. Làm với từng function sau lần deploy đầu.
2. Trong log group, mở log stream mới nhất → kiểm tra có START/END/report lỗi; không chia sẻ log nếu có dữ liệu nhạy cảm.
3. CloudWatch → **Alarms → All alarms → Create alarm → Select metric**. Mở **Lambda → By Function Name → Errors → chọn function → Select metric** → statistic `Sum`, period `5 minutes`, threshold `>= 1` → **Next**.
4. Ở **Configure actions**, chọn SNS topic `learncloud-ops-alerts` và email subscription đã confirm. Nhập alarm name `learncloud-<function>-errors` → **Next → Create alarm**. Lặp cho Lambda `Errors` và `Throttles`.
5. Tạo alarm tương tự cho Step Functions → metric `ExecutionsFailed` trên state machine và API Gateway 5xx sau khi API sẵn sàng. Nếu namespace/metric chưa xuất hiện, chạy một request test rồi quay lại.
6. Billing and Cost Management → **Budgets** → `learncloud-demo-budget` → xác nhận trạng thái và notification recipients. Chủ account kiểm tra hàng ngày trong thời gian demo; budget không tự dừng dịch vụ.
7. Log chỉ ghi lesson_id, execution_id, bước xử lý, thời gian, status và lỗi đã làm sạch; không ghi PII, secret, JWT hay URL ký.

## 14. Nghiệm thu, giữ môi trường 1–2 tuần

**Chịu trách nhiệm:** A điều phối nghiệm thu; B kiểm tra UI; C kiểm tra AI/review;
A kiểm tra API Gateway/CloudWatch; D kiểm tra backend Lambda, DB, upload/workflow;
chủ account xác nhận chi phí/thời hạn giữ.

| Kiểm tra | Kết quả mong đợi |
|---|---|
| CloudFront domain | Trang React tải qua HTTPS; S3 frontend vẫn private |
| Cognito | Tài khoản demo đăng nhập, nhận JWT; callback đúng domain |
| API Gateway | Request không token nhận 401; token hợp lệ gọi API |
| Authorization | Student không xem draft/lesson chưa unlock; Instructor chỉ sửa course của mình |
| RDS | Private, không public; Lambda kết nối qua TCP 5432 |
| Upload | Backend cấp presigned PUT; browser tải trực tiếp vào raw S3 |
| Workflow | Chỉ bật sau migration 0005 + DB/network/IAM; test theo pipeline runbook, một upload hợp lệ có một run sở hữu; khi AI tắt, kết quả VIDEO_READY không đồng nghĩa đã tạo học liệu AI |
| Review | Instructor xác nhận học liệu; trạng thái và cách publish theo code/schema đang được triển khai. Không kỳ vọng auto-approve hoặc auto-publish |
| Video | Backend kiểm tra enrollment/unlock trước khi cấp CloudFront signed URL |
| Logs/Budget | Logs tra được theo lesson/execution; budget alert đã bật |

1. A điều phối: B mở CloudFront URL ở cửa sổ ẩn danh; đăng nhập demo Instructor và Student; A gọi `/health` và route API cần xác thực, kiểm tra 401/403/response và CloudWatch; D đối chiếu backend/database; C xác nhận AI/review chỉ nếu worker được bật; chủ account xem Budget.
2. D mở Step Functions → state machine → **Executions**; nếu test pipeline, xác nhận execution đã kết thúc và xem từng state. Mở RDS/log để đối chiếu đúng lesson/run; không tự cập nhật DB bằng SQL để làm demo xanh.
3. Nhóm ghi vào bảng nghiệm thu: URL frontend/API (không có secret), user demo đã tạo (không ghi password), Region, account ID, trạng thái từng dòng trong bảng trên, ngày bắt đầu và hạn dọn tài nguyên.
4. A gửi giảng viên URL CloudFront, hướng dẫn tài khoản demo qua kênh riêng và thời hạn kiểm tra. Không gửi AWS portal, AWS credential, DB password, private key hay secret. Trong kỳ giữ các tài nguyên cần demo; chủ account tiếp tục xem Budget hằng ngày.

## 15. Cleanup sau khi giảng viên xác nhận

**Chịu trách nhiệm:** D lập thứ tự dọn tài nguyên và thực hiện phần triển khai; chủ account
gỡ danh tính/quyền và xác nhận Billing; A lưu biên bản/bàn giao. Chỉ cleanup sau khi giảng
viên xác nhận hoàn tất.

1. Chỉ bắt đầu sau khi A xác nhận giảng viên đã hoàn tất và chủ DB xác nhận có/không giữ dữ liệu. Tải backup/dữ liệu cần bàn giao trước khi xóa.
2. D mở **EventBridge → Rules** → từng rule LearnCloud → **Disable**. Chờ trạng thái Disabled. Dừng relay tick trước khi dừng workflow.
3. Step Functions → state machine → **Stop execution** chỉ cho run còn chạy sau khi đã xem ảnh hưởng; lưu execution history cần thiết. Xóa state machine sau đó.
4. Lambda → **Functions** → chọn function LearnCloud → **Actions → Delete** → nhập xác nhận → **Delete**. Xóa cả ba pipeline function và API function nếu đã tồn tại.
5. API Gateway → **APIs** → chọn API LearnCloud → **Actions → Delete** → nhập tên xác nhận → **Delete**.
6. CloudFront → **Distributions** → chọn distribution → **Disable** → **Save changes** → chờ **Deployed** → **Delete**. Lặp với distribution video riêng nếu có.
7. CloudFront → **Public keys / Key groups** → xóa video key group/public key nếu đã tạo và không còn distribution dùng. Xóa khóa private khỏi nơi lưu tạm theo quy trình của nhóm; xóa Secrets Manager secret signer sau khi runtime đã dừng.
8. S3 → mở từng bucket → **Empty** → nhập xác nhận → **Empty bucket**. Chỉ sau khi xác nhận không cần dữ liệu, vào **Delete bucket** → nhập bucket name → **Delete**. Không xóa bucket có dữ liệu cần giữ.
9. RDS → **Databases** → chọn DB → **Actions → Delete**. Bỏ final snapshot chỉ khi chủ DB duyệt và đã có backup khác; nếu không, giữ snapshot. Sau DB, xóa subnet group nếu không còn DB nào dùng.
10. CloudWatch → **Alarms → All alarms** → đánh dấu alarms LearnCloud → **Actions → Delete**. Vào **Logs → Log groups** → chọn nhóm `/aws/lambda/learncloud-*` → **Delete log group**. Xóa SNS topic chỉ nếu topic được tạo riêng cho demo.
11. Xóa Cognito demo users/User Pool nếu không cần giữ; xóa VPC endpoints, security groups, subnets/VPC theo dependency (AWS sẽ báo resource nào còn attached). Xóa Secrets Manager secrets cuối cùng sau khi runtime đã dừng.
12. IAM → **Roles** → xóa các LearnCloud runtime roles sau khi service đã xóa; trước tiên mở role → **Permissions** → detach/delete policy gắn riêng cho demo → **Delete role**. Không xóa policy/role dùng chung của account/lab.
13. IAM Identity Center → **AWS accounts → Assign users or groups** → bỏ gán permission set của thành viên cần thu hồi; gỡ user khỏi group hoặc disable user theo chính sách nhóm. Chủ account kiểm tra **Billing → Bills/Cost Explorer** và Budgets vài ngày sau cleanup để tìm phí còn phát sinh.

## Trạng thái hiện tại của repository

Repo hiện có React/Vite, FastAPI, S3 adapter, video pipeline Lambda/ASL/EventBridge templates. AWS vẫn ghi **NOT DEPLOYED** trong tài liệu pipeline. API Cognito production, Mangum/API Lambda handler và signed video playback chưa sẵn sàng; migration 0005 chưa áp dụng. Chỉ gọi là **AWS verified** sau khi từng bước nghiệm thu trên account thật đạt; local/mock test không chứng minh dịch vụ AWS đã hoạt động.
